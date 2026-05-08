"""Backend API tests for SurfAI v2 - Memberships, Coach, Stripe."""
import os
import pytest


BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
FREE_TOKEN = "demo_token_active"
COACH_TOKEN = "demo_coach_token"
COACH_USER_ID = "user_coach_67890"
FREE_USER_ID = "user_demo_12345"
SAMPLE_VIDEO_PATH = "/tmp/test_surf.mp4"
ORIGIN_URL = "https://wave-motion-ai.preview.emergentagent.com"


@pytest.fixture
def free_headers():
    return {"Authorization": f"Bearer {FREE_TOKEN}"}


@pytest.fixture
def coach_headers():
    return {"Authorization": f"Bearer {COACH_TOKEN}"}


# ---------------- Plans ----------------
class TestPlans:
    def test_get_plans(self, client):
        r = client.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200
        body = r.json()
        plans = body["plans"]
        ids = {p["plan_id"]: p for p in plans}
        assert "free" in ids and "coach" in ids
        assert ids["coach"]["amount"] == 120.00
        assert ids["coach"]["currency"] == "usd"
        assert ids["free"]["amount"] == 0.0
        assert body["free_daily_limit"] == 1


# ---------------- Quota ----------------
class TestQuota:
    def test_quota_free(self, client, free_headers):
        r = client.get(f"{API}/analyses/quota", headers=free_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "free"
        assert d["limit"] == 1
        assert "remaining" in d and "used_today" in d

    def test_quota_coach_unlimited(self, client, coach_headers):
        r = client.get(f"{API}/analyses/quota", headers=coach_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "coach"
        assert d["limit"] == -1
        assert d["remaining"] == -1


# ---------------- Free quota enforcement ----------------
class TestFreeQuotaEnforcement:
    @pytest.mark.timeout(180)
    def test_free_first_then_402(self, client, free_headers):
        assert os.path.exists(SAMPLE_VIDEO_PATH), "Sample video missing"
        # First analysis - may succeed or fail depending on existing usage
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample.mp4", f, "video/mp4")}
            r1 = client.post(f"{API}/analyses", headers=free_headers,
                             files=files, timeout=180)
        # Either 200 (first time today) or 402 (already used)
        assert r1.status_code in (200, 402), f"Unexpected: {r1.status_code} {r1.text[:300]}"

        # Second attempt MUST be 402
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample.mp4", f, "video/mp4")}
            r2 = client.post(f"{API}/analyses", headers=free_headers,
                             files=files, timeout=30)
        assert r2.status_code == 402, f"Expected 402, got {r2.status_code} {r2.text[:300]}"
        body = r2.json()
        assert "Upgrade" in body.get("detail", "") or "limit" in body.get("detail", "").lower()


# ---------------- Coach unlimited ----------------
class TestCoachUnlimited:
    @pytest.mark.timeout(180)
    def test_coach_can_create_analysis(self, client, coach_headers):
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample.mp4", f, "video/mp4")}
            r = client.post(f"{API}/analyses", headers=coach_headers,
                            files=files, timeout=180)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d["user_id"] == COACH_USER_ID
        assert d["status"] == "ready"
        pytest.coach_analysis_id = d["analysis_id"]


# ---------------- Coach directory ----------------
class TestCoaches:
    def test_list_public_coaches(self, client):
        r = client.get(f"{API}/coaches", timeout=15)
        assert r.status_code == 200
        coaches = r.json()
        assert isinstance(coaches, list)
        assert any(c["user_id"] == COACH_USER_ID for c in coaches), \
            f"Demo coach not in directory: {coaches}"
        demo = next(c for c in coaches if c["user_id"] == COACH_USER_ID)
        assert demo["name"] == "Demo Coach"
        assert demo["coach_specialty"]

    def test_get_single_coach(self, client):
        r = client.get(f"{API}/coaches/{COACH_USER_ID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user_id"] == COACH_USER_ID
        assert d["coach_location"] == "Ericeira, PT"

    def test_get_unknown_coach(self, client):
        r = client.get(f"{API}/coaches/unknown_user_xx", timeout=15)
        assert r.status_code == 404


# ---------------- Coach profile update ----------------
class TestCoachProfile:
    def test_update_coach_profile_success(self, client, coach_headers):
        payload = {
            "bio": "Updated bio for testing.",
            "specialty": "Bottom-turn & rail control",
            "location": "Ericeira, PT",
            "public": True,
        }
        r = client.put(f"{API}/coach/profile", headers=coach_headers,
                       json=payload, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["coach_bio"] == "Updated bio for testing."
        assert d["coach_public"] is True

    def test_update_coach_profile_forbidden_for_free(self, client, free_headers):
        r = client.put(f"{API}/coach/profile", headers=free_headers,
                       json={"bio": "hack"}, timeout=15)
        assert r.status_code == 403


# ---------------- Coach inbox ----------------
class TestCoachInbox:
    def test_inbox_forbidden_for_free(self, client, free_headers):
        r = client.get(f"{API}/coach/inbox", headers=free_headers, timeout=15)
        assert r.status_code == 403

    def test_inbox_ok_for_coach(self, client, coach_headers):
        r = client.get(f"{API}/coach/inbox", headers=coach_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Sharing & comments ----------------
class TestSharingAndComments:
    """Free user shares an analysis with coach; both can comment."""

    @pytest.mark.timeout(180)
    def test_setup_share_flow(self, client, free_headers, coach_headers):
        # Free user needs an analysis. Re-seed to clear quota then upload.
        # We'll attempt to fetch existing first; if none exists, we need to
        # ensure quota is clear. Just delete via API? No — go via a fresh upload.
        # The free quota test class may have used today's slot. Workaround:
        # delete via mongosh would require shell. Instead, list existing.
        r_list = client.get(f"{API}/analyses", headers=free_headers, timeout=15)
        assert r_list.status_code == 200
        items = r_list.json()
        if items:
            analysis_id = items[0]["analysis_id"]
        else:
            with open(SAMPLE_VIDEO_PATH, "rb") as f:
                files = {"file": ("sample.mp4", f, "video/mp4")}
                rc = client.post(f"{API}/analyses", headers=free_headers,
                                 files=files, timeout=180)
            assert rc.status_code == 200, f"Could not create initial free analysis: {rc.status_code} {rc.text[:200]}"
            analysis_id = rc.json()["analysis_id"]
        pytest.shared_analysis_id = analysis_id

        # Share with coach
        rs = client.post(f"{API}/analyses/{analysis_id}/share",
                        headers=free_headers,
                        json={"coach_user_id": COACH_USER_ID}, timeout=15)
        assert rs.status_code == 200, f"{rs.status_code} {rs.text[:300]}"
        assert rs.json()["coach_user_id"] == COACH_USER_ID

        # Coach can now read the analysis
        rg = client.get(f"{API}/analyses/{analysis_id}",
                       headers=coach_headers, timeout=15)
        assert rg.status_code == 200, f"Coach could not read shared analysis: {rg.status_code}"

        # Coach inbox now contains it
        ri = client.get(f"{API}/coach/inbox", headers=coach_headers, timeout=15)
        assert ri.status_code == 200
        ids = [a["analysis_id"] for a in ri.json()]
        assert analysis_id in ids

    def test_owner_comment(self, client, free_headers):
        analysis_id = getattr(pytest, "shared_analysis_id", None)
        if not analysis_id:
            pytest.skip("share setup did not run")
        r = client.post(f"{API}/analyses/{analysis_id}/comments",
                        headers=free_headers,
                        json={"text": "Owner comment"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["author_id"] == FREE_USER_ID
        assert d["text"] == "Owner comment"

    def test_coach_comment(self, client, coach_headers):
        analysis_id = getattr(pytest, "shared_analysis_id", None)
        if not analysis_id:
            pytest.skip("share setup did not run")
        r = client.post(f"{API}/analyses/{analysis_id}/comments",
                        headers=coach_headers,
                        json={"text": "Coach feedback"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["author_id"] == COACH_USER_ID
        assert d["is_coach"] is True

    def test_list_comments(self, client, coach_headers):
        analysis_id = getattr(pytest, "shared_analysis_id", None)
        if not analysis_id:
            pytest.skip("share setup did not run")
        r = client.get(f"{API}/analyses/{analysis_id}/comments",
                       headers=coach_headers, timeout=15)
        assert r.status_code == 200
        comments = r.json()
        assert len(comments) >= 2

    def test_comment_forbidden_for_other_user(self, client):
        """A non-owner non-coach (bogus token) → 401. Use a real other free user
        scenario by simulating with no token first."""
        analysis_id = getattr(pytest, "shared_analysis_id", None)
        if not analysis_id:
            pytest.skip("share setup did not run")
        r = client.post(f"{API}/analyses/{analysis_id}/comments",
                        json={"text": "bad"}, timeout=15)
        assert r.status_code == 401


# ---------------- Stripe checkout ----------------
class TestStripeCheckout:
    def test_checkout_invalid_plan(self, client, free_headers):
        r = client.post(f"{API}/payments/checkout", headers=free_headers,
                        json={"plan_id": "garbage", "origin_url": ORIGIN_URL},
                        timeout=20)
        assert r.status_code == 400

    def test_checkout_unauthorized(self, client):
        r = client.post(f"{API}/payments/checkout",
                        json={"plan_id": "coach", "origin_url": ORIGIN_URL},
                        timeout=20)
        assert r.status_code == 401

    @pytest.mark.timeout(45)
    def test_checkout_creates_stripe_session(self, client, free_headers):
        r = client.post(f"{API}/payments/checkout", headers=free_headers,
                        json={"plan_id": "coach", "origin_url": ORIGIN_URL},
                        timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert "url" in d and "session_id" in d
        assert "checkout.stripe.com" in d["url"] or "stripe.com" in d["url"]
        assert d["session_id"].startswith("cs_")
        pytest.stripe_session_id = d["session_id"]

    def test_payment_status_unpaid(self, client, free_headers):
        sid = getattr(pytest, "stripe_session_id", None)
        if not sid:
            pytest.skip("no checkout session created")
        r = client.get(f"{API}/payments/status/{sid}",
                       headers=free_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["session_id"] == sid
        # Unpaid → tier should not be "coach"
        assert d.get("tier") in (None, "free", "")
        assert d["payment_status"] != "paid"

    def test_payment_status_unknown_session(self, client, free_headers):
        r = client.get(f"{API}/payments/status/cs_unknown_xxxxx",
                       headers=free_headers, timeout=20)
        assert r.status_code == 404

    def test_free_user_tier_unchanged(self, client, free_headers):
        r = client.get(f"{API}/auth/me", headers=free_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "free", f"Free user shouldn't be upgraded yet, got {d['tier']}"
