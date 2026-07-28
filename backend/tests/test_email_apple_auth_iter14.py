"""
Iteration 14 — Email/password + Apple auth backend tests.

Covers:
  - POST /api/auth/register success -> 200 + AuthResponse + session works on /auth/me
  - POST /api/auth/register duplicate -> 409
  - POST /api/auth/register password too short -> 422
  - POST /api/auth/register linking a Google-only account (no password_hash) -> same user_id, no dup
  - POST /api/auth/login correct -> 200
  - POST /api/auth/login wrong password -> 401 generic
  - POST /api/auth/login unknown email -> 401
  - POST /api/auth/apple garbage token -> 401
  - Session-token from /auth/register works on GET /api/analyses and /api/analyses/quota

Cleanup: removes all TEST_ created users EXCEPT the persisted qa.tester@surfcoach23.com.
"""

import os
import uuid
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

QA_EMAIL = "qa.tester@surfcoach23.com"
QA_PASSWORD = "TestPass123!"

_created_emails: list[str] = []


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_users(db):
    yield
    # Cleanup: everything we made in this run, except qa.tester (kept for future runs)
    keep = {QA_EMAIL}
    to_delete = [e for e in _created_emails if e not in keep]
    if to_delete:
        users = list(db.users.find({"email": {"$in": to_delete}}, {"user_id": 1, "_id": 0}))
        uids = [u["user_id"] for u in users]
        db.users.delete_many({"email": {"$in": to_delete}})
        if uids:
            db.user_sessions.delete_many({"user_id": {"$in": uids}})


def _mkemail(tag: str) -> str:
    e = f"test_{tag}_{uuid.uuid4().hex[:8]}@surfcoach23qa.com"
    _created_emails.append(e)
    return e


# ---------- REGISTER ----------

class TestRegister:
    def test_register_success(self):
        email = _mkemail("reg")
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Password123!", "name": "Reg User"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "session_token" in data and data["session_token"]
        assert "user" in data
        assert data["user"]["email"] == email
        assert data["user"].get("tier") == "free"
        # session works on /auth/me
        me = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {data['session_token']}"},
            timeout=15,
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email

    def test_register_duplicate_returns_409(self):
        email = _mkemail("dup")
        r1 = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Password123!"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text
        r2 = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Password123!"},
            timeout=30,
        )
        assert r2.status_code == 409, r2.text

    def test_register_short_password_returns_422(self):
        email = _mkemail("short")
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "short7!"},  # 7 chars
            timeout=15,
        )
        assert r.status_code == 422, r.text

    def test_register_links_google_only_account(self, db):
        # Simulate a Google-only account already existing (no password_hash)
        email = _mkemail("link")
        pre_uid = f"user_google_{uuid.uuid4().hex[:8]}"
        db.users.insert_one(
            {
                "user_id": pre_uid,
                "email": email,
                "name": "Google User",
                "picture": None,
                "created_at": datetime.now(timezone.utc),
                "tier": "free",
                "subscription_status": None,
                "subscription_expires_at": None,
                "coach_bio": None,
                "coach_specialty": None,
                "coach_location": None,
                "coach_public": False,
            }
        )
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Password123!"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        # SAME user_id (linked, not duplicated)
        assert r.json()["user"]["user_id"] == pre_uid
        count = db.users.count_documents({"email": email})
        assert count == 1, f"expected 1 doc, got {count} — duplicate created"
        # password_hash now set
        doc = db.users.find_one({"user_id": pre_uid})
        assert doc.get("password_hash"), "password_hash should be linked to existing user"


# ---------- LOGIN ----------

class TestLogin:
    @pytest.fixture(scope="class")
    def qa_user_token(self):
        """Ensure the persisted QA user exists (register or login), return token."""
        _created_emails.append(QA_EMAIL)  # so we don't add extra; kept anyway
        r = requests.post(
            f"{API}/auth/register",
            json={"email": QA_EMAIL, "password": QA_PASSWORD, "name": "QA Tester"},
            timeout=30,
        )
        if r.status_code == 409:
            r = requests.post(
                f"{API}/auth/login",
                json={"email": QA_EMAIL, "password": QA_PASSWORD},
                timeout=30,
            )
        assert r.status_code == 200, r.text
        return r.json()["session_token"]

    def test_login_correct(self, qa_user_token):
        assert qa_user_token
        r = requests.post(
            f"{API}/auth/login",
            json={"email": QA_EMAIL, "password": QA_PASSWORD},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == QA_EMAIL

    def test_login_wrong_password_401(self, qa_user_token):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": QA_EMAIL, "password": "WrongPassword!!"},
            timeout=15,
        )
        assert r.status_code == 401, r.text
        # Generic message (should NOT reveal whether email exists)
        detail = r.json().get("detail", "").lower()
        assert "invalid" in detail or "incorrect" in detail

    def test_login_unknown_email_401(self):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": f"nonexistent_{uuid.uuid4().hex[:8]}@surfcoach23qa.com", "password": "whatever123"},
            timeout=15,
        )
        assert r.status_code == 401, r.text


# ---------- APPLE ----------

class TestApple:
    def test_apple_garbage_token_401(self):
        r = requests.post(
            f"{API}/auth/apple",
            json={"identity_token": "not-a-real-jwt.garbage.value"},
            timeout=30,
        )
        assert r.status_code == 401, r.text


# ---------- SESSION COMPAT ----------

class TestSessionCompatibility:
    def test_email_session_works_on_analyses_endpoints(self):
        email = _mkemail("sess")
        r = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": "Password123!", "name": "Sess User"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        tok = r.json()["session_token"]
        hdr = {"Authorization": f"Bearer {tok}"}

        r1 = requests.get(f"{API}/analyses", headers=hdr, timeout=15)
        assert r1.status_code == 200, r1.text
        assert isinstance(r1.json(), list)

        r2 = requests.get(f"{API}/analyses/quota", headers=hdr, timeout=15)
        assert r2.status_code == 200, r2.text
        data = r2.json()
        # Basic shape check — should include some quota fields
        assert isinstance(data, dict)
