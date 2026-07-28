"""
Iteration 19 — Phase 2/3/4 tests (pose endpoint + regression).

Coverage:
- GET /api/analyses/{id}/pose — auth, ownership, shape, metrics
- Regression: /auth/me, /analyses, /analyses/{id}, quota, plans still OK
"""
import os
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

DEMO_TOKEN = "demo_token_active"          # user_demo_12345
COACH_TOKEN = "demo_coach_token"          # user_coach_67890
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}
COACH_AUTH = {"Authorization": f"Bearer {COACH_TOKEN}"}

NEW_ID = "ana_demoupgrade01"
OLD_ID = "ana_ipadshot001"


# ---------------- Pose endpoint — happy path (owner, ready) ----------------
class TestPoseEndpointReady:
    def test_pose_returns_ready_with_data(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", headers=AUTH, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ready", body
        data = body.get("data")
        assert isinstance(data, dict)
        # Frame/dim metadata
        assert isinstance(data.get("width"), int) and data["width"] > 0
        assert isinstance(data.get("height"), int) and data["height"] > 0
        assert isinstance(data.get("sample_fps"), (int, float)) and data["sample_fps"] > 0
        # 55 frames per problem statement — allow ±5 tolerance
        frames = data.get("frames")
        assert isinstance(frames, list) and 45 <= len(frames) <= 65, len(frames)

    def test_pose_frame_shape(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", headers=AUTH, timeout=30)
        frames = r.json()["data"]["frames"]
        # Each frame has t (float) + kp[33][3]
        f0 = frames[0]
        assert "t" in f0 and isinstance(f0["t"], (int, float))
        kp = f0["kp"]
        assert isinstance(kp, list) and len(kp) == 33
        for p in kp:
            assert isinstance(p, list) and len(p) == 3
            # x, y are ~normalised (may slightly leak <0 or >1 when crop
            # touches the frame edge) — allow small overshoot.
            assert -0.5 <= p[0] <= 1.5
            assert -0.5 <= p[1] <= 1.5
            assert 0.0 <= p[2] <= 1.0

    def test_pose_metrics_non_empty(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", headers=AUTH, timeout=30)
        m = r.json()["data"]["metrics"]
        assert isinstance(m, dict)
        assert isinstance(m.get("speed"), list) and len(m["speed"]) > 0
        assert isinstance(m.get("compression"), list) and len(m["compression"]) > 0
        s0 = m["speed"][0]
        assert "t" in s0 and "v" in s0
        c0 = m["compression"][0]
        assert "t" in c0 and "v" in c0
        # Compression is a knee angle in degrees (~10-180)
        assert 5.0 <= c0["v"] <= 200.0

    def test_pose_frames_time_monotonic(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", headers=AUTH, timeout=30)
        frames = r.json()["data"]["frames"]
        ts = [f["t"] for f in frames]
        assert ts == sorted(ts), "frame timestamps must be monotonic"


# ---------------- Pose endpoint — auth / ownership ----------------
class TestPoseEndpointAuth:
    def test_pose_requires_token(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_pose_other_user_gets_404(self):
        # Coach is not shared_with — must NOT see demo user's analysis
        r = requests.get(f"{API}/analyses/{NEW_ID}/pose", headers=COACH_AUTH, timeout=15)
        assert r.status_code == 404, r.text

    def test_pose_unknown_id_404(self):
        r = requests.get(
            f"{API}/analyses/ana_does_not_exist_xyz/pose", headers=AUTH, timeout=15
        )
        assert r.status_code == 404, r.text


# ---------------- Pose endpoint — "no pose data" states ----------------
class TestPoseNoData:
    """When an analysis has no pose_status ('none') or has failed/processing,
    endpoint returns {status: <state>, data: null} without 500."""
    def test_pose_old_analysis_reasonable_shape(self):
        # ana_ipadshot001 may or may not have pose seeded — either way it must
        # not 500 and must return the documented envelope.
        r = requests.get(f"{API}/analyses/{OLD_ID}/pose", headers=AUTH, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "status" in body
        assert body["status"] in ("ready", "none", "processing", "failed"), body
        if body["status"] == "ready":
            assert isinstance(body.get("data"), dict)
        else:
            assert body.get("data") is None


# ---------------- Regression — existing analysis endpoints still OK ----------
class TestRegression:
    def test_auth_me(self):
        r = requests.get(f"{API}/auth/me", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["user_id"] == "user_demo_12345"

    def test_get_new_analysis_has_scores(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("scores"), list) and len(d["scores"]) >= 1
        assert isinstance(d.get("main_mistake"), dict)
        for k in ["title", "why", "cause", "performance_lost", "fix"]:
            assert k in d["main_mistake"]
        assert isinstance(d.get("key_moments"), list) and len(d["key_moments"]) >= 1

    def test_list_analyses(self):
        r = requests.get(f"{API}/analyses", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        ids = {a["analysis_id"] for a in r.json()}
        assert NEW_ID in ids and OLD_ID in ids

    def test_quota(self):
        r = requests.get(f"{API}/analyses/quota", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "tier" in d

    def test_plans(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, dict) and isinstance(d.get("plans"), list)
