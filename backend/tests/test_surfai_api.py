"""Backend API tests for SurfAI"""
import os
import time
import pytest


BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
DEMO_TOKEN = "demo_token_active"
SAMPLE_VIDEO_PATH = "/tmp/test_surf.mp4"


# ---------------- Health ----------------
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{API}/health", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"
        assert "time" in body


# ---------------- Auth ----------------
class TestAuth:
    def test_auth_me_no_token(self, client):
        r = client.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_auth_me_invalid_token(self, client):
        r = client.get(f"{API}/auth/me",
                       headers={"Authorization": "Bearer not_a_real_token"},
                       timeout=15)
        assert r.status_code == 401

    def test_auth_me_with_demo_token(self, client, auth_headers):
        r = client.get(f"{API}/auth/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == "user_demo_12345"
        assert data["email"] == "demo@surfai.test"
        assert data["name"] == "Demo Surfer"

    def test_auth_session_invalid_session_id(self, client):
        r = client.post(f"{API}/auth/session",
                        json={"session_id": "definitely_invalid_session_xyz"},
                        timeout=20)
        assert r.status_code == 401


# ---------------- Analyses (list / detail / create / video) ----------------
class TestAnalyses:
    def test_list_analyses_unauthorized(self, client):
        r = client.get(f"{API}/analyses", timeout=15)
        assert r.status_code == 401

    def test_list_analyses_with_token(self, client, auth_headers):
        r = client.get(f"{API}/analyses", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Each item must have required keys (if any exist)
        for item in data:
            for k in ("analysis_id", "title", "score", "status", "created_at"):
                assert k in item

    @pytest.mark.timeout(120)
    def test_create_analysis_uploads_and_runs_gemini(self, client, auth_headers):
        assert os.path.exists(SAMPLE_VIDEO_PATH), "Sample video not downloaded"
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": ("sample.mp4", f, "video/mp4")}
            r = client.post(f"{API}/analyses", headers=auth_headers,
                            files=files, timeout=120)
        assert r.status_code == 200, f"Create failed: {r.status_code} - {r.text[:300]}"
        data = r.json()
        # Validate AnalysisOut shape
        for k in ("analysis_id", "user_id", "title", "score", "overall_rating",
                  "summary", "strengths", "mistakes", "corrections", "tips",
                  "drills", "status", "created_at"):
            assert k in data, f"Missing key: {k}"
        assert data["user_id"] == "user_demo_12345"
        assert isinstance(data["score"], int)
        assert 0 <= data["score"] <= 100
        assert isinstance(data["mistakes"], list)
        assert isinstance(data["corrections"], list)
        assert isinstance(data["tips"], list)
        assert isinstance(data["drills"], list)
        assert data["status"] == "ready"

        # Persist for downstream tests
        pytest.created_analysis_id = data["analysis_id"]

    def test_get_analysis_detail(self, client, auth_headers):
        analysis_id = getattr(pytest, "created_analysis_id", None)
        if not analysis_id:
            pytest.skip("No analysis created in previous step")
        r = client.get(f"{API}/analyses/{analysis_id}",
                       headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["analysis_id"] == analysis_id
        assert data["user_id"] == "user_demo_12345"

    def test_get_analysis_detail_unauth(self, client):
        analysis_id = getattr(pytest, "created_analysis_id", None)
        if not analysis_id:
            pytest.skip("No analysis created in previous step")
        r = client.get(f"{API}/analyses/{analysis_id}", timeout=15)
        assert r.status_code == 401

    def test_get_analysis_detail_not_found(self, client, auth_headers):
        r = client.get(f"{API}/analyses/ana_does_not_exist_xx",
                       headers=auth_headers, timeout=15)
        assert r.status_code == 404

    def test_video_stream_with_token(self, client):
        analysis_id = getattr(pytest, "created_analysis_id", None)
        if not analysis_id:
            pytest.skip("No analysis created in previous step")
        url = f"{API}/analyses/{analysis_id}/video?token={DEMO_TOKEN}"
        r = client.get(url, timeout=30, stream=True)
        assert r.status_code == 200
        # Pull a small chunk to confirm bytes flow
        chunk = next(r.iter_content(chunk_size=1024), b"")
        assert len(chunk) > 0
        ct = r.headers.get("Content-Type", "")
        assert "video" in ct or ct == "application/octet-stream"

    def test_video_stream_missing_token(self, client):
        r = client.get(f"{API}/analyses/whatever/video", timeout=15)
        assert r.status_code == 401

    def test_video_stream_invalid_token(self, client):
        r = client.get(f"{API}/analyses/whatever/video?token=invalid_token_xx",
                       timeout=15)
        assert r.status_code == 401


# ---------------- Logout ----------------
class TestLogout:
    """Run last; uses a separate token so we don't break the demo session."""

    def test_logout_no_op_without_token(self, client):
        r = client.post(f"{API}/auth/logout", timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
