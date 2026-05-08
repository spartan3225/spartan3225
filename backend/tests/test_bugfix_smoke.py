"""Targeted bug fix verification for iteration_3:
- Bug #1: POST /api/analyses with coach token must return 200 even when
  Gemini returns dicts in drills/strengths/tips/corrections lists
  (server now coerces via _coerce_str_list).
- Bug #2: GET /api/payments/status/{session_id} must NOT 500 when the
  emergentintegrations library raises CheckoutError - degrade gracefully.
- Regression: GET /api/payments/status/cs_test_doesnotexist still 404.
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"
FREE_TOKEN = "demo_token_active"
SAMPLE_VIDEO_PATH = "/tmp/test_surf.mp4"
ORIGIN_URL = "https://wave-motion-ai.preview.emergentagent.com"


@pytest.fixture
def coach_headers():
    return {"Authorization": f"Bearer {COACH_TOKEN}"}


@pytest.fixture
def free_headers():
    return {"Authorization": f"Bearer {FREE_TOKEN}"}


# Bug #1: coach analyses succeed and lists are List[str]
class TestBugCoachAnalysisCoerce:
    @pytest.mark.timeout(240)
    def test_first_coach_upload_returns_200_and_lists_are_strings(self, coach_headers):
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample.mp4", f, "video/mp4")}
            r = requests.post(f"{API}/analyses", headers=coach_headers,
                              files=files, timeout=240)
        assert r.status_code == 200, f"{r.status_code} {r.text[:500]}"
        d = r.json()
        assert d["status"] == "ready"
        for fld in ("strengths", "corrections", "tips", "drills"):
            v = d.get(fld)
            assert isinstance(v, list), f"{fld} not list: {type(v)}"
            for item in v:
                assert isinstance(item, str), \
                    f"{fld} contains non-string item: {item!r}"

    @pytest.mark.timeout(240)
    def test_second_coach_upload_returns_200_and_lists_are_strings(self, coach_headers):
        # Stability check: a second deeper-prompt analysis must also work.
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample2.mp4", f, "video/mp4")}
            r = requests.post(f"{API}/analyses", headers=coach_headers,
                              files=files, timeout=240)
        assert r.status_code == 200, f"{r.status_code} {r.text[:500]}"
        d = r.json()
        for fld in ("strengths", "corrections", "tips", "drills"):
            v = d.get(fld)
            assert isinstance(v, list)
            for item in v:
                assert isinstance(item, str), \
                    f"{fld} contains non-string: {item!r}"


# Bug #2: payment status no longer 500s on Stripe metadata error
class TestBugPaymentStatusNoFiveHundred:
    @pytest.mark.timeout(45)
    def test_checkout_then_status_polls_no_500(self, free_headers):
        # Create a real checkout session
        rc = requests.post(f"{API}/payments/checkout", headers=free_headers,
                           json={"plan_id": "coach", "origin_url": ORIGIN_URL},
                           timeout=30)
        assert rc.status_code == 200, f"checkout: {rc.status_code} {rc.text[:300]}"
        d = rc.json()
        sid = d["session_id"]
        assert sid.startswith("cs_")
        # Poll status 3 times in succession - none must 500
        for i in range(3):
            r = requests.get(f"{API}/payments/status/{sid}",
                             headers=free_headers, timeout=20)
            assert r.status_code == 200, \
                f"poll #{i+1}: {r.status_code} {r.text[:300]}"
            j = r.json()
            assert j["session_id"] == sid
            assert j.get("status") == "open"
            assert j.get("payment_status") in ("initiated", "unpaid")
            assert j.get("plan_id") == "coach"
            assert j.get("tier") is None  # not yet paid

    def test_unknown_session_returns_404(self, free_headers):
        r = requests.get(f"{API}/payments/status/cs_test_doesnotexist",
                         headers=free_headers, timeout=20)
        assert r.status_code == 404, f"{r.status_code} {r.text[:200]}"
