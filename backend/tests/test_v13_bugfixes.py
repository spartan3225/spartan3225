"""v1.3 SurfCoach23 — CRITICAL BUG FIX verification tests.

Bugs being verified:
  BUG 1: GET /api/analyses/quota for plus user must return tier='plus', limit=3.
  BUG 1b: POST /api/analyses for plus user accepts 3 uploads then 402 on the 4th.
  BUG 2: _apply_subscription_if_paid for plan='plus' must set user.tier='plus'
         (not 'coach') after GET /api/payments/status/{session_id}.

All tests promote demo user to plus, exercise the fix, then RESTORE tier='free'
so future test runs aren't affected.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
FREE_HEADERS = {"Authorization": "Bearer demo_token_active"}
DEMO_USER_ID = "user_demo_12345"

MONGO = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
DB = MONGO[os.environ.get("DB_NAME", "test_database")]

SAMPLE_MP4 = "/tmp/test_surf.mp4"


def _promote_to_plus():
    """Set demo user to plus tier active for 30d, clear today's analyses."""
    DB.users.update_one(
        {"user_id": DEMO_USER_ID},
        {"$set": {
            "tier": "plus",
            "subscription_status": "active",
            "subscription_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        }},
    )
    DB.analyses.delete_many({"user_id": DEMO_USER_ID})


def _restore_to_free():
    DB.users.update_one(
        {"user_id": DEMO_USER_ID},
        {"$set": {
            "tier": "free",
            "subscription_status": None,
            "subscription_expires_at": None,
        }},
    )
    DB.analyses.delete_many({"user_id": DEMO_USER_ID})


@pytest.fixture
def plus_demo_user():
    """Promote demo user to plus, yield, then restore to free."""
    _promote_to_plus()
    yield
    _restore_to_free()


# ---- BUG FIX 1: /api/analyses/quota for plus user ----
class TestQuotaPlusUser:
    def test_quota_plus_user_returns_tier_plus_limit_3(self, plus_demo_user):
        r = requests.get(f"{API}/analyses/quota", headers=FREE_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "plus", f"expected tier=plus, got {data}"
        assert data["limit"] == 3, f"expected limit=3, got {data['limit']}"
        assert data["remaining"] == 3, f"expected remaining=3, got {data['remaining']}"
        assert data["used_today"] == 0, f"expected used_today=0, got {data['used_today']}"


# ---- BUG FIX 1b: POST /api/analyses for plus user 3x then 402 ----
class TestPlusUploadsEnforcement:
    def test_plus_user_can_upload_3_times_then_402_on_4th(self, plus_demo_user):
        # Insert 3 stub analyses directly so we don't burn Gemini quota.
        # The enforcement check counts db.analyses.count_documents on user_id.
        now = datetime.now(timezone.utc)
        for i in range(3):
            DB.analyses.insert_one({
                "analysis_id": f"ana_test_{uuid.uuid4().hex[:10]}",
                "user_id": DEMO_USER_ID,
                "video_path": "/tmp/fake.mp4",
                "mime_type": "video/mp4",
                "created_at": now,
                "status": "complete",
            })

        # quota should now show 3 used, 0 remaining
        r = requests.get(f"{API}/analyses/quota", headers=FREE_HEADERS, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "plus"
        assert data["limit"] == 3
        assert data["used_today"] == 3
        assert data["remaining"] == 0

        # 4th upload should be rejected with 402
        with open(SAMPLE_MP4, "rb") as f:
            r = requests.post(
                f"{API}/analyses",
                headers=FREE_HEADERS,
                files={"file": ("surf.mp4", f, "video/mp4")},
                timeout=30,
            )
        assert r.status_code == 402, f"expected 402, got {r.status_code} body={r.text}"
        body = r.json()
        # Error message should mention the Plus limit
        detail = (body.get("detail") or "").lower()
        assert "3" in detail or "plus" in detail, f"unexpected 402 detail: {body}"

    def test_plus_user_first_upload_does_not_402(self, plus_demo_user):
        """Smoke check: with 0 used, an upload attempt is NOT blocked at the
        quota gate. (We don't wait for Gemini; we only confirm status != 402.)"""
        with open(SAMPLE_MP4, "rb") as f:
            r = requests.post(
                f"{API}/analyses",
                headers=FREE_HEADERS,
                files={"file": ("surf.mp4", f, "video/mp4")},
                timeout=120,
            )
        assert r.status_code != 402, (
            f"plus user with 0 used was blocked at quota: {r.status_code} {r.text[:300]}"
        )


# ---- BUG FIX 2: _apply_subscription_if_paid sets tier=plan_id ----
class TestApplySubscriptionPlusPlan:
    def test_paid_plus_checkout_sets_user_tier_plus(self):
        """Insert a fake-paid plus payment_transactions row, hit the status
        endpoint, then verify user.tier == 'plus' (NOT 'coach')."""
        # Make sure user starts as free
        _restore_to_free()

        session_id = f"cs_test_plus_{uuid.uuid4().hex[:16]}"
        DB.payment_transactions.delete_many({"session_id": session_id})
        DB.payment_transactions.insert_one({
            "session_id": session_id,
            "user_id": DEMO_USER_ID,
            "plan_id": "plus",
            "amount": 9.99,
            "currency": "usd",
            "payment_status": "paid",
            "status": "complete",
            "applied": False,
            "created_at": datetime.now(timezone.utc),
            "metadata": {},
        })

        try:
            r = requests.get(
                f"{API}/payments/status/{session_id}",
                headers=FREE_HEADERS,
                timeout=20,
            )
            # 200 expected even if Stripe lookup degrades gracefully
            assert r.status_code == 200, r.text

            # Allow async write to settle
            time.sleep(0.5)

            user = DB.users.find_one({"user_id": DEMO_USER_ID}, {"_id": 0})
            assert user is not None
            assert user.get("tier") == "plus", (
                f"expected tier=plus after paid plus checkout, got tier={user.get('tier')}"
            )
            assert user.get("subscription_status") == "active"

            txn = DB.payment_transactions.find_one(
                {"session_id": session_id}, {"_id": 0}
            )
            assert txn.get("applied") is True, "txn.applied should be True"
        finally:
            DB.payment_transactions.delete_many({"session_id": session_id})
            _restore_to_free()

    def test_paid_coach_checkout_still_sets_user_tier_coach(self):
        """Regression: ensure the fix didn't break coach plan activation."""
        _restore_to_free()

        session_id = f"cs_test_coach_{uuid.uuid4().hex[:16]}"
        DB.payment_transactions.delete_many({"session_id": session_id})
        DB.payment_transactions.insert_one({
            "session_id": session_id,
            "user_id": DEMO_USER_ID,
            "plan_id": "coach",
            "amount": 120.0,
            "currency": "usd",
            "payment_status": "paid",
            "status": "complete",
            "applied": False,
            "created_at": datetime.now(timezone.utc),
            "metadata": {},
        })

        try:
            r = requests.get(
                f"{API}/payments/status/{session_id}",
                headers=FREE_HEADERS,
                timeout=20,
            )
            assert r.status_code == 200, r.text
            time.sleep(0.5)

            user = DB.users.find_one({"user_id": DEMO_USER_ID}, {"_id": 0})
            assert user.get("tier") == "coach", (
                f"expected tier=coach, got tier={user.get('tier')}"
            )
        finally:
            DB.payment_transactions.delete_many({"session_id": session_id})
            _restore_to_free()
