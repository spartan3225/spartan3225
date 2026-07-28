"""
Iteration 18 — Phase 1 premium upgrade tests.
Covers:
- New /api/users/preferences endpoint (language)
- Extended AnalysisOut schema (scores/main_mistake/key_moments) on new seed
- Backwards compatibility for old seed (no new fields)
- Regression on auth/analyses/quota/plans/comments/chunk-upload
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
DEMO_TOKEN = "demo_token_active"
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}
NEW_ID = "ana_demoupgrade01"
OLD_ID = "ana_ipadshot001"


# ---------------- Auth / regression ----------------
class TestAuthRegression:
    def test_auth_me(self):
        r = requests.get(f"{API}/auth/me", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user_id"] == "user_demo_12345"
        assert data["email"] == "demo@surfai.test"
        # preferred_language must be exposed
        assert "preferred_language" in data

    def test_auth_me_requires_token(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)


# ---------------- Preferences (new endpoint) ----------------
class TestPreferences:
    def test_put_preferences_es(self):
        r = requests.put(
            f"{API}/users/preferences",
            headers=AUTH,
            json={"language": "es"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("preferred_language") == "es"

    def test_put_preferences_pt(self):
        r = requests.put(
            f"{API}/users/preferences",
            headers=AUTH,
            json={"language": "pt"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("preferred_language") == "pt"

    def test_put_preferences_invalid(self):
        r = requests.put(
            f"{API}/users/preferences",
            headers=AUTH,
            json={"language": "zz"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_put_preferences_requires_auth(self):
        r = requests.put(
            f"{API}/users/preferences", json={"language": "en"}, timeout=15
        )
        assert r.status_code in (401, 403)

    def test_reset_language_en(self):
        r = requests.put(
            f"{API}/users/preferences",
            headers=AUTH,
            json={"language": "en"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["preferred_language"] == "en"


# ---------------- Extended schema on new seed ----------------
class TestNewSchemaAnalysis:
    def test_get_new_analysis_returns_new_fields(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["analysis_id"] == NEW_ID
        assert data["status"] == "ready"
        # New optional fields must be present with proper types
        assert isinstance(data.get("scores"), list) and len(data["scores"]) >= 1
        for s in data["scores"]:
            assert set(["key", "value", "note"]).issubset(s.keys())
            assert isinstance(s["value"], (int, float))
        assert isinstance(data.get("main_mistake"), dict)
        for k in ["title", "why", "cause", "performance_lost", "fix"]:
            assert k in data["main_mistake"]
        assert isinstance(data.get("key_moments"), list)
        assert len(data["key_moments"]) >= 1
        for km in data["key_moments"]:
            assert "timestamp" in km and "label" in km and "type" in km

    def test_new_analysis_still_has_legacy_fields(self):
        r = requests.get(f"{API}/analyses/{NEW_ID}", headers=AUTH, timeout=15)
        d = r.json()
        # Backwards-compatible legacy fields still present
        for key in ["title", "summary", "strengths", "mistakes",
                    "corrections", "tips", "drills"]:
            assert key in d, f"missing {key}"


# ---------------- Backwards compatibility on old seed ----------------
class TestOldSchemaAnalysis:
    def test_get_old_analysis_still_ok(self):
        r = requests.get(f"{API}/analyses/{OLD_ID}", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["analysis_id"] == OLD_ID
        # New optional fields may be missing / None / empty — must NOT 500
        # Old schema: scores/main_mistake/key_moments absent or empty
        # AnalysisOut may still expose them as None
        assert d.get("scores") in (None, []) or (
            isinstance(d.get("scores"), list) and len(d["scores"]) == 0
        )
        assert d.get("main_mistake") in (None, {}) or isinstance(
            d.get("main_mistake"), dict
        ) is True
        assert d.get("key_moments") in (None, []) or (
            isinstance(d.get("key_moments"), list) and len(d["key_moments"]) == 0
        )
        # Legacy fields still there
        assert "title" in d and "summary" in d


# ---------------- Analyses list / quota / plans ----------------
class TestListsAndQuota:
    def test_list_analyses(self):
        r = requests.get(f"{API}/analyses", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        arr = r.json()
        assert isinstance(arr, list)
        ids = {a["analysis_id"] for a in arr}
        assert NEW_ID in ids and OLD_ID in ids

    def test_quota(self):
        r = requests.get(f"{API}/analyses/quota", headers=AUTH, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "tier" in d
        # Free user has lifetime cap; used_total >= 2 from seeds
        # Just assert fields present
        assert "used_total" in d or "remaining" in d or "used" in d

    def test_plans(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, dict) and isinstance(d.get("plans"), list)
        assert len(d["plans"]) >= 1


# ---------------- Comments regression ----------------
class TestComments:
    def test_list_comments_new_analysis(self):
        r = requests.get(
            f"{API}/analyses/{NEW_ID}/comments", headers=AUTH, timeout=15
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_post_and_read_comment(self):
        body = {"text": "TEST_iter18 comment"}
        r = requests.post(
            f"{API}/analyses/{NEW_ID}/comments",
            headers=AUTH,
            json=body,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        created = r.json()
        assert created.get("text") == "TEST_iter18 comment"
        # Confirm read-back
        r2 = requests.get(
            f"{API}/analyses/{NEW_ID}/comments", headers=AUTH, timeout=15
        )
        assert r2.status_code == 200
        texts = [c.get("text") for c in r2.json()]
        assert "TEST_iter18 comment" in texts


# ---------------- Chunked upload validation still enforced ----------------
class TestChunkedUpload:
    def test_chunk_upload_auth_required(self):
        r = requests.post(
            f"{API}/uploads/chunk",
            files={"chunk": ("x.bin", b"\x00", "application/octet-stream")},
            data={
                "upload_id": "test_upload",
                "chunk_index": "0",
                "total_chunks": "1",
                "filename": "x.mp4",
            },
            timeout=15,
        )
        assert r.status_code in (401, 403), r.text

    def test_chunk_upload_missing_fields(self):
        # Auth'd request but missing required fields must not 500
        r = requests.post(
            f"{API}/uploads/chunk", headers=AUTH, data={}, timeout=15
        )
        assert r.status_code in (400, 401, 403, 422), r.text
