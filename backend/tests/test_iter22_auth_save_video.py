"""Iteration 22 — email auth lifecycle + save-video sanity + session indexes.

Focus for this iteration:
  1. POST /api/auth/register + /api/auth/me + /api/auth/logout + /api/auth/me lifecycle.
  2. POST /api/auth/login for the same account.
  3. Direct multipart POST /api/analyses with demo_coach_token reaches ready + video streams 200.
  4. Verify user_sessions indexes exist (session_token unique, expires_at TTL).

Cleanup: any users/analyses/sessions created here are removed in teardown_class.
"""
from __future__ import annotations

import io
import os
import random
import string
import struct
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"
TIMEOUT = 60


def _rand_email() -> str:
    tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"qa_iter22_{tag}@surfcoach23.com"


def _tiny_mp4_bytes() -> bytes:
    """Build a tiny valid H.264/mp4 clip via imageio-ffmpeg on a black frame."""
    try:
        import imageio_ffmpeg
        import subprocess
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        out = f"/tmp/iter22_{uuid.uuid4().hex}.mp4"
        # 1s black clip @ 24fps, 128x128
        cmd = [
            ffmpeg, "-y", "-f", "lavfi", "-i", "color=black:s=128x128:d=1:r=24",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", "1", out,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        with open(out, "rb") as f:
            data = f.read()
        os.remove(out)
        return data
    except Exception as e:
        pytest.skip(f"ffmpeg not available for tiny mp4 build: {e}")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    yield s
    s.close()


class TestEmailAuthLifecycle:
    """Register -> me(200) -> logout -> me(401), then login on same account."""

    created_emails: list[str] = []

    def test_register_then_me_then_logout_then_me_401(self, api_client):
        email = _rand_email()
        pwd = "TestPass123!"
        TestEmailAuthLifecycle.created_emails.append(email)

        # Register
        r = api_client.post(
            f"{API}/auth/register",
            json={"email": email, "password": pwd, "name": "QA Iter22"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"register {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "session_token" in body and body["session_token"]
        assert body["user"]["email"] == email
        token = body["session_token"]

        # /auth/me with bearer
        r = api_client.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"me post-register {r.status_code}: {r.text[:200]}"
        me = r.json()
        assert me["email"] == email

        # logout
        r = api_client.post(
            f"{API}/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"logout {r.status_code}: {r.text[:200]}"

        # /auth/me now should 401
        r = api_client.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"me post-logout expected 401 got {r.status_code}"

    def test_login_same_account(self, api_client):
        assert TestEmailAuthLifecycle.created_emails, "prev test must have created one"
        email = TestEmailAuthLifecycle.created_emails[-1]
        pwd = "TestPass123!"
        r = api_client.post(
            f"{API}/auth/login",
            json={"email": email, "password": pwd},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"login {r.status_code}: {r.text[:200]}"
        tok = r.json()["session_token"]
        assert tok
        # Confirm the token works
        r = api_client.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_login_bad_password_is_401_or_400(self, api_client):
        assert TestEmailAuthLifecycle.created_emails
        email = TestEmailAuthLifecycle.created_emails[-1]
        r = api_client.post(
            f"{API}/auth/login",
            json={"email": email, "password": "WrongPass000!"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 401), f"bad-pw expected 401 got {r.status_code}"

    @classmethod
    def teardown_class(cls):
        # Best-effort cleanup: log in and DELETE /api/auth/account for each created email
        for email in cls.created_emails:
            try:
                r = requests.post(
                    f"{API}/auth/login",
                    json={"email": email, "password": "TestPass123!"},
                    timeout=TIMEOUT,
                )
                if r.status_code == 200:
                    tok = r.json()["session_token"]
                    requests.delete(
                        f"{API}/auth/account",
                        headers={"Authorization": f"Bearer {tok}"},
                        timeout=TIMEOUT,
                    )
            except Exception:
                pass


class TestUploadAndVideoStream:
    """Small MP4 upload with demo_coach_token reaches status=ready and video streams."""

    created_analysis_ids: list[str] = []

    def test_upload_small_mp4_reaches_ready_and_streams(self, api_client):
        mp4 = _tiny_mp4_bytes()
        files = {"file": ("iter22.mp4", io.BytesIO(mp4), "video/mp4")}
        headers = {"Authorization": f"Bearer {COACH_TOKEN}"}
        t0 = time.time()
        r = api_client.post(f"{API}/analyses", files=files, headers=headers, timeout=90)
        assert r.status_code == 200, f"POST /api/analyses {r.status_code}: {r.text[:200]}"
        body = r.json()
        aid = body["analysis_id"]
        TestUploadAndVideoStream.created_analysis_ids.append(aid)
        assert body["status"] in ("processing", "ready"), body["status"]
        t_first = time.time() - t0
        assert t_first < 30, f"initial POST took {t_first:.1f}s — persistence-first broken?"

        # Persistence-first: video should stream 200 immediately (before ready).
        # NOTE (iter21 known perf): CPU-bound Mediapipe pose extraction can
        # briefly block the FastAPI event loop, so we retry with backoff.
        vr = None
        last = None
        for attempt in range(6):
            try:
                vr = api_client.get(
                    f"{API}/analyses/{aid}/video?token={COACH_TOKEN}",
                    timeout=90,
                    stream=True,
                )
                if vr.status_code == 200:
                    break
                last = f"HTTP {vr.status_code}"
                vr.close()
                vr = None
            except Exception as e:
                last = str(e)
            time.sleep(5 * (attempt + 1))
        assert vr is not None and vr.status_code == 200, f"immediate video stream failed: {last}"
        assert (vr.headers.get("Content-Type") or "").startswith("video/"), vr.headers
        # drain a byte
        first_chunk = next(vr.iter_content(1024), b"")
        assert first_chunk
        vr.close()

        # Poll to ready
        ready = False
        for _ in range(60):
            time.sleep(3)
            gr = api_client.get(
                f"{API}/analyses/{aid}",
                headers=headers,
                timeout=TIMEOUT,
            )
            if gr.status_code == 200 and gr.json().get("status") == "ready":
                ready = True
                break
        assert ready, f"analysis {aid} did not reach ready in ~180s"

        # After ready still streams
        vr = api_client.get(
            f"{API}/analyses/{aid}/video?token={COACH_TOKEN}",
            timeout=60,
            stream=True,
        )
        assert vr.status_code == 200
        vr.close()

    @classmethod
    def teardown_class(cls):
        for aid in cls.created_analysis_ids:
            try:
                requests.delete(
                    f"{API}/analyses/{aid}",
                    headers={"Authorization": f"Bearer {COACH_TOKEN}"},
                    timeout=TIMEOUT,
                )
            except Exception:
                pass


class TestSessionIndexes:
    """Best-effort: session_token unique + expires_at TTL index exists."""

    def test_indexes_exist(self):
        try:
            from pymongo import MongoClient
        except Exception:
            pytest.skip("pymongo not available")
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("mongo env not set")
        cli = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        try:
            info = cli[db_name]["user_sessions"].index_information()
        except Exception as e:
            pytest.skip(f"mongo unreachable: {e}")
        finally:
            cli.close()
        # session_token unique
        found_unique = any(
            "session_token" in [k for k, _ in v.get("key", [])] and v.get("unique")
            for v in info.values()
        )
        assert found_unique, f"no unique session_token index; got {list(info.keys())}"
        # expires_at TTL (expireAfterSeconds present)
        found_ttl = any(
            "expires_at" in [k for k, _ in v.get("key", [])]
            and "expireAfterSeconds" in v
            for v in info.values()
        )
        assert found_ttl, f"no TTL expires_at index; got {list(info.keys())}"
