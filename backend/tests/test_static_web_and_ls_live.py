"""SurfCoach23 iteration-8 regression tests.

Covers:
  1. Backend-served Expo web export (index, terms, privacy, refund, paywall,
     payment-success, JS bundle, SPA fallback for unknown path) — tested via
     the backend's INTERNAL host (localhost:8001) because the deployed prod
     domain routes root to the backend, while the preview domain routes root
     to the Expo dev server.
  2. API regressions on the public preview URL:
     - /api/plans returns LemonSqueezy provider + $15/$25/$35 USD plans.
     - /api/payments/lemonsqueezy/checkout returns live surfcoach23.lemon…
       checkout URL for seeded demo user.
     - Invalid plan_id => 400.
     - /api/webhook/lemonsqueezy without signature => 400.
"""
import os
import re
import pytest
import requests

# Public preview URL used for API regression (goes through ingress to backend).
PREVIEW_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")

# Direct backend host: the deployed .emergent.host domain routes root to
# backend, so we simulate that by hitting localhost:8001 (Expo dev server
# owns root on the preview domain, which would confuse the static-web tests).
BACKEND_DIRECT = "http://localhost:8001"
DEMO_TOKEN = "demo_token_active"


# ---------- 1. Backend-served Expo web export ----------
class TestStaticWebBuild:
    """Backend serves /app/backend/static_web at root with SPA fallback."""

    @pytest.mark.parametrize("path", ["/", "/terms", "/privacy", "/refund",
                                      "/paywall", "/payment-success"])
    def test_html_pages_return_200_html(self, path):
        r = requests.get(f"{BACKEND_DIRECT}{path}", timeout=10)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert "text/html" in r.headers.get("content-type", ""), \
            f"{path} content-type={r.headers.get('content-type')}"
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()

    def test_js_bundle_referenced_and_served(self):
        html = requests.get(f"{BACKEND_DIRECT}/", timeout=10).text
        m = re.search(r'/_expo/static/js/web/[A-Za-z0-9_.\-]+\.js', html)
        assert m, "No /_expo/static/js/web/*.js reference in index.html"
        js_path = m.group(0)
        r = requests.get(f"{BACKEND_DIRECT}{js_path}", timeout=15)
        assert r.status_code == 200, f"{js_path} -> {r.status_code}"
        ct = r.headers.get("content-type", "")
        assert "javascript" in ct or "text/plain" in ct, f"bundle ct={ct}"

    def test_unknown_path_falls_back_to_index_html(self):
        r = requests.get(f"{BACKEND_DIRECT}/xyz-does-not-exist", timeout=10)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_api_paths_are_not_html(self):
        # /api/* must still return JSON, not the SPA index.
        r = requests.get(f"{BACKEND_DIRECT}/api/plans", timeout=10)
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", ""), \
            f"/api/plans ct={r.headers.get('content-type')}"
        r2 = requests.get(f"{BACKEND_DIRECT}/api/health", timeout=10)
        assert r2.status_code == 200
        assert "application/json" in r2.headers.get("content-type", "")

    def test_static_pages_contain_rebranded_email(self):
        # Sanity check: index/terms/privacy/refund HTML shells reference the
        # JS bundle; the actual email string is baked into that JS bundle.
        # Verify it appears in the bundle (proves rebrand shipped to web).
        html = requests.get(f"{BACKEND_DIRECT}/", timeout=10).text
        m = re.search(r'/_expo/static/js/web/[A-Za-z0-9_.\-]+\.js', html)
        assert m
        bundle = requests.get(f"{BACKEND_DIRECT}{m.group(0)}", timeout=20).text
        assert "surfcoach23@gmail.com" in bundle, \
            "New contact email surfcoach23@gmail.com not found in JS bundle"
        assert "coach1othman@gmail.com" not in bundle, \
            "Old contact email still present in JS bundle"


# ---------- 2. API regressions on preview URL ----------
class TestPlansEndpoint:

    def test_plans_provider_and_pricing(self):
        r = requests.get(f"{PREVIEW_URL}/api/plans", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("provider") == "lemonsqueezy", data
        plans = {p["plan_id"]: p for p in data["plans"]}
        assert "free" in plans and plans["free"]["amount"] == 0.0
        assert plans["learn"]["amount"] == 15.0
        assert plans["learn"]["currency"] == "usd"
        assert plans["advanced"]["amount"] == 25.0
        assert plans["advanced"]["currency"] == "usd"
        assert plans["pro"]["amount"] == 35.0
        assert plans["pro"]["currency"] == "usd"


class TestLemonSqueezyCheckoutLive:

    HEADERS = {
        "Authorization": f"Bearer {DEMO_TOKEN}",
        "Content-Type": "application/json",
    }

    def test_checkout_learn_returns_live_surfcoach23_url(self):
        payload = {"plan_id": "learn", "origin_url": PREVIEW_URL}
        r = requests.post(
            f"{PREVIEW_URL}/api/payments/lemonsqueezy/checkout",
            json=payload, headers=self.HEADERS, timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert "url" in data and "session_id" in data
        # Live mode -> URL should be on the surfcoach23 lemonsqueezy subdomain
        assert "surfcoach23.lemonsqueezy.com" in data["url"], data["url"]

    def test_checkout_invalid_plan_returns_400(self):
        payload = {"plan_id": "not_a_real_plan", "origin_url": PREVIEW_URL}
        r = requests.post(
            f"{PREVIEW_URL}/api/payments/lemonsqueezy/checkout",
            json=payload, headers=self.HEADERS, timeout=15,
        )
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"


class TestLemonSqueezyWebhookSignature:

    def test_webhook_without_signature_returns_400(self):
        r = requests.post(
            f"{PREVIEW_URL}/api/webhook/lemonsqueezy",
            json={"meta": {"event_name": "test"}}, timeout=15,
        )
        assert r.status_code == 400
        assert "signature" in r.text.lower() or "invalid" in r.text.lower()
