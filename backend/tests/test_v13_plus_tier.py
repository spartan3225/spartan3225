"""v1.3 SurfCoach23 — Plus tier ($9.99/mo, 3 analyses/day) and rebrand tests.

Coverage:
- /api/plans returns 3 plans with proper amounts and daily_limit fields
- /api/analyses/quota for free + coach
- /api/payments/checkout for plus / coach / unknown plans
- payment_transactions persistence
"""
import os
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or
            "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
FREE_HEADERS = {"Authorization": "Bearer demo_token_active"}
COACH_HEADERS = {"Authorization": "Bearer demo_coach_token"}
ORIGIN = "https://wave-motion-ai.preview.emergentagent.com"

MONGO = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
DB = MONGO[os.environ.get("DB_NAME", "test_database")]


# ---- /api/plans ----
class TestPlans:
    def test_plans_returns_3_plans_with_correct_ids(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200, r.text
        plans = r.json()["plans"]
        ids = [p["plan_id"] for p in plans]
        assert ids == ["free", "plus", "coach"], f"got {ids}"

    def test_free_plan_amount_and_limit(self):
        plans = requests.get(f"{API}/plans", timeout=15).json()["plans"]
        free = next(p for p in plans if p["plan_id"] == "free")
        assert free["amount"] == 0.0
        assert free["daily_limit"] == 1

    def test_plus_plan_amount_999_and_limit_3(self):
        plans = requests.get(f"{API}/plans", timeout=15).json()["plans"]
        plus = next(p for p in plans if p["plan_id"] == "plus")
        assert plus["amount"] == 9.99, f"plus.amount={plus['amount']}"
        assert plus["daily_limit"] == 3, f"plus.daily_limit={plus['daily_limit']}"
        assert plus["currency"] == "usd"

    def test_coach_plan_amount_120_and_unlimited(self):
        plans = requests.get(f"{API}/plans", timeout=15).json()["plans"]
        coach = next(p for p in plans if p["plan_id"] == "coach")
        assert coach["amount"] == 120.0
        assert coach["daily_limit"] == -1


# ---- /api/analyses/quota ----
class TestQuota:
    def test_quota_free_user(self):
        r = requests.get(f"{API}/analyses/quota", headers=FREE_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "free"
        assert data["limit"] == 1
        assert "remaining" in data
        assert "used_today" in data

    def test_quota_coach_user_unlimited(self):
        r = requests.get(f"{API}/analyses/quota", headers=COACH_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "coach"
        assert data["limit"] == -1
        assert data["remaining"] == -1


# ---- /api/payments/checkout ----
class TestCheckoutPlus:
    def test_checkout_plus_creates_stripe_session(self):
        r = requests.post(
            f"{API}/payments/checkout",
            headers=FREE_HEADERS,
            json={"plan_id": "plus", "origin_url": ORIGIN},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        assert "stripe.com" in data["url"], f"url={data['url']}"

        # verify DB persistence
        txn = DB.payment_transactions.find_one({"session_id": data["session_id"]})
        assert txn is not None, "payment_transactions row missing"
        assert txn["plan_id"] == "plus"
        assert txn["amount"] == 9.99
        assert txn["user_id"] == "user_demo_12345"
        assert txn["payment_status"] == "initiated"

    def test_checkout_coach_still_works_120(self):
        r = requests.post(
            f"{API}/payments/checkout",
            headers=FREE_HEADERS,
            json={"plan_id": "coach", "origin_url": ORIGIN},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "stripe.com" in data["url"]
        txn = DB.payment_transactions.find_one({"session_id": data["session_id"]})
        assert txn["plan_id"] == "coach"
        assert txn["amount"] == 120.0

    def test_checkout_invalid_plan_400(self):
        r = requests.post(
            f"{API}/payments/checkout",
            headers=FREE_HEADERS,
            json={"plan_id": "unknown", "origin_url": ORIGIN},
            timeout=15,
        )
        assert r.status_code == 400, r.text


# ---- regression smoke ----
class TestRegression:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=15)
        assert r.status_code == 200

    def test_auth_me_free(self):
        r = requests.get(f"{API}/auth/me", headers=FREE_HEADERS, timeout=15)
        assert r.status_code == 200
        assert r.json()["tier"] == "free"

    def test_auth_me_coach(self):
        r = requests.get(f"{API}/auth/me", headers=COACH_HEADERS, timeout=15)
        assert r.status_code == 200
        assert r.json()["tier"] == "coach"

    def test_coaches_directory_lists_demo_coach(self):
        r = requests.get(f"{API}/coaches", timeout=15)
        assert r.status_code == 200
        ids = [c["user_id"] for c in r.json()]
        assert "user_coach_67890" in ids
