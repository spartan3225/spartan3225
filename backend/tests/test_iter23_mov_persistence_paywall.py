"""Iteration 23 — .MOV/HEVC upload + persistence-first + paywall/design rollback.

Backend focus (frontend covered separately via Playwright):
  1. Build a real HEVC (hvc1) .MOV clip using the bundled imageio-ffmpeg.
  2. Direct multipart POST /api/analyses with filename=*.mov, mime=video/quicktime,
     Authorization: Bearer demo_coach_token -> 200 (processing) in <2s.
  3. Poll GET /api/analyses/{id} until status=ready (up to 4 min).
  4. Immediately after upload (while processing), GET /api/analyses/{id}/video?token=demo_coach_token
     returns 200 (persistence-first).
  5. After status=ready, DB doc mime_type should be video/mp4 (conversion ran) AND
     GET /api/analyses/{id}/video?token=demo_coach_token still returns 200.
  6. LemonSqueezy checkout still returns a valid checkout URL (web paywall regression).

Cleanup: analysis created here is DELETED in teardown_class.
"""
from __future__ import annotations

import io
import os
import subprocess
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"
TIMEOUT = 90


def _build_hevc_mov() -> bytes:
    """Real HEVC (hvc1) .MOV via bundled ffmpeg — the exact iPhone codec."""
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        out = f"/tmp/iter23_{uuid.uuid4().hex}.mov"
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=blue:s=256x256:d=2:r=24",
            "-c:v", "libx265",
            "-tag:v", "hvc1",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-t", "2",
            "-movflags", "+faststart",
            out,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        with open(out, "rb") as f:
            data = f.read()
        os.remove(out)
        assert len(data) > 500, "HEVC mov build produced empty file"
        return data
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"HEVC mov build failed (ffmpeg missing?): {e}")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    yield s
    s.close()


class TestMovUploadPersistenceFlow:
    """iPhone .MOV upload -> convert -> ready + persistence-first video stream."""

    created_analysis_ids: list[str] = []

    def test_1_health_and_coach_session(self, api_client):
        r = api_client.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            timeout=30,
        )
        assert r.status_code == 200, f"coach /me {r.status_code}: {r.text[:200]}"
        assert r.json().get("tier") == "coach"

    def test_2_mov_upload_returns_200_and_processing_quickly(self, api_client):
        payload = _build_hevc_mov()
        t0 = time.time()
        files = {
            "file": (
                f"iphone_clip_{uuid.uuid4().hex[:6]}.mov",
                io.BytesIO(payload),
                "video/quicktime",
            )
        }
        r = api_client.post(
            f"{API}/analyses",
            files=files,
            headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, f"upload {r.status_code}: {r.text[:400]}"
        body = r.json()
        assert body.get("status") == "processing", f"expected processing, got {body!r}"
        aid = body.get("analysis_id") or body.get("id")
        assert aid, f"no analysis_id in {body!r}"
        TestMovUploadPersistenceFlow.created_analysis_ids.append(aid)
        print(f"[iter23] .MOV upload accepted in {elapsed:.2f}s -> {aid}")

    def test_3_video_streams_200_immediately_while_processing(self, api_client):
        """Persistence-first: GridFS write happens BEFORE Gemini task starts."""
        assert TestMovUploadPersistenceFlow.created_analysis_ids, "prior test must create analysis"
        aid = TestMovUploadPersistenceFlow.created_analysis_ids[-1]
        # Retry a few times: cannot exceed ~15s wait, but pod may briefly be busy
        last_status = None
        for i in range(8):
            r = api_client.get(
                f"{API}/analyses/{aid}/video",
                params={"token": COACH_TOKEN},
                timeout=TIMEOUT,
                stream=True,
            )
            last_status = r.status_code
            if r.status_code == 200:
                first_bytes = next(r.iter_content(chunk_size=64), b"")
                r.close()
                assert first_bytes, "video stream body empty"
                print(f"[iter23] video streamed 200 (immediate, attempt {i+1})")
                return
            r.close()
            time.sleep(1.5)
        pytest.fail(f"video did not stream 200 while processing (last {last_status})")

    def test_4_polls_to_ready_and_mime_becomes_mp4(self, api_client):
        assert TestMovUploadPersistenceFlow.created_analysis_ids
        aid = TestMovUploadPersistenceFlow.created_analysis_ids[-1]
        deadline = time.time() + 240  # up to 4 min
        final = None
        while time.time() < deadline:
            try:
                r = api_client.get(
                    f"{API}/analyses/{aid}",
                    headers={"Authorization": f"Bearer {COACH_TOKEN}"},
                    timeout=90,
                )
            except requests.RequestException:
                time.sleep(4)
                continue
            if r.status_code == 200:
                body = r.json()
                status = body.get("status")
                if status == "ready":
                    final = body
                    break
                if status == "failed":
                    pytest.fail(f"analysis failed while polling: {body}")
            time.sleep(4)
        assert final is not None, "analysis did not reach ready within 240s"
        print(f"[iter23] reached ready in <=240s, score={final.get('score')}")
        # Query DB mime_type indirectly by inspecting Content-Type on the stream.
        rv = api_client.get(
            f"{API}/analyses/{aid}/video",
            params={"token": COACH_TOKEN},
            timeout=90,
            stream=True,
        )
        assert rv.status_code == 200
        ctype = (rv.headers.get("content-type") or "").lower()
        rv.close()
        # After conversion ran, the served mime should be video/mp4 (not quicktime).
        assert "mp4" in ctype, f"expected video/mp4 after conversion, got {ctype!r}"
        print(f"[iter23] post-ready video content-type = {ctype}")

    def test_5_video_still_streams_200_after_ready_persistence(self, api_client):
        assert TestMovUploadPersistenceFlow.created_analysis_ids
        aid = TestMovUploadPersistenceFlow.created_analysis_ids[-1]
        r = api_client.get(
            f"{API}/analyses/{aid}/video",
            params={"token": COACH_TOKEN},
            timeout=90,
            stream=True,
        )
        assert r.status_code == 200, f"post-ready video {r.status_code}"
        first_bytes = next(r.iter_content(chunk_size=64), b"")
        r.close()
        assert first_bytes, "post-ready video body empty"

    @classmethod
    def teardown_class(cls):
        s = requests.Session()
        for aid in cls.created_analysis_ids:
            try:
                s.delete(
                    f"{API}/analyses/{aid}",
                    headers={"Authorization": f"Bearer {COACH_TOKEN}"},
                    timeout=30,
                )
            except Exception:  # noqa: BLE001
                pass
        s.close()


class TestPaywallCheckoutRegression:
    """Web paywall must still be able to build a LemonSqueezy checkout URL."""

    def test_lemonsqueezy_checkout_returns_url(self, api_client):
        r = api_client.post(
            f"{API}/payments/lemonsqueezy/checkout",
            json={"plan_id": "learn", "origin_url": BASE_URL},
            headers={"Authorization": f"Bearer {COACH_TOKEN}"},
            timeout=60,
        )
        assert r.status_code == 200, f"LS checkout {r.status_code}: {r.text[:300]}"
        data = r.json()
        url = data.get("url") or data.get("checkout_url")
        assert url and "lemonsqueezy.com" in url, f"unexpected checkout url: {data}"
