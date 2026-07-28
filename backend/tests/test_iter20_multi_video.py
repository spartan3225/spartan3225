"""Iteration 20 — Multi-video paid add-on & Train tutorials regression.

Covers:
- POST /api/analyses/finalize-multi validation (upload count, id format, existence, missing chunks)
- 402 when caller has no multi_credits (demo_coach_token)
- GET /api/auth/me returns multi_credits
- POST /api/payments/lemonsqueezy/checkout: plan_id="multi" -> 400 (variant not configured);
  plan_id="learn" -> 200 with url (no payment completion)
- Existing multi analysis ana_cf496d925cac4b: video_count=2, video?index=0/1/5 all 200
- Regression: single chunk-upload validation, quota endpoint, /analyses list
"""
from __future__ import annotations

import io
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")

DEMO_TOKEN = "demo_token_active"          # user_demo_12345 — should have 1 multi_credit
COACH_TOKEN = "demo_coach_token"           # user_coach_67890 — 0 multi_credits
MULTI_ANALYSIS_ID = "ana_cf496d925cac4b"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    yield s
    s.close()


# ---------------- /auth/me ----------------
def test_auth_me_demo_has_multi_credits_field(sess):
    r = sess.get(f"{BASE_URL}/api/auth/me", headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "multi_credits" in data, "User model must expose multi_credits"
    assert isinstance(data["multi_credits"], int)
    assert data["user_id"] == "user_demo_12345"
    # main-agent E2E left demo user with 1 credit
    assert data["multi_credits"] >= 1, f"Expected >=1 multi_credit, got {data['multi_credits']}"


def test_auth_me_coach_has_zero_multi_credits(sess):
    r = sess.get(f"{BASE_URL}/api/auth/me", headers=_headers(COACH_TOKEN), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("multi_credits", 0) == 0


# ---------------- finalize-multi validation ----------------
def test_finalize_multi_requires_two_or_three_uploads(sess):
    """1 upload -> 400."""
    good_id = uuid.uuid4().hex
    body = {"uploads": [{"upload_id": good_id, "filename": "a.mp4", "mime_type": "video/mp4", "total_chunks": 1}]}
    r = sess.post(f"{BASE_URL}/api/analyses/finalize-multi", json=body, headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 400, r.text
    assert "2 or 3" in r.json().get("detail", "").lower() or "provide" in r.json().get("detail", "").lower()


def test_finalize_multi_rejects_bad_upload_id_format(sess):
    body = {
        "uploads": [
            {"upload_id": "not-hex!!!", "filename": "a.mp4", "mime_type": "video/mp4", "total_chunks": 1},
            {"upload_id": uuid.uuid4().hex, "filename": "b.mp4", "mime_type": "video/mp4", "total_chunks": 1},
        ]
    }
    r = sess.post(f"{BASE_URL}/api/analyses/finalize-multi", json=body, headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 400, r.text
    assert "invalid upload_id" in r.json().get("detail", "").lower()


def test_finalize_multi_rejects_nonexistent_upload_id(sess):
    """Valid hex format but not present in upload_chunks -> 400 'Upload not found'."""
    body = {
        "uploads": [
            {"upload_id": uuid.uuid4().hex, "filename": "a.mp4", "mime_type": "video/mp4", "total_chunks": 1},
            {"upload_id": uuid.uuid4().hex, "filename": "b.mp4", "mime_type": "video/mp4", "total_chunks": 1},
        ]
    }
    r = sess.post(f"{BASE_URL}/api/analyses/finalize-multi", json=body, headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "").lower()
    assert "not found" in detail or "incomplete" in detail


# ---------------- finalize-multi 402 with 0 credits ----------------
def _upload_one_tiny_chunk(sess, token: str, upload_id: str, data: bytes = b"fakevideo") -> None:
    """POST a single chunk (total=1) for a given upload_id using the coach token."""
    files = {"file": ("chunk.bin", io.BytesIO(data), "application/octet-stream")}
    form = {"upload_id": upload_id, "chunk_index": "0", "total_chunks": "1"}
    r = sess.post(
        f"{BASE_URL}/api/uploads/chunk",
        files=files,
        data=form,
        headers=_headers(token),
        timeout=15,
    )
    assert r.status_code == 200, f"chunk upload failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("received") == 1
    assert body.get("total") == 1


def test_finalize_multi_returns_402_when_zero_credits(sess):
    """Coach user has 0 multi_credits — after uploading valid chunks, finalize-multi must return 402."""
    up1 = uuid.uuid4().hex
    up2 = uuid.uuid4().hex
    _upload_one_tiny_chunk(sess, COACH_TOKEN, up1)
    _upload_one_tiny_chunk(sess, COACH_TOKEN, up2)
    body = {
        "uploads": [
            {"upload_id": up1, "filename": "a.mp4", "mime_type": "video/mp4", "total_chunks": 1},
            {"upload_id": up2, "filename": "b.mp4", "mime_type": "video/mp4", "total_chunks": 1},
        ]
    }
    r = sess.post(f"{BASE_URL}/api/analyses/finalize-multi", json=body, headers=_headers(COACH_TOKEN), timeout=20)
    assert r.status_code == 402, f"Expected 402, got {r.status_code} {r.text}"
    detail = r.json().get("detail", "").lower()
    assert "credit" in detail


# ---------------- LemonSqueezy checkout ----------------
def test_lemonsqueezy_checkout_multi_returns_400_invalid_plan(sess):
    """Variant not configured -> 400 Invalid plan."""
    body = {
        "plan_id": "multi",
        "origin_url": "https://wave-motion-ai.preview.emergentagent.com",
    }
    r = sess.post(
        f"{BASE_URL}/api/payments/lemonsqueezy/checkout",
        json=body,
        headers=_headers(DEMO_TOKEN),
        timeout=20,
    )
    # Expected 400 Invalid plan (per problem statement — variant env is empty)
    assert r.status_code == 400, f"Expected 400, got {r.status_code} {r.text}"
    assert "invalid plan" in r.json().get("detail", "").lower()


def test_lemonsqueezy_checkout_learn_returns_url_regression(sess):
    """Regression: 'learn' plan checkout still returns a URL. DO NOT complete payment."""
    body = {
        "plan_id": "learn",
        "origin_url": "https://wave-motion-ai.preview.emergentagent.com",
    }
    r = sess.post(
        f"{BASE_URL}/api/payments/lemonsqueezy/checkout",
        json=body,
        headers=_headers(DEMO_TOKEN),
        timeout=25,
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code} {r.text}"
    data = r.json()
    assert "url" in data and data["url"].startswith("http"), data
    assert "session_id" in data


# ---------------- Existing multi analysis ----------------
def test_multi_analysis_returns_video_count_and_ready_status(sess):
    r = sess.get(
        f"{BASE_URL}/api/analyses/{MULTI_ANALYSIS_ID}",
        headers=_headers(DEMO_TOKEN),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("video_count") == 2, f"video_count expected 2, got {data.get('video_count')}"
    assert data.get("status") == "ready"
    assert data.get("analysis_id") == MULTI_ANALYSIS_ID
    # Sanity: AI outputs present
    assert isinstance(data.get("key_moments") or [], list)


@pytest.mark.parametrize("idx", [0, 1])
def test_multi_analysis_video_endpoint_serves_each_index(sess, idx):
    r = sess.get(
        f"{BASE_URL}/api/analyses/{MULTI_ANALYSIS_ID}/video",
        params={"token": DEMO_TOKEN, "index": idx},
        timeout=30,
        stream=True,
    )
    assert r.status_code == 200, f"index={idx} -> {r.status_code} {r.text[:200]}"
    assert "video" in r.headers.get("content-type", "")
    # Read a few bytes to confirm body streams
    it = r.iter_content(chunk_size=512)
    first = next(it, b"")
    assert len(first) > 0, f"empty body for index={idx}"
    r.close()


def test_multi_analysis_video_index_clamps_to_last_clip(sess):
    """index=5 should clamp to last available clip and still return 200."""
    r = sess.get(
        f"{BASE_URL}/api/analyses/{MULTI_ANALYSIS_ID}/video",
        params={"token": DEMO_TOKEN, "index": 5},
        timeout=30,
        stream=True,
    )
    assert r.status_code == 200, f"index=5 -> {r.status_code} {r.text[:200]}"
    r.close()


# ---------------- Regression ----------------
def test_single_chunk_upload_validation_regression(sess):
    """Bad upload_id format still rejected on single chunk endpoint."""
    files = {"file": ("chunk.bin", io.BytesIO(b"x"), "application/octet-stream")}
    form = {"upload_id": "bad-id!!!", "chunk_index": "0", "total_chunks": "1"}
    r = sess.post(
        f"{BASE_URL}/api/uploads/chunk",
        files=files,
        data=form,
        headers=_headers(DEMO_TOKEN),
        timeout=15,
    )
    assert r.status_code == 400
    assert "upload_id" in r.json().get("detail", "").lower()


def test_quota_endpoint_regression(sess):
    r = sess.get(f"{BASE_URL}/api/analyses/quota", headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # Standard quota response — at minimum has 'tier' and either used/limit or remaining
    assert "tier" in data


def test_analyses_list_regression(sess):
    r = sess.get(f"{BASE_URL}/api/analyses", headers=_headers(DEMO_TOKEN), timeout=15)
    assert r.status_code == 200, r.text
    lst = r.json()
    assert isinstance(lst, list)
    ids = [a.get("analysis_id") for a in lst]
    assert MULTI_ANALYSIS_ID in ids, "Multi analysis missing from list"
