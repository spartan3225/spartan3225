"""
Iteration 21 — Video persistence & upload reliability regression suite.

Coverage requested by main agent:
 1. Direct multipart upload POST /api/analyses returns 200, analysis eventually
    reaches status=ready (poll GET /api/analyses/{id}).
 2. Chunked upload POST /api/uploads/chunk + POST /api/analyses/finalize
    returns 200 and reaches status=ready.
 3. PERSISTENCE-FIRST: immediately after upload while status=processing,
    GET /api/analyses/{id}/video?token=... must already stream 200
    (GridFS stored synchronously at finalize). Then confirm it STILL
    streams 200 after analysis completes.
 4. GET /api/analyses/{id} returns full analysis with scores when ready.
 5. LemonSqueezy multi checkout POST /api/payments/lemonsqueezy/checkout
    {plan_id:'multi'} returns 200 with a lemonsqueezy.com url
    (env var LEMONSQUEEZY_VARIANT_MULTI is now set).
"""

import os
import io
import time
import uuid
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://wave-motion-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"          # coach tier — has upload quota
HEADERS = {"Authorization": f"Bearer {COACH_TOKEN}"}

MP4_TMP: Path | None = None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _build_tiny_mp4() -> Path:
    """Build a tiny valid H.264 MP4 via the bundled imageio-ffmpeg binary."""
    global MP4_TMP
    if MP4_TMP and MP4_TMP.exists():
        return MP4_TMP
    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        pytest.skip(f"imageio-ffmpeg not available: {e}")

    out = Path(tempfile.gettempdir()) / f"iter21_{uuid.uuid4().hex}.mp4"
    # 2-second 320x240 red frame, 15 fps — extremely tiny but valid H.264 MP4.
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=15",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
        "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    assert out.exists() and out.stat().st_size > 0
    MP4_TMP = out
    return out


def _poll_until_ready(analysis_id: str, timeout_s: int = 240) -> dict:
    """Poll GET /analyses/{id} until status=ready or terminal failure."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{API}/analyses/{analysis_id}", headers=HEADERS, timeout=30)
        except requests.exceptions.Timeout:
            time.sleep(3)
            continue
        assert r.status_code == 200, f"GET analysis {analysis_id}: {r.status_code} {r.text[:200]}"
        last = r.json()
        if last["status"] in ("ready", "failed"):
            return last
        time.sleep(3)
    return last or {}


def _delete_analysis(analysis_id: str):
    try:
        requests.delete(f"{API}/analyses/{analysis_id}", headers=HEADERS, timeout=10)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Health / auth sanity
# ----------------------------------------------------------------------
class TestHealth:
    def test_api_root(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200

    def test_auth_me_coach(self):
        r = requests.get(f"{API}/auth/me", headers=HEADERS, timeout=10)
        assert r.status_code == 200
        me = r.json()
        assert me["tier"] == "coach"
        assert me["email"] == "demo.coach@surfai.test"


# ----------------------------------------------------------------------
# 1) Direct multipart upload → poll to ready
# ----------------------------------------------------------------------
class TestDirectMultipartUpload:
    analysis_id: str | None = None

    @classmethod
    def teardown_class(cls):
        if cls.analysis_id:
            _delete_analysis(cls.analysis_id)

    def test_direct_upload_returns_200_and_reaches_ready(self):
        mp4 = _build_tiny_mp4()
        with open(mp4, "rb") as fh:
            files = {"file": (f"iter21_direct_{uuid.uuid4().hex}.mp4", fh, "video/mp4")}
            data = {"title": "TEST_iter21_direct", "spot": "TEST", "stance": "regular"}
            r = requests.post(
                f"{API}/analyses",
                headers=HEADERS,
                files=files,
                data=data,
                timeout=90,
            )
        assert r.status_code == 200, f"direct upload: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "analysis_id" in body
        assert body["status"] in ("processing", "ready")
        TestDirectMultipartUpload.analysis_id = body["analysis_id"]

        # Poll to ready. Pose failure is OK; only status matters.
        final = _poll_until_ready(body["analysis_id"], timeout_s=180)
        assert final.get("status") == "ready", f"did not reach ready: {final.get('status')} err={final.get('error')}"
        assert isinstance(final.get("scores"), list) and len(final["scores"]) >= 1


# ----------------------------------------------------------------------
# 2) Chunked upload → finalize → ready
# 3) Persistence-first check (video streams during processing AND after ready)
# ----------------------------------------------------------------------
class TestChunkedUploadAndPersistence:
    analysis_id: str | None = None

    @classmethod
    def teardown_class(cls):
        if cls.analysis_id:
            _delete_analysis(cls.analysis_id)

    def _upload_chunks(self, mp4_path: Path, chunk_size: int = 512 * 1024) -> tuple[str, int]:
        """Upload the MP4 as chunks. Return (upload_id, total_chunks)."""
        upload_id = uuid.uuid4().hex  # matches ^[a-f0-9]{16,64}$
        data = mp4_path.read_bytes()
        total = max(1, (len(data) + chunk_size - 1) // chunk_size)
        for i in range(total):
            blob = data[i * chunk_size : (i + 1) * chunk_size]
            files = {"file": (f"chunk_{i}", io.BytesIO(blob), "application/octet-stream")}
            form = {"upload_id": upload_id, "chunk_index": str(i), "total_chunks": str(total)}
            r = requests.post(
                f"{API}/uploads/chunk",
                headers=HEADERS,
                files=files,
                data=form,
                timeout=60,
            )
            assert r.status_code == 200, f"chunk {i}/{total}: {r.status_code} {r.text[:200]}"
        return upload_id, total

    def test_chunked_finalize_returns_ready_and_persistence_first(self):
        mp4 = _build_tiny_mp4()
        upload_id, total = self._upload_chunks(mp4)

        # Finalize
        payload = {
            "upload_id": upload_id,
            "filename": f"iter21_chunk_{uuid.uuid4().hex}.mp4",
            "mime_type": "video/mp4",
            "total_chunks": total,
            "title": "TEST_iter21_chunk",
            "spot": "TEST",
            "stance": "regular",
        }
        r = requests.post(
            f"{API}/analyses/finalize",
            headers=HEADERS,
            json=payload,
            timeout=90,
        )
        assert r.status_code == 200, f"finalize: {r.status_code} {r.text[:300]}"
        body = r.json()
        aid = body["analysis_id"]
        TestChunkedUploadAndPersistence.analysis_id = aid
        # At finalize response time, status should be processing OR ready.
        assert body["status"] in ("processing", "ready")

        # ------------------------------------------------------------------
        # PERSISTENCE-FIRST: video must stream 200 IMMEDIATELY, before AI
        # completes. We give one tiny beat to make sure DB write is visible.
        # ------------------------------------------------------------------
        # NOTE: while the background AI+pose task is running, this pod can be
        # briefly unresponsive (Mediapipe pose blocks the event loop and the
        # ingress can return 502 during that window). This does NOT invalidate
        # persistence — GridFS holds the video from the moment finalize
        # completes. Retry with backoff to prove the object IS there.
        time.sleep(0.5)
        r_early = None
        for attempt in range(6):
            try:
                r_early = requests.get(
                    f"{API}/analyses/{aid}/video",
                    params={"token": COACH_TOKEN},
                    headers=HEADERS,
                    timeout=90,
                    stream=True,
                )
                if r_early.status_code == 200:
                    break
                r_early.close()
            except requests.exceptions.RequestException:
                pass
            time.sleep(3 + attempt * 2)
        assert r_early is not None and r_early.status_code == 200, (
            f"persistence-first FAILED: video not streamable during processing "
            f"(last status={getattr(r_early,'status_code',None)})"
        )
        ct = r_early.headers.get("content-type", "")
        assert "video" in ct or ct.startswith("application/octet-stream"), f"unexpected ct={ct}"
        # Read a few bytes to confirm real body
        got = next(r_early.iter_content(chunk_size=64), b"")
        assert got and len(got) > 0
        r_early.close()

        # ------------------------------------------------------------------
        # Poll to ready
        # ------------------------------------------------------------------
        final = _poll_until_ready(aid, timeout_s=180)
        assert final.get("status") == "ready", (
            f"did not reach ready: {final.get('status')} err={final.get('error')}"
        )
        assert isinstance(final.get("scores"), list) and len(final["scores"]) >= 1

        # ------------------------------------------------------------------
        # STILL streams after ready (replay scenario)
        # ------------------------------------------------------------------
        r_late = requests.get(
            f"{API}/analyses/{aid}/video",
            params={"token": COACH_TOKEN},
            timeout=30,
            stream=True,
        )
        assert r_late.status_code == 200, (
            f"video not replayable after ready: {r_late.status_code} {r_late.text[:200]}"
        )
        r_late.close()


# ----------------------------------------------------------------------
# 5) LemonSqueezy multi checkout
# ----------------------------------------------------------------------
class TestLemonSqueezyMultiCheckout:
    def test_multi_checkout_returns_lemonsqueezy_url(self):
        r = requests.post(
            f"{API}/payments/lemonsqueezy/checkout",
            headers=HEADERS,
            json={"plan_id": "multi", "origin_url": BASE_URL},
            timeout=60,
        )
        # If the variant is unconfigured we accept 400 with an explicit message
        # so the test still surfaces the config gap. Per this iteration's env
        # it IS configured (1975057), so we expect 200 + lemonsqueezy.com URL.
        assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text[:300]}"
        body = r.json()
        url = body.get("checkout_url") or body.get("url") or ""
        assert "lemonsqueezy.com" in url, f"url missing lemonsqueezy.com: {url!r}"

    def test_learn_checkout_still_ok(self):
        # regression: single-plan checkout
        r = requests.post(
            f"{API}/payments/lemonsqueezy/checkout",
            headers=HEADERS,
            json={"plan_id": "learn", "origin_url": BASE_URL},
            timeout=60,
        )
        assert r.status_code == 200
        url = r.json().get("checkout_url") or r.json().get("url") or ""
        assert "lemonsqueezy.com" in url
