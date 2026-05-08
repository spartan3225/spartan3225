"""SurfAI v1.2 tests:
   - PUT /api/users/push-token (set + clear)
   - POST /api/payments/cancel-renewal & resume-renewal
   - GET /api/coaches?q=&location=&specialty= filtering
"""
import os
import pytest


BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
FREE_TOKEN = "demo_token_active"
COACH_TOKEN = "demo_coach_token"
COACH_USER_ID = "user_coach_67890"


@pytest.fixture
def free_h():
    return {"Authorization": f"Bearer {FREE_TOKEN}"}


@pytest.fixture
def coach_h():
    return {"Authorization": f"Bearer {COACH_TOKEN}"}


# ---------- Push token ----------
class TestPushToken:
    def test_set_push_token(self, client, free_h):
        r = client.put(f"{API}/users/push-token", headers=free_h,
                       json={"token": "ExponentPushToken[FAKE_TEST_AAAA]"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["expo_push_token"] == "ExponentPushToken[FAKE_TEST_AAAA]"

    def test_get_me_reflects_token(self, client, free_h):
        r = client.get(f"{API}/auth/me", headers=free_h, timeout=15)
        assert r.status_code == 200
        assert r.json().get("expo_push_token") == "ExponentPushToken[FAKE_TEST_AAAA]"

    def test_clear_push_token_with_null(self, client, free_h):
        r = client.put(f"{API}/users/push-token", headers=free_h,
                       json={"token": None}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("expo_push_token") in (None, "")

    def test_push_token_unauthorized(self, client):
        r = client.put(f"{API}/users/push-token",
                       json={"token": "x"}, timeout=15)
        assert r.status_code == 401


# ---------- Cancel / Resume renewal ----------
class TestSubscriptionRenewal:
    def test_cancel_renewal_free_returns_400(self, client, free_h):
        r = client.post(f"{API}/payments/cancel-renewal", headers=free_h, timeout=15)
        assert r.status_code == 400

    def test_resume_renewal_free_returns_400(self, client, free_h):
        r = client.post(f"{API}/payments/resume-renewal", headers=free_h, timeout=15)
        assert r.status_code == 400

    def test_cancel_renewal_as_coach(self, client, coach_h):
        r = client.post(f"{API}/payments/cancel-renewal", headers=coach_h, timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["cancel_at_period_end"] is True

        # Verify auth/me reflects update; tier still 'coach' until expiry
        rm = client.get(f"{API}/auth/me", headers=coach_h, timeout=15)
        assert rm.status_code == 200
        me = rm.json()
        assert me["tier"] == "coach"
        assert me["cancel_at_period_end"] is True
        assert me["subscription_status"] == "canceled"

    def test_resume_renewal_as_coach(self, client, coach_h):
        r = client.post(f"{API}/payments/resume-renewal", headers=coach_h, timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["cancel_at_period_end"] is False

        rm = client.get(f"{API}/auth/me", headers=coach_h, timeout=15)
        assert rm.status_code == 200
        me = rm.json()
        assert me["tier"] == "coach"
        assert me["cancel_at_period_end"] is False
        assert me["subscription_status"] == "active"


# ---------- Coach directory filters ----------
class TestCoachDirectoryFilters:
    def test_no_filter_returns_demo(self, client):
        r = client.get(f"{API}/coaches", timeout=15)
        assert r.status_code == 200
        ids = [c["user_id"] for c in r.json()]
        assert COACH_USER_ID in ids

    def test_location_match(self, client):
        r = client.get(f"{API}/coaches", params={"location": "Eric"}, timeout=15)
        assert r.status_code == 200
        coaches = r.json()
        assert any(c["user_id"] == COACH_USER_ID for c in coaches), \
            f"Expected demo coach for location=Eric, got {coaches}"

    def test_location_miss(self, client):
        r = client.get(f"{API}/coaches", params={"location": "XYZNoSuchPlace"}, timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_specialty_match(self, client):
        r = client.get(f"{API}/coaches", params={"specialty": "Bottom"}, timeout=15)
        assert r.status_code == 200
        coaches = r.json()
        assert any(c["user_id"] == COACH_USER_ID for c in coaches)

    def test_specialty_miss(self, client):
        r = client.get(f"{API}/coaches", params={"specialty": "NonExistent"}, timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_q_case_insensitive_name(self, client):
        r = client.get(f"{API}/coaches", params={"q": "demo"}, timeout=15)
        assert r.status_code == 200
        coaches = r.json()
        assert any(c["user_id"] == COACH_USER_ID for c in coaches), \
            f"Expected case-insensitive q=demo to match Demo Coach, got {coaches}"

    def test_q_no_match(self, client):
        r = client.get(f"{API}/coaches", params={"q": "ZZZqqqUNFINDABLE"}, timeout=15)
        assert r.status_code == 200
        assert r.json() == []
