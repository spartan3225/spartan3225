"""Iteration 12 — Security fix verification (SEC-001, SEC-002, SEC-003).

SEC-001: analysis quota race — post-insert quota guard in
         _finalize_and_start_analysis (fail-closed under concurrency).
SEC-002: unbounded uploads — MAX_CHUNK_BYTES=8MB (413), total_chunks cap
         500->100 (400 invalid chunk index), MAX_VIDEO_BYTES=300MB.
SEC-003: GET /api/analyses/{id}/video?token= now validates session expires_at
         (401 'Session expired').
"""

from __future__ import annotations

import base64
import concurrent.futures as cf
import io
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

# -------- Config ----------------------------------------------------------
BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = (
    open("/app/backend/.env").read().split("MONGO_URL=")[1].split("\n")[0].strip('"')
)
DB_NAME = "test_database"

FREE_TOKEN = "demo_token_active"
FREE_USER_ID = "user_demo_12345"
COACH_TOKEN = "demo_coach_token"
COACH_USER_ID = "user_coach_67890"

# ---- Minimal valid-ish MP4 payload (fake — background AI will fail; fine).
# We just need bytes small enough for chunk cap tests and to pass upload path.
FAKE_MP4_HEADER = bytes.fromhex(
    "0000001c66747970697336" "6d000000006973" "6f366d70343100"
)

# -------- Helpers ---------------------------------------------------------


def _mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _reset_analyses(user_ids: list[str]) -> None:
    db = _mongo()
    db.analyses.delete_many({"user_id": {"$in": user_ids}})
    # also clean any orphan chunks
    db.upload_chunks.delete_many({"user_id": {"$in": user_ids}})


def _cleanup_local_files(user_id: str) -> None:
    d = f"/app/backend/uploads/videos/{user_id}"
    if os.path.isdir(d):
        for name in os.listdir(d):
            try:
                os.remove(os.path.join(d, name))
            except OSError:
                pass


def _reseed_users() -> None:
    db = _mongo()
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"user_id": FREE_USER_ID},
        {
            "$set": {
                "email": "demo@surfai.test",
                "name": "Demo Surfer",
                "tier": "free",
                "subscription_status": None,
                "subscription_expires_at": None,
                "coach_public": False,
            },
            "$setOnInsert": {"created_at": now, "user_id": FREE_USER_ID},
        },
        upsert=True,
    )
    db.users.update_one(
        {"user_id": COACH_USER_ID},
        {
            "$set": {
                "email": "demo.coach@surfai.test",
                "name": "Demo Coach",
                "tier": "coach",
                "subscription_status": "active",
                "subscription_expires_at": now + timedelta(days=30),
                "coach_bio": "World-tour coach with 15 years experience.",
                "coach_specialty": "Bottom-turn & rail control",
                "coach_location": "Ericeira, PT",
                "coach_public": True,
            },
            "$setOnInsert": {"created_at": now, "user_id": COACH_USER_ID},
        },
        upsert=True,
    )
    db.user_sessions.update_one(
        {"session_token": FREE_TOKEN},
        {
            "$set": {
                "user_id": FREE_USER_ID,
                "session_token": FREE_TOKEN,
                "expires_at": now + timedelta(days=7),
                "created_at": now,
            }
        },
        upsert=True,
    )
    db.user_sessions.update_one(
        {"session_token": COACH_TOKEN},
        {
            "$set": {
                "user_id": COACH_USER_ID,
                "session_token": COACH_TOKEN,
                "expires_at": now + timedelta(days=7),
                "created_at": now,
            }
        },
        upsert=True,
    )


@pytest.fixture(autouse=True, scope="module")
def _seed_and_teardown():
    _reseed_users()
    _reset_analyses([FREE_USER_ID, COACH_USER_ID])
    yield
    _reset_analyses([FREE_USER_ID, COACH_USER_ID])
    _cleanup_local_files(FREE_USER_ID)
    _cleanup_local_files(COACH_USER_ID)
    _reseed_users()  # restore clean sessions


# =========================================================================
# SEC-002 — chunk size + total_chunks cap
# =========================================================================
class TestSec002ChunkCaps:
    def test_chunk_9mb_returns_413(self):
        upload_id = secrets.token_hex(16)
        payload = os.urandom(9 * 1024 * 1024)  # 9MB > 8MB cap
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_auth(COACH_TOKEN),
            data={"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1},
            files={"file": ("chunk.bin", payload, "application/octet-stream")},
            timeout=60,
        )
        assert r.status_code == 413, r.text
        assert "chunk too large" in r.text.lower()
        # ensure nothing persisted
        assert (
            _mongo().upload_chunks.count_documents({"upload_id": upload_id}) == 0
        )

    def test_chunk_3mb_returns_200(self):
        upload_id = secrets.token_hex(16)
        payload = os.urandom(3 * 1024 * 1024)
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_auth(COACH_TOKEN),
            data={"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1},
            files={"file": ("chunk.bin", payload, "application/octet-stream")},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["received"] == 1
        _mongo().upload_chunks.delete_many({"upload_id": upload_id})

    def test_total_chunks_101_returns_400(self):
        upload_id = secrets.token_hex(16)
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_auth(COACH_TOKEN),
            data={"upload_id": upload_id, "chunk_index": 0, "total_chunks": 101},
            files={"file": ("chunk.bin", b"AAAA", "application/octet-stream")},
            timeout=30,
        )
        assert r.status_code == 400, r.text
        assert "invalid chunk index" in r.text.lower()

    def test_total_chunks_100_returns_200(self):
        upload_id = secrets.token_hex(16)
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_auth(COACH_TOKEN),
            data={"upload_id": upload_id, "chunk_index": 0, "total_chunks": 100},
            files={"file": ("chunk.bin", b"AAAA", "application/octet-stream")},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        _mongo().upload_chunks.delete_many({"upload_id": upload_id})


# =========================================================================
# SEC-002 — legacy /api/analyses small upload still 200 (code-review the cap)
# =========================================================================
class TestSec002LegacySmallUpload:
    def test_small_legacy_upload_still_processes(self):
        _reset_analyses([COACH_USER_ID])
        r = requests.post(
            f"{API}/analyses",
            headers=_auth(COACH_TOKEN),
            files={"file": ("tiny.mp4", FAKE_MP4_HEADER, "video/mp4")},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "processing"
        # cleanup created doc + file
        aid = body["analysis_id"]
        _mongo().analyses.delete_one({"analysis_id": aid})
        _cleanup_local_files(COACH_USER_ID)

    def test_legacy_cap_logic_present_in_code(self):
        """Code-review check: MAX_VIDEO_BYTES=300MB is enforced in legacy path."""
        src = open("/app/backend/server.py").read()
        assert "MAX_VIDEO_BYTES = 300 * 1024 * 1024" in src
        # Legacy path (create_analysis) has the 413 branch
        legacy = src.split("async def create_analysis")[1].split(
            "async def upload_chunk"
        )[0]
        assert "MAX_VIDEO_BYTES" in legacy
        assert "413" in legacy
        assert "Video too large" in legacy


# =========================================================================
# SEC-001 — quota race (concurrent uploads) + sequential regression
# =========================================================================
def _post_free_upload():
    return requests.post(
        f"{API}/analyses",
        headers=_auth(FREE_TOKEN),
        files={"file": ("t.mp4", FAKE_MP4_HEADER, "video/mp4")},
        timeout=60,
    )


class TestSec001QuotaRace:
    def test_three_concurrent_free_uploads_only_one_persists(self):
        _reset_analyses([FREE_USER_ID])
        _cleanup_local_files(FREE_USER_ID)

        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(_post_free_upload) for _ in range(3)]
            results = [f.result() for f in futs]

        codes = sorted([r.status_code for r in results])
        print("concurrent status codes:", codes,
              [r.text[:120] for r in results])

        # At most 1 success (200), the rest must be 402 (either pre-check or
        # post-insert rollback).
        ok = [r for r in results if r.status_code == 200]
        paywall = [r for r in results if r.status_code == 402]
        assert len(ok) <= 1, f"expected <=1 200, got {codes}"
        assert len(ok) + len(paywall) == 3, f"unexpected codes: {codes}"

        # DB state: non-failed count for free user should be <= 1
        db = _mongo()
        remaining = list(
            db.analyses.find(
                {"user_id": FREE_USER_ID, "status": {"$ne": "failed"}},
                {"_id": 0, "analysis_id": 1, "video_path": 1, "status": 1},
            )
        )
        print("remaining analyses:", remaining)
        assert len(remaining) <= 1, f"quota race left {len(remaining)} rows"

        # No orphaned local files for ROLLED-BACK ids: every file on disk
        # must correspond to SOME analysis doc in DB (any status — the
        # background AI task may transition the surviving winner to 'failed'
        # because we ship fake mp4 bytes, and that's expected/fine).
        vdir = f"/app/backend/uploads/videos/{FREE_USER_ID}"
        on_disk = set()
        if os.path.isdir(vdir):
            for name in os.listdir(vdir):
                on_disk.add(name.split(".")[0])
        all_db_ids = {
            row["analysis_id"]
            for row in db.analyses.find(
                {"user_id": FREE_USER_ID}, {"_id": 0, "analysis_id": 1}
            )
        }
        orphans = on_disk - all_db_ids
        assert not orphans, (
            f"orphaned files after rollback: {orphans} "
            f"(db_ids={all_db_ids}, remaining_nonfailed={[r['analysis_id'] for r in remaining]})"
        )

        # cleanup
        _reset_analyses([FREE_USER_ID])
        _cleanup_local_files(FREE_USER_ID)

    def test_sequential_free_second_upload_402(self):
        _reset_analyses([FREE_USER_ID])
        _cleanup_local_files(FREE_USER_ID)
        # Insert an existing non-failed analysis directly (status=ready
        # so it counts toward the cap regardless of bg AI outcome).
        db = _mongo()
        db.analyses.insert_one(
            {
                "analysis_id": "ana_seed_existing_1",
                "user_id": FREE_USER_ID,
                "video_path": "",
                "mime_type": "video/mp4",
                "status": "ready",
                "created_at": datetime.now(timezone.utc),
                "title": "seeded",
                "score": 50,
                "overall_rating": "",
                "summary": "",
                "strengths": [],
                "mistakes": [],
                "corrections": [],
                "tips": [],
                "drills": [],
                "shared_with_coach_id": None,
            }
        )
        r = _post_free_upload()
        assert r.status_code == 402, r.text
        # cleanup
        db.analyses.delete_one({"analysis_id": "ana_seed_existing_1"})

    def test_coach_unlimited_still_uploads(self):
        _reset_analyses([COACH_USER_ID])
        # Coach tier has -1 daily limit; multiple uploads should succeed.
        for _ in range(2):
            r = requests.post(
                f"{API}/analyses",
                headers=_auth(COACH_TOKEN),
                files={"file": ("t.mp4", FAKE_MP4_HEADER, "video/mp4")},
                timeout=60,
            )
            assert r.status_code == 200, r.text
        # cleanup
        _reset_analyses([COACH_USER_ID])
        _cleanup_local_files(COACH_USER_ID)


# =========================================================================
# SEC-003 — expired session on /api/analyses/{id}/video?token=
# =========================================================================
class TestSec003ExpiredSessionVideo:
    def test_expired_session_returns_401_session_expired(self):
        db = _mongo()
        # Create a coach-owned analysis with a real local file so a VALID
        # token would stream 200.
        analysis_id = f"ana_sec003_{secrets.token_hex(6)}"
        vpath = f"/app/backend/uploads/videos/{COACH_USER_ID}/{analysis_id}.mp4"
        os.makedirs(os.path.dirname(vpath), exist_ok=True)
        with open(vpath, "wb") as f:
            f.write(FAKE_MP4_HEADER * 10)

        db.analyses.insert_one(
            {
                "analysis_id": analysis_id,
                "user_id": COACH_USER_ID,
                "video_path": vpath,
                "mime_type": "video/mp4",
                "status": "ready",
                "created_at": datetime.now(timezone.utc),
                "title": "sec003",
                "score": 0,
                "overall_rating": "",
                "summary": "",
                "strengths": [],
                "mistakes": [],
                "corrections": [],
                "tips": [],
                "drills": [],
                "shared_with_coach_id": None,
            }
        )

        # Insert an expired session for the coach user
        expired_token = f"expired_{secrets.token_hex(8)}"
        db.user_sessions.insert_one(
            {
                "user_id": COACH_USER_ID,
                "session_token": expired_token,
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                "created_at": datetime.now(timezone.utc) - timedelta(days=8),
            }
        )

        try:
            # Expired -> 401 Session expired
            r = requests.get(
                f"{API}/analyses/{analysis_id}/video",
                params={"token": expired_token},
                timeout=30,
                allow_redirects=False,
                stream=True,
            )
            assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"
            assert "session expired" in r.text.lower(), r.text

            # Valid token still streams 200
            r2 = requests.get(
                f"{API}/analyses/{analysis_id}/video",
                params={"token": COACH_TOKEN},
                timeout=30,
                stream=True,
            )
            assert r2.status_code == 200, f"valid token failed: {r2.status_code} {r2.text[:200]}"
            # confirm bytes returned
            body = r2.content
            assert len(body) > 0
        finally:
            db.user_sessions.delete_many({"session_token": expired_token})
            db.analyses.delete_one({"analysis_id": analysis_id})
            try:
                os.remove(vpath)
            except OSError:
                pass

    def test_missing_token_returns_401(self):
        r = requests.get(f"{API}/analyses/anything/video", timeout=30)
        assert r.status_code == 401
        assert "token" in r.text.lower()


# =========================================================================
# Regressions — chunked flow, finalize validations, /api/plans, / (HTML)
# =========================================================================
class TestRegressions:
    def test_chunked_flow_end_to_end(self):
        _reset_analyses([COACH_USER_ID])
        upload_id = secrets.token_hex(16)
        parts = [
            b"A" * (1 * 1024 * 1024),
            b"B" * (1 * 1024 * 1024),
            b"C" * (1 * 1024 * 1024),
        ]
        for idx, part in enumerate(parts):
            r = requests.post(
                f"{API}/uploads/chunk",
                headers=_auth(COACH_TOKEN),
                data={
                    "upload_id": upload_id,
                    "chunk_index": idx,
                    "total_chunks": 3,
                },
                files={
                    "file": (f"c{idx}.bin", part, "application/octet-stream")
                },
                timeout=60,
            )
            assert r.status_code == 200, r.text
            assert r.json()["received"] == idx + 1

        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_auth(COACH_TOKEN), "Content-Type": "application/json"},
            json={
                "upload_id": upload_id,
                "filename": "clip.mp4",
                "mime_type": "video/mp4",
                "total_chunks": 3,
            },
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "processing"
        aid = body["analysis_id"]
        # chunk docs should be gone
        assert (
            _mongo().upload_chunks.count_documents({"upload_id": upload_id})
            == 0
        )
        _mongo().analyses.delete_one({"analysis_id": aid})
        _cleanup_local_files(COACH_USER_ID)

    def test_finalize_unknown_id_400(self):
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_auth(COACH_TOKEN), "Content-Type": "application/json"},
            json={
                "upload_id": secrets.token_hex(16),
                "filename": "x.mp4",
                "mime_type": "video/mp4",
                "total_chunks": 3,
            },
            timeout=30,
        )
        assert r.status_code == 400, r.text
        assert "upload not found" in r.text.lower()

    def test_finalize_incomplete_400(self):
        upload_id = secrets.token_hex(16)
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_auth(COACH_TOKEN),
            data={
                "upload_id": upload_id,
                "chunk_index": 0,
                "total_chunks": 3,
            },
            files={"file": ("c0.bin", b"AAAA", "application/octet-stream")},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_auth(COACH_TOKEN), "Content-Type": "application/json"},
            json={
                "upload_id": upload_id,
                "filename": "x.mp4",
                "mime_type": "video/mp4",
                "total_chunks": 3,
            },
            timeout=30,
        )
        assert r.status_code == 400, r.text
        assert "incomplete" in r.text.lower()
        _mongo().upload_chunks.delete_many({"upload_id": upload_id})

    def test_plans_200(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), (list, dict))

    def test_root_html_200(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "html" in ct.lower(), ct
