"""
Stripe LIVE-key webhook signature verification + tier upgrade tests.

Covers:
- Backend reads STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY / STRIPE_WEBHOOK_SECRET
- POST /api/payments/checkout returns cs_live_... session URL for plus & coach
- payment_transactions document inserted with correct amount
- POST /api/webhook/stripe rejects: missing sig (400), bogus sig (400)
- POST /api/webhook/stripe with VALID HMAC sig → 200 + tier upgraded to plan_id,
  subscription_status='active', subscription_expires_at ~ now+30d
- Idempotent replay: expiry NOT extended a 2nd time
- async_payment_succeeded event also applies tier
- GET /api/payments/status/{cs_id} does not 500 even when Stripe retrieve fails
"""

import os
import time
import json
import hmac
import hashlib
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

# Load backend env so we can read STRIPE_WEBHOOK_SECRET / MONGO_URL the same
# way the running server does.
load_dotenv("/app/backend/.env")

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
DEMO_TOKEN = "demo_token_active"
DEMO_USER_ID = "user_demo_12345"
DEMO_EMAIL = "demo@surfai.test"

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture
def reset_demo_user(db):
    """Ensure demo user is free with no subscription before each test."""
    db.users.update_one(
        {"user_id": DEMO_USER_ID},
        {
            "$set": {
                "tier": "free",
                "subscription_status": None,
                "subscription_expires_at": None,
                "cancel_at_period_end": False,
            }
        },
    )
    yield
    # Always restore at end too.
    db.users.update_one(
        {"user_id": DEMO_USER_ID},
        {
            "$set": {
                "tier": "free",
                "subscription_status": None,
                "subscription_expires_at": None,
                "cancel_at_period_end": False,
            }
        },
    )


def _sign(payload_bytes: bytes, secret: str, ts: int | None = None) -> str:
    if ts is None:
        ts = int(time.time())
    signed_payload = f"{ts}.{payload_bytes.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _make_event(session_id: str, event_type: str = "checkout.session.completed") -> bytes:
    event = {
        "id": f"evt_test_{uuid.uuid4().hex[:14]}",
        "object": "event",
        "api_version": "2024-06-20",
        "created": int(time.time()),
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_status": "paid",
                "status": "complete",
                "mode": "payment",
            }
        },
        "livemode": True,
    }
    return json.dumps(event, separators=(",", ":")).encode()


def _seed_paid_txn(db, plan_id: str, session_id: str | None = None) -> str:
    """Create a payment_transactions row in 'paid' state ready for tier upgrade."""
    if session_id is None:
        session_id = f"cs_live_test_{uuid.uuid4().hex[:18]}"
    # Remove any prior row so test is deterministic.
    db.payment_transactions.delete_one({"session_id": session_id})
    db.payment_transactions.insert_one(
        {
            "session_id": session_id,
            "user_id": DEMO_USER_ID,
            "email": DEMO_EMAIL,
            "plan_id": plan_id,
            "amount": 9.99 if plan_id == "plus" else 120.00,
            "currency": "usd",
            "metadata": {
                "user_id": DEMO_USER_ID,
                "email": DEMO_EMAIL,
                "plan_id": plan_id,
            },
            # IMPORTANT: payment_status='paid' so when stripe.Session.retrieve
            # fails for our synthetic id, the handler falls back to DB state and
            # still applies tier upgrade — which is the path under test.
            "payment_status": "paid",
            "status": "complete",
            "applied": False,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return session_id


# --------------------------------------------------------------------------
# 1. Env config sanity
# --------------------------------------------------------------------------
class TestStripeEnvLoaded:
    def test_secret_is_live(self):
        assert STRIPE_SECRET_KEY.startswith("sk_live_"), "Expected sk_live_ key in /app/backend/.env"

    def test_publishable_is_live(self):
        assert STRIPE_PUBLISHABLE_KEY.startswith("pk_live_")

    def test_webhook_secret_present(self):
        assert STRIPE_WEBHOOK_SECRET.startswith("whsec_")
        # Specific value the main agent committed (no secret leak — already in repo .env)
        assert STRIPE_WEBHOOK_SECRET == "whsec_dbOTqdehRItlzN4NdjAxiAIQP7v36nuG"


# --------------------------------------------------------------------------
# 2. Live checkout session creation (Plus & Coach)
# --------------------------------------------------------------------------
class TestLiveCheckoutCreation:
    def _create(self, plan_id: str):
        r = requests.post(
            f"{API}/payments/checkout",
            json={"plan_id": plan_id, "origin_url": "https://wave-motion-ai.preview.emergentagent.com"},
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
            timeout=30,
        )
        return r

    def test_checkout_plus_returns_live_url(self, db):
        r = self._create("plus")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "session_id" in data
        # Live mode session URLs use checkout.stripe.com; ids are cs_live_…
        assert data["session_id"].startswith("cs_live_"), f"got {data['session_id']}"
        assert "checkout.stripe.com" in data["url"]

        txn = db.payment_transactions.find_one({"session_id": data["session_id"]})
        assert txn is not None, "payment_transactions doc not inserted"
        assert txn["user_id"] == DEMO_USER_ID
        assert txn["plan_id"] == "plus"
        assert abs(txn["amount"] - 9.99) < 0.001
        assert txn["currency"] == "usd"
        assert txn.get("applied") is False
        # cleanup
        db.payment_transactions.delete_one({"session_id": data["session_id"]})

    def test_checkout_coach_returns_live_url_amount_120(self, db):
        r = self._create("coach")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["session_id"].startswith("cs_live_")
        txn = db.payment_transactions.find_one({"session_id": data["session_id"]})
        assert txn is not None
        assert txn["plan_id"] == "coach"
        assert abs(txn["amount"] - 120.00) < 0.001
        db.payment_transactions.delete_one({"session_id": data["session_id"]})

    def test_checkout_invalid_plan(self):
        r = requests.post(
            f"{API}/payments/checkout",
            json={"plan_id": "ultra", "origin_url": "https://example.com"},
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
            timeout=15,
        )
        assert r.status_code == 400


# --------------------------------------------------------------------------
# 3. Webhook signature rejection
# --------------------------------------------------------------------------
class TestWebhookSignatureRejection:
    def test_missing_signature_400(self):
        r = requests.post(
            f"{API}/webhook/stripe",
            data=b'{"id":"evt_x","type":"checkout.session.completed","data":{"object":{"id":"cs_x"}}}',
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "signature" in r.text.lower() or "invalid" in r.text.lower()

    def test_bogus_signature_400(self):
        body = b'{"id":"evt_x","type":"checkout.session.completed","data":{"object":{"id":"cs_x"}}}'
        r = requests.post(
            f"{API}/webhook/stripe",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=1700000000,v1=deadbeef",
            },
            timeout=15,
        )
        assert r.status_code == 400

    def test_valid_signature_unknown_event_type_returns_200(self):
        """Sanity: signature path works for an event type the server ignores."""
        body = json.dumps(
            {
                "id": f"evt_ignored_{uuid.uuid4().hex[:8]}",
                "object": "event",
                "type": "customer.created",
                "api_version": "2024-06-20",
                "created": int(time.time()),
                "livemode": True,
                "data": {"object": {"id": "cus_xxx", "object": "customer"}},
            },
            separators=(",", ":"),
        ).encode()
        sig = _sign(body, STRIPE_WEBHOOK_SECRET)
        r = requests.post(
            f"{API}/webhook/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("type") == "customer.created"


# --------------------------------------------------------------------------
# 4. Webhook tier upgrade (checkout.session.completed)
# --------------------------------------------------------------------------
class TestWebhookTierUpgrade:
    def test_completed_event_upgrades_to_plus(self, db, reset_demo_user):
        session_id = _seed_paid_txn(db, "plus")
        body = _make_event(session_id, "checkout.session.completed")
        sig = _sign(body, STRIPE_WEBHOOK_SECRET)

        r = requests.post(
            f"{API}/webhook/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
            timeout=20,
        )
        assert r.status_code == 200, r.text

        user = db.users.find_one({"user_id": DEMO_USER_ID})
        assert user["tier"] == "plus", f"tier={user.get('tier')}"
        assert user["subscription_status"] == "active"
        exp = user["subscription_expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta = exp - datetime.now(timezone.utc)
        # Expiry should be ~30d from now (allow ±1 day jitter)
        assert timedelta(days=29) <= delta <= timedelta(days=31), f"delta={delta}"

        txn = db.payment_transactions.find_one({"session_id": session_id})
        assert txn.get("applied") is True
        db.payment_transactions.delete_one({"session_id": session_id})

    def test_completed_event_upgrades_to_coach(self, db, reset_demo_user):
        session_id = _seed_paid_txn(db, "coach")
        body = _make_event(session_id, "checkout.session.completed")
        sig = _sign(body, STRIPE_WEBHOOK_SECRET)

        r = requests.post(
            f"{API}/webhook/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
            timeout=20,
        )
        assert r.status_code == 200

        user = db.users.find_one({"user_id": DEMO_USER_ID})
        assert user["tier"] == "coach"
        assert user["subscription_status"] == "active"
        db.payment_transactions.delete_one({"session_id": session_id})

    def test_async_payment_succeeded_also_applies(self, db, reset_demo_user):
        session_id = _seed_paid_txn(db, "plus")
        body = _make_event(session_id, "checkout.session.async_payment_succeeded")
        sig = _sign(body, STRIPE_WEBHOOK_SECRET)

        r = requests.post(
            f"{API}/webhook/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig},
            timeout=20,
        )
        assert r.status_code == 200
        user = db.users.find_one({"user_id": DEMO_USER_ID})
        assert user["tier"] == "plus"
        assert user["subscription_status"] == "active"
        db.payment_transactions.delete_one({"session_id": session_id})


# --------------------------------------------------------------------------
# 5. Idempotency
# --------------------------------------------------------------------------
class TestWebhookIdempotency:
    def test_replay_does_not_double_extend_expiry(self, db, reset_demo_user):
        session_id = _seed_paid_txn(db, "plus")
        body = _make_event(session_id, "checkout.session.completed")
        sig = _sign(body, STRIPE_WEBHOOK_SECRET)
        headers = {"Content-Type": "application/json", "Stripe-Signature": sig}

        r1 = requests.post(f"{API}/webhook/stripe", data=body, headers=headers, timeout=20)
        assert r1.status_code == 200
        user1 = db.users.find_one({"user_id": DEMO_USER_ID})
        exp1 = user1["subscription_expires_at"]
        if exp1.tzinfo is None:
            exp1 = exp1.replace(tzinfo=timezone.utc)

        # Replay
        time.sleep(1)
        # Re-sign with fresh timestamp so it's not a tolerance issue.
        sig2 = _sign(body, STRIPE_WEBHOOK_SECRET)
        headers2 = {"Content-Type": "application/json", "Stripe-Signature": sig2}
        r2 = requests.post(f"{API}/webhook/stripe", data=body, headers=headers2, timeout=20)
        assert r2.status_code == 200

        user2 = db.users.find_one({"user_id": DEMO_USER_ID})
        exp2 = user2["subscription_expires_at"]
        if exp2.tzinfo is None:
            exp2 = exp2.replace(tzinfo=timezone.utc)

        # Idempotent: expiry must NOT be extended on replay.
        # Allow microsecond equality.
        assert exp2 == exp1, f"exp1={exp1} exp2={exp2} — webhook is NOT idempotent"
        db.payment_transactions.delete_one({"session_id": session_id})


# --------------------------------------------------------------------------
# 6. /api/payments/status graceful degrade
# --------------------------------------------------------------------------
class TestPaymentStatusGraceful:
    def test_status_does_not_500_for_synthetic_session(self, db, reset_demo_user):
        # Insert a row that is 'initiated' (NOT paid) so retrieve fail leaves it unpaid.
        session_id = f"cs_live_synthetic_{uuid.uuid4().hex[:14]}"
        db.payment_transactions.insert_one(
            {
                "session_id": session_id,
                "user_id": DEMO_USER_ID,
                "email": DEMO_EMAIL,
                "plan_id": "plus",
                "amount": 9.99,
                "currency": "usd",
                "metadata": {"user_id": DEMO_USER_ID, "plan_id": "plus"},
                "payment_status": "initiated",
                "status": "open",
                "applied": False,
                "created_at": datetime.now(timezone.utc),
            }
        )
        r = requests.get(
            f"{API}/payments/status/{session_id}",
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["session_id"] == session_id
        assert data["plan_id"] == "plus"
        # Stripe retrieve will fail → fall back to DB state; remains unpaid.
        assert data["payment_status"] in ("initiated", "unpaid")
        assert data["tier"] is None
        db.payment_transactions.delete_one({"session_id": session_id})


# --------------------------------------------------------------------------
# 7. Light regression on previously-tested endpoints (no full re-run)
# --------------------------------------------------------------------------
class TestRegressionLight:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200

    def test_auth_me_demo(self):
        r = requests.get(
            f"{API}/auth/me", headers={"Authorization": f"Bearer {DEMO_TOKEN}"}, timeout=10
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == DEMO_USER_ID

    def test_quota_free(self, reset_demo_user):
        r = requests.get(
            f"{API}/analyses/quota",
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
            timeout=10,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "free"
        assert d["limit"] == 1

    def test_coaches_directory(self):
        r = requests.get(f"{API}/coaches", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_plans(self):
        r = requests.get(f"{API}/plans", timeout=10)
        assert r.status_code == 200
        ids = [p["plan_id"] for p in r.json()["plans"]]
        assert "plus" in ids and "coach" in ids
