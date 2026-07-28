"""
Iteration 16: Analysis polling / lazy stale watchdog / AI timeout / logout.

Tests focus on:
- BACKEND stale watchdog on GET /api/analyses/{id}
- Regression: ready analysis (ana_ipadshot001), /api/health, chunked upload finalize
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

DEMO_TOKEN = "demo_token_active"          # user_demo_12345 (free)
COACH_TOKEN = "demo_coach_token"          # user_coach_67890 (coach)
DEMO_UID = "user_demo_12345"
COACH_UID = "user_coach_67890"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _mk_analysis_doc(user_id: str, status: str, minutes_old: float, aid: str | None = None) -> dict:
    aid = aid or f"TEST_ana_{uuid.uuid4().hex[:10]}"
    return {
        "analysis_id": aid,
        "user_id": user_id,
        "title": "TEST processing",
        "score": 0,
        "overall_rating": "",
        "summary": "",
        "strengths": [],
        "mistakes": [],
        "corrections": [],
        "tips": [],
        "drills": [],
        "duration_seconds": None,
        "status": status,
        "created_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_old),
    }


# ---------------- Regression: baseline ----------------
class TestBaseline:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200

    def test_ready_seeded_unchanged(self, api):
        r = api.get(
            f"{BASE_URL}/api/analyses/ana_ipadshot001",
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
        )
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "ready"
        assert j["score"] == 78
        assert j["analysis_id"] == "ana_ipadshot001"


# ---------------- Backend stale watchdog ----------------
class TestStaleWatchdog:
    def test_stale_processing_becomes_failed(self, api, db):
        doc = _mk_analysis_doc(COACH_UID, "processing", minutes_old=30)
        db.analyses.insert_one(doc)
        try:
            r = api.get(
                f"{BASE_URL}/api/analyses/{doc['analysis_id']}",
                headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            )
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["status"] == "failed", f"expected failed got {j['status']}"

            # DB should be updated too
            fresh = db.analyses.find_one({"analysis_id": doc["analysis_id"]})
            assert fresh["status"] == "failed"
            err = (fresh.get("error") or "")
            # Must include the "did not use your quota" message
            assert "quota" in err.lower(), f"error text missing quota copy: {err!r}"
        finally:
            db.analyses.delete_one({"analysis_id": doc["analysis_id"]})

    def test_recent_processing_stays_processing(self, api, db):
        doc = _mk_analysis_doc(COACH_UID, "processing", minutes_old=2)
        db.analyses.insert_one(doc)
        try:
            r = api.get(
                f"{BASE_URL}/api/analyses/{doc['analysis_id']}",
                headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            )
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["status"] == "processing", f"expected processing got {j['status']}"

            fresh = db.analyses.find_one({"analysis_id": doc["analysis_id"]})
            assert fresh["status"] == "processing"
        finally:
            db.analyses.delete_one({"analysis_id": doc["analysis_id"]})

    def test_owner_only_access(self, api, db):
        """Coach can't read demo user's analysis unless shared."""
        doc = _mk_analysis_doc(DEMO_UID, "processing", minutes_old=2)
        db.analyses.insert_one(doc)
        try:
            r = api.get(
                f"{BASE_URL}/api/analyses/{doc['analysis_id']}",
                headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            )
            assert r.status_code == 404
        finally:
            db.analyses.delete_one({"analysis_id": doc["analysis_id"]})


# ---------------- Auth / logout regression ----------------
class TestAuthLogout:
    def test_logout_invalidates_session(self, api, db):
        # Create a temporary session so we don't invalidate the shared demo tokens
        tmp_token = f"TEST_tok_{uuid.uuid4().hex[:12]}"
        db.user_sessions.insert_one({
            "user_id": DEMO_UID,
            "session_token": tmp_token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": datetime.now(timezone.utc),
        })
        try:
            # /auth/me works before logout
            r1 = api.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tmp_token}"})
            assert r1.status_code == 200
            # Logout
            r2 = api.post(f"{BASE_URL}/api/auth/logout", headers={"Authorization": f"Bearer {tmp_token}"})
            assert r2.status_code == 200
            assert r2.json() == {"ok": True}
            # /auth/me should now 401 (session removed from DB)
            r3 = api.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tmp_token}"})
            assert r3.status_code == 401
            # Session gone from DB
            assert db.user_sessions.find_one({"session_token": tmp_token}) is None
        finally:
            db.user_sessions.delete_one({"session_token": tmp_token})


# ---------------- Chunked upload finalize regression ----------------
class TestChunkedUploadFinalize:
    def test_finalize_no_chunks_returns_error(self, api):
        """Sanity: /analyses/finalize is reachable and returns non-500 on empty chunk set."""
        r = api.post(
            f"{BASE_URL}/api/analyses/finalize",
            headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            json={
                "upload_id": f"TEST_up_{uuid.uuid4().hex[:8]}",
                "filename": "test.mp4",
                "mime_type": "video/mp4",
                "total_chunks": 1,
            },
        )
        # Expected: 4xx (missing chunks), never 5xx
        assert r.status_code < 500, f"finalize crashed: {r.status_code} {r.text}"
