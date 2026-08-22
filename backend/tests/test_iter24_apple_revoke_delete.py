"""
Iteration 24 backend tests
---------------------------
Focus: Apple Sign-in token revocation on account deletion (Guideline 5.1.1(v))
and the new `authorization_code` field on POST /api/auth/apple.

Notes:
- APPLE_TEAM_ID / APPLE_KEY_ID / APPLE_PRIVATE_KEY are intentionally NOT set,
  so _apple_revoke_refresh_token must skip gracefully (no 500 on delete).
- We seed users + sessions directly in Mongo to avoid depending on live Apple.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
if not BASE_URL:
    # Fallback: read frontend/.env directly
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass
assert BASE_URL, "EXPO_BACKEND_URL not configured"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def seeded_apple_user(db):
    """Create a user with apple_sub + apple_refresh_token + a session."""
    uid = f"user_TESTAPPLE_{uuid.uuid4().hex[:8]}"
    token = f"TESTAPPLE_sess_{uuid.uuid4().hex[:10]}"
    db.users.insert_one({
        "user_id": uid,
        "email": f"TEST_{uid}@surfcoach23.test",
        "name": "TEST Apple User",
        "picture": None,
        "apple_sub": f"apple.{uid}",
        "apple_refresh_token": "fake_rt_TEST",
        "created_at": datetime.now(timezone.utc),
        "tier": "free",
        "subscription_status": None,
        "subscription_expires_at": None,
        "coach_bio": None,
        "coach_specialty": None,
        "coach_location": None,
        "coach_public": False,
    })
    db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    # A dummy analysis to check the cascade deletion
    aid = f"ana_TEST_{uuid.uuid4().hex[:10]}"
    db.analyses.insert_one({
        "analysis_id": aid,
        "user_id": uid,
        "status": "ready",
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": uid, "token": token, "analysis_id": aid}
    # Belt-and-suspenders cleanup (delete_account should already have wiped these)
    db.users.delete_one({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})
    db.analyses.delete_many({"user_id": uid})


# ---------- Tests: DELETE /api/auth/account ----------

class TestDeleteAccountAppleRevoke:
    """DELETE /api/auth/account with apple_refresh_token — must NOT 500 when
    APPLE_TEAM_ID/KEY_ID/PRIVATE_KEY are unset (graceful skip)."""

    def test_delete_returns_ok_true(self, http, seeded_apple_user):
        r = http.delete(
            f"{API}/auth/account",
            headers={"Authorization": f"Bearer {seeded_apple_user['token']}"},
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body == {"ok": True}, f"unexpected body: {body}"

    def test_delete_removes_user_sessions_and_analyses(self, http, db, seeded_apple_user):
        # Delete
        r = http.delete(
            f"{API}/auth/account",
            headers={"Authorization": f"Bearer {seeded_apple_user['token']}"},
        )
        assert r.status_code == 200

        uid = seeded_apple_user["user_id"]
        assert db.users.find_one({"user_id": uid}) is None, "user record must be removed"
        assert db.user_sessions.count_documents({"user_id": uid}) == 0, "sessions must be removed"
        assert db.analyses.count_documents({"user_id": uid}) == 0, "analyses must be removed"

    def test_delete_session_no_longer_usable(self, http, seeded_apple_user):
        r = http.delete(
            f"{API}/auth/account",
            headers={"Authorization": f"Bearer {seeded_apple_user['token']}"},
        )
        assert r.status_code == 200
        # Subsequent /auth/me with the same token must be 401
        me = http.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {seeded_apple_user['token']}"},
        )
        assert me.status_code == 401, f"expected 401 after deletion, got {me.status_code}"


# ---------- Tests: POST /api/auth/apple (authorization_code field) ----------

class TestAppleLoginAuthorizationCodeField:
    """New optional `authorization_code` on POST /api/auth/apple must not crash
    the endpoint. Invalid identity_token must still return 401."""

    def test_apple_invalid_token_returns_401(self, http):
        r = http.post(
            f"{API}/auth/apple",
            json={"identity_token": "definitely.not.a.valid.jwt"},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"
        assert "Apple" in r.text or "Invalid" in r.text

    def test_apple_invalid_token_with_authorization_code_still_401(self, http):
        """The NEW authorization_code field must be accepted (no 422) but the
        invalid identity_token should still trigger 401 — not 500."""
        r = http.post(
            f"{API}/auth/apple",
            json={
                "identity_token": "definitely.not.a.valid.jwt",
                "authorization_code": "c.fake_authorization_code",
                "email": "TEST_authcode@surfcoach23.test",
                "name": "TEST Apple AuthCode",
            },
        )
        assert r.status_code == 401, (
            f"expected 401 (invalid token), got {r.status_code}: {r.text[:200]}"
        )

    def test_apple_missing_identity_token_is_422(self, http):
        r = http.post(f"{API}/auth/apple", json={"authorization_code": "c.abc"})
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"


# ---------- Regression: /api/auth/logout + /api/auth/me still work ----------

class TestAuthRegression:
    """Regression against the pre-seeded demo tokens from test_credentials.md."""

    DEMO_TOKEN = "demo_token_active"

    def test_me_with_demo_token(self, http):
        r = http.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {self.DEMO_TOKEN}"})
        # If seed was wiped, this can be 401 — skip in that case rather than fail
        if r.status_code == 401:
            pytest.skip("demo_token_active not seeded on this deploy")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("user_id") == "user_demo_12345"
        assert body.get("email") == "demo@surfai.test"

    def test_logout_endpoint_returns_ok(self, http, db):
        # Seed a throwaway session so we don't kill demo_token_active
        uid = "user_demo_12345"
        throwaway = f"TEST_logout_{uuid.uuid4().hex[:10]}"
        db.user_sessions.insert_one({
            "user_id": uid,
            "session_token": throwaway,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": datetime.now(timezone.utc),
        })
        try:
            r = http.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {throwaway}"})
            assert r.status_code == 200
            assert r.json() == {"ok": True}
            # Session must be gone
            assert db.user_sessions.find_one({"session_token": throwaway}) is None
        finally:
            db.user_sessions.delete_one({"session_token": throwaway})

    def test_logout_no_auth_still_ok(self, http):
        r = http.post(f"{API}/auth/logout")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
