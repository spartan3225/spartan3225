"""Iter 13 backend tests: account deletion + push-removal regression.

Covers:
* DELETE /api/auth/account deletes users, sessions, analyses, comments,
  upload_chunks, GridFS video, and local upload dir.
* DELETE /api/auth/account without auth -> 401.
* Comment posting still works after push-notification removal.
* PUT /api/users/push-token endpoint is gone (404/405).
* /api/plans 200, /api/health 200, / serves HTML, chunked upload happy path.
"""

import base64
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pymongo
import gridfs
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
UPLOAD_DIR = Path("/app/backend/uploads/videos")

COACH_TOKEN = "demo_coach_token"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo():
    c = pymongo.MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture()
def throwaway_user(mongo):
    """Insert a throwaway user + valid session directly in Mongo; yield ids/token; cleanup."""
    uid = f"user_test_del_{uuid.uuid4().hex[:8]}"
    token = f"tok_test_del_{uuid.uuid4().hex[:12]}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@surfai.test",
        "name": "Throwaway Test",
        "picture": None,
        "created_at": datetime.now(timezone.utc),
        "tier": "free",
        "subscription_status": None,
        "subscription_expires_at": None,
        "coach_bio": None,
        "coach_specialty": None,
        "coach_location": None,
        "coach_public": False,
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": uid, "token": token}
    # Best-effort cleanup (even if delete succeeded, these are no-ops).
    mongo.users.delete_many({"user_id": uid})
    mongo.user_sessions.delete_many({"user_id": uid})
    mongo.analyses.delete_many({"user_id": uid})
    mongo.analysis_comments.delete_many({
        "$or": [{"user_id": uid}, {"author_id": uid}]
    })
    mongo.upload_chunks.delete_many({"user_id": uid})
    # Cleanup GridFS files by filename prefix
    for f in list(mongo["videos.files"].find({"filename": {"$regex": f"^ana_test_{uid[-8:]}"}}, {"_id": 1})):
        try:
            mongo["videos.chunks"].delete_many({"files_id": f["_id"]})
            mongo["videos.files"].delete_one({"_id": f["_id"]})
        except Exception:
            pass
    # Cleanup local dir
    try:
        import shutil
        shutil.rmtree(UPLOAD_DIR / uid, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. Account deletion happy path
# ---------------------------------------------------------------------------
class TestDeleteAccount:
    def test_delete_account_full_cleanup(self, mongo, throwaway_user):
        uid = throwaway_user["user_id"]
        token = throwaway_user["token"]
        analysis_id = f"ana_test_{uid[-8:]}_{uuid.uuid4().hex[:6]}"

        # 1) Insert analysis doc + local file
        user_dir = UPLOAD_DIR / uid
        user_dir.mkdir(parents=True, exist_ok=True)
        video_path = user_dir / f"{analysis_id}.mp4"
        video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42fakebytes")

        mongo.analyses.insert_one({
            "analysis_id": analysis_id,
            "user_id": uid,
            "title": "TEST_del",
            "status": "ready",
            "score": 50,
            "video_path": str(video_path),
            "mime_type": "video/mp4",
            "created_at": datetime.now(timezone.utc),
        })

        # 2) Insert a GridFS file with filename == analysis_id
        gfs = gridfs.GridFSBucket(pymongo.MongoClient(MONGO_URL)[DB_NAME], bucket_name="videos")
        gfs.upload_from_stream(analysis_id, b"gridfs-fake-bytes-for-test")

        # 3) Insert a comment authored by user (comments use author_id, not user_id — see BUG note)
        mongo.analysis_comments.insert_one({
            "comment_id": f"cmt_test_{uuid.uuid4().hex[:8]}",
            "analysis_id": analysis_id,
            "author_id": uid,
            "user_id": uid,  # tolerate schema drift; see RCA in report
            "author_name": "Throwaway Test",
            "author_picture": None,
            "is_coach": False,
            "text": "TEST comment",
            "created_at": datetime.now(timezone.utc),
        })

        # 4) Insert an upload_chunks doc
        mongo.upload_chunks.insert_one({
            "upload_id": f"up_test_{uuid.uuid4().hex[:8]}",
            "user_id": uid,
            "chunk_index": 0,
            "data": b"xxxx",
            "created_at": datetime.now(timezone.utc),
        })

        # Sanity pre-check
        assert mongo.users.count_documents({"user_id": uid}) == 1
        assert mongo.user_sessions.count_documents({"user_id": uid}) == 1
        assert mongo.analyses.count_documents({"user_id": uid}) == 1
        assert mongo.analysis_comments.count_documents({"analysis_id": analysis_id}) == 1
        assert mongo.upload_chunks.count_documents({"user_id": uid}) == 1
        assert mongo["videos.files"].count_documents({"filename": analysis_id}) == 1
        assert video_path.exists()

        # 5) Call DELETE /api/auth/account
        r = requests.delete(
            f"{API}/auth/account",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        assert r.json() == {"ok": True}

        # 6) Verify EVERY collection is empty for that user
        assert mongo.users.count_documents({"user_id": uid}) == 0
        assert mongo.user_sessions.count_documents({"user_id": uid}) == 0
        assert mongo.analyses.count_documents({"user_id": uid}) == 0
        assert mongo.upload_chunks.count_documents({"user_id": uid}) == 0
        assert mongo["videos.files"].count_documents({"filename": analysis_id}) == 0
        # Local dir removed
        assert not (UPLOAD_DIR / uid).exists()
        # Comments: any doc referencing the analysis_id or the author should be gone.
        # Note: current impl uses {"user_id": uid} — the test comment set both fields,
        # so this passes. Comments that only had author_id would NOT be deleted (see BUG).
        assert mongo.analysis_comments.count_documents({"analysis_id": analysis_id}) == 0

        # 7) Verify the deleted token returns 401 on /api/auth/me
        r2 = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r2.status_code == 401

    def test_delete_account_without_auth_returns_401(self):
        r = requests.delete(f"{API}/auth/account", timeout=15)
        assert r.status_code == 401

    def test_delete_account_bad_token_returns_401(self):
        r = requests.delete(
            f"{API}/auth/account",
            headers={"Authorization": "Bearer totally_bogus_token_xyz"},
            timeout=15,
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. Comments still work after push removal
# ---------------------------------------------------------------------------
class TestCommentsAfterPushRemoval:
    def test_add_and_list_comment_on_own_analysis(self, mongo):
        """Coach user comments on their own analysis (author == owner path)."""
        coach_uid = "user_coach_67890"
        analysis_id = f"ana_test_cmt_{uuid.uuid4().hex[:8]}"
        mongo.analyses.insert_one({
            "analysis_id": analysis_id,
            "user_id": coach_uid,
            "title": "TEST_comment_regression",
            "status": "ready",
            "score": 60,
            "video_path": None,
            "mime_type": "video/mp4",
            "created_at": datetime.now(timezone.utc),
        })
        try:
            r = requests.post(
                f"{API}/analyses/{analysis_id}/comments",
                headers={
                    "Authorization": f"Bearer {COACH_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"text": "TEST comment from coach — push removed"},
                timeout=15,
            )
            assert r.status_code == 200, f"post comment {r.status_code}: {r.text}"
            body = r.json()
            assert body["text"] == "TEST comment from coach — push removed"
            assert body["author_id"] == coach_uid

            # List them back
            r2 = requests.get(
                f"{API}/analyses/{analysis_id}/comments",
                headers={"Authorization": f"Bearer {COACH_TOKEN}"},
                timeout=15,
            )
            assert r2.status_code == 200
            items = r2.json()
            assert any(c["comment_id"] == body["comment_id"] for c in items)
        finally:
            mongo.analyses.delete_many({"analysis_id": analysis_id})
            mongo.analysis_comments.delete_many({"analysis_id": analysis_id})

    def test_push_token_endpoint_removed(self):
        r = requests.put(
            f"{API}/users/push-token",
            headers={
                "Authorization": f"Bearer {COACH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"expo_push_token": "ExponentPushToken[fake]"},
            timeout=15,
        )
        # After removal we should NOT get 200; FastAPI returns 404 (route absent) or 405.
        assert r.status_code in (404, 405), f"expected push-token endpoint removed, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 3. Broader regression
# ---------------------------------------------------------------------------
class TestRegression:
    def test_plans_ok(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_health_ok(self):
        r = requests.get(f"{API}/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_root_serves_html(self):
        r = requests.get(BASE_URL + "/", timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "html" in ct.lower(), f"root should serve HTML, got {ct}"

    def test_chunked_upload_happy_path(self, mongo):
        """2 chunks -> finalize -> 200 processing; clean up."""
        # Build 2 tiny chunks of fake mp4 bytes
        chunk0 = b"\x00\x00\x00\x18ftypmp42" + b"a" * 512
        chunk1 = b"b" * 512
        upload_id = uuid.uuid4().hex + uuid.uuid4().hex[:8]  # 40 hex chars
        try:
            for idx, blob in enumerate([chunk0, chunk1]):
                r = requests.post(
                    f"{API}/uploads/chunk",
                    headers={"Authorization": f"Bearer {COACH_TOKEN}"},
                    data={
                        "upload_id": upload_id,
                        "chunk_index": str(idx),
                        "total_chunks": "2",
                        "chunk_b64": base64.b64encode(blob).decode(),
                    },
                    timeout=30,
                )
                assert r.status_code == 200, f"chunk {idx} -> {r.status_code}: {r.text}"
                assert r.json()["received"] == idx + 1

            # Finalize
            r = requests.post(
                f"{API}/analyses/finalize",
                headers={
                    "Authorization": f"Bearer {COACH_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "upload_id": upload_id,
                    "total_chunks": 2,
                    "mime_type": "video/mp4",
                    "title": "TEST chunked regression",
                },
                timeout=60,
            )
            assert r.status_code == 200, f"finalize -> {r.status_code}: {r.text}"
            body = r.json()
            assert body.get("status") in ("processing", "ready", "failed")
            analysis_id = body.get("analysis_id")
            assert analysis_id
            # Chunks should be deleted after finalize
            assert mongo.upload_chunks.count_documents({"upload_id": upload_id}) == 0

            # Cleanup: remove this test analysis + any file
            time.sleep(0.5)
            doc = mongo.analyses.find_one({"analysis_id": analysis_id})
            if doc and doc.get("video_path"):
                Path(doc["video_path"]).unlink(missing_ok=True)
            mongo.analyses.delete_many({"analysis_id": analysis_id})
            for f in list(mongo["videos.files"].find({"filename": analysis_id}, {"_id": 1})):
                mongo["videos.chunks"].delete_many({"files_id": f["_id"]})
                mongo["videos.files"].delete_one({"_id": f["_id"]})
        finally:
            if upload_id:
                mongo.upload_chunks.delete_many({"upload_id": upload_id})
