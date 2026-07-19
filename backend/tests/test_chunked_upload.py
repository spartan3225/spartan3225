"""
Backend tests for the chunked upload fix (Cloudflare 520 bug).

Covers:
- Happy path: multi-chunk multipart 'file' upload -> finalize -> AnalysisOut
- chunk_b64 variant
- Validation: bad upload_id, incomplete finalize, unknown upload_id, unauth
- Regression: legacy single POST /api/analyses still works
- Quota enforcement on the free tier via finalize
"""
import base64
import os
import secrets
import time
from pathlib import Path

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"   # unlimited quota
DEMO_TOKEN = "demo_token_active"   # free tier (1 lifetime)

# server.py: UPLOAD_DIR = ROOT_DIR/'uploads'/'videos'; CHUNKS_DIR = ROOT_DIR/'uploads'/'chunks'
UPLOAD_DIR = Path("/app/backend/uploads/videos")
CHUNKS_DIR = Path("/app/backend/uploads/chunks")


def _coach_headers():
    return {"Authorization": f"Bearer {COACH_TOKEN}"}


def _demo_headers():
    return {"Authorization": f"Bearer {DEMO_TOKEN}"}


def _cleanup_analysis(analysis_id: str, user_id: str):
    """Delete DB doc + on-disk video so quota/disk stays clean."""
    try:
        import subprocess
        subprocess.run(
            ["mongosh", "--quiet", "--eval",
             f"use('test_database'); db.analyses.deleteMany({{analysis_id:'{analysis_id}'}});"],
            check=False, capture_output=True, timeout=10,
        )
    except Exception:
        pass
    for ext in ("mp4", "mov", "m4v", "webm", "avi"):
        p = UPLOAD_DIR / user_id / f"{analysis_id}.{ext}"
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 1. Chunked happy path (coach user, ~9MB fake mp4, 3 x 3MB chunks)
# ---------------------------------------------------------------------------
class TestChunkedHappyPath:
    def test_chunked_upload_and_finalize(self):
        upload_id = secrets.token_hex(16)  # 32 hex chars -> matches ^[a-f0-9]{16,64}$
        chunk_size = 3 * 1024 * 1024
        total_chunks = 3
        header = b"\x00\x00\x00\x18ftypmp42"  # 12 bytes
        payload = header + os.urandom(chunk_size * total_chunks - len(header))
        assert len(payload) == chunk_size * total_chunks

        for i in range(total_chunks):
            piece = payload[i * chunk_size:(i + 1) * chunk_size]
            r = requests.post(
                f"{API}/uploads/chunk",
                headers=_coach_headers(),
                data={"upload_id": upload_id,
                      "chunk_index": str(i),
                      "total_chunks": str(total_chunks)},
                files={"file": ("chunk", piece, "application/octet-stream")},
                timeout=60,
            )
            assert r.status_code == 200, f"chunk {i} -> {r.status_code} {r.text}"
            j = r.json()
            assert j["received"] == i + 1
            assert j["total"] == total_chunks

        # Finalize
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_coach_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id,
                  "filename": "test_surf.mp4",
                  "mime_type": "video/mp4",
                  "total_chunks": total_chunks},
            timeout=60,
        )
        assert r.status_code == 200, f"finalize -> {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "processing"
        analysis_id = data.get("id") or data.get("analysis_id")
        assert analysis_id and analysis_id.startswith("ana_")

        # Assembled file exists with correct size
        assembled = UPLOAD_DIR / "user_coach_67890" / f"{analysis_id}.mp4"
        # allow a short delay for filesystem visibility
        for _ in range(10):
            if assembled.exists():
                break
            time.sleep(0.2)
        assert assembled.exists(), f"assembled file missing at {assembled}"
        # Size may be either the original (before ffmpeg) OR the transcoded MP4.
        # If ffmpeg re-encoded then size will differ. We accept either.
        size = assembled.stat().st_size
        assert size > 0

        # Chunk dir deleted
        chunk_dir = CHUNKS_DIR / "user_coach_67890" / upload_id
        assert not chunk_dir.exists(), f"chunk dir still present: {chunk_dir}"

        # Cleanup
        _cleanup_analysis(analysis_id, "user_coach_67890")


# ---------------------------------------------------------------------------
# 2. chunk_b64 variant
# ---------------------------------------------------------------------------
class TestChunkB64Variant:
    def test_chunk_via_base64_field(self):
        upload_id = secrets.token_hex(16)
        blob = b"hello-surf-" + os.urandom(1024)
        b64 = base64.b64encode(blob).decode()
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_coach_headers(),
            data={"upload_id": upload_id,
                  "chunk_index": "0",
                  "total_chunks": "1",
                  "chunk_b64": b64},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["received"] == 1 and j["total"] == 1

        # Clean up the orphan chunk dir
        try:
            import shutil
            shutil.rmtree(CHUNKS_DIR / "user_coach_67890" / upload_id, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 3. Validation & auth
# ---------------------------------------------------------------------------
class TestValidation:
    def test_bad_upload_id_path_traversal(self):
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_coach_headers(),
            data={"upload_id": "../evil",
                  "chunk_index": "0",
                  "total_chunks": "1"},
            files={"file": ("c", b"x", "application/octet-stream")},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_bad_upload_id_wrong_charset(self):
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_coach_headers(),
            data={"upload_id": "XYZ",
                  "chunk_index": "0",
                  "total_chunks": "1"},
            files={"file": ("c", b"x", "application/octet-stream")},
            timeout=15,
        )
        assert r.status_code == 400

    def test_unauthenticated_chunk(self):
        r = requests.post(
            f"{API}/uploads/chunk",
            data={"upload_id": secrets.token_hex(16),
                  "chunk_index": "0",
                  "total_chunks": "1"},
            files={"file": ("c", b"x", "application/octet-stream")},
            timeout=15,
        )
        assert r.status_code == 401, r.text

    def test_finalize_unknown_upload_id(self):
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_coach_headers(), "Content-Type": "application/json"},
            json={"upload_id": secrets.token_hex(16),
                  "filename": "x.mp4",
                  "mime_type": "video/mp4",
                  "total_chunks": 1},
            timeout=15,
        )
        assert r.status_code == 400
        assert "not found" in r.text.lower() or "incomplete" in r.text.lower()

    def test_finalize_incomplete_chunks(self):
        upload_id = secrets.token_hex(16)
        # Send 1 of 3
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_coach_headers(),
            data={"upload_id": upload_id,
                  "chunk_index": "0",
                  "total_chunks": "3"},
            files={"file": ("c", os.urandom(1024), "application/octet-stream")},
            timeout=15,
        )
        assert r.status_code == 200

        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_coach_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id,
                  "filename": "x.mp4",
                  "mime_type": "video/mp4",
                  "total_chunks": 3},
            timeout=15,
        )
        assert r.status_code == 400
        assert "incomplete" in r.text.lower()

        # Cleanup orphan
        import shutil
        shutil.rmtree(CHUNKS_DIR / "user_coach_67890" / upload_id, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Regression: legacy single-request /api/analyses still works with small file
# ---------------------------------------------------------------------------
class TestLegacyEndpoint:
    def test_legacy_small_upload(self):
        payload = b"\x00\x00\x00\x18ftypmp42" + os.urandom(64 * 1024)  # ~64KB
        r = requests.post(
            f"{API}/analyses",
            headers=_coach_headers(),
            files={"file": ("legacy.mp4", payload, "video/mp4")},
            timeout=60,
        )
        assert r.status_code == 200, f"legacy -> {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "processing"
        analysis_id = data.get("id") or data.get("analysis_id")
        assert analysis_id and analysis_id.startswith("ana_")

        _cleanup_analysis(analysis_id, "user_coach_67890")


# ---------------------------------------------------------------------------
# 5. Quota enforcement: free tier that already has 1 non-failed analysis -> 402
# ---------------------------------------------------------------------------
class TestQuota:
    def test_free_tier_quota_on_finalize(self):
        # Seed one completed analysis for demo user so lifetime quota is used.
        import subprocess
        seed = """
use('test_database');
db.analyses.deleteMany({user_id:'user_demo_12345', analysis_id:{$regex:'^ana_TEST_'}});
db.analyses.insertOne({
  analysis_id:'ana_TEST_quota01',
  user_id:'user_demo_12345',
  status:'completed',
  created_at:new Date(),
  filename:'seed.mp4',
});
"""
        subprocess.run(["mongosh", "--quiet", "--eval", seed],
                       check=False, capture_output=True, timeout=10)

        # Upload a chunk, then finalize -> expect 402
        upload_id = secrets.token_hex(16)
        r = requests.post(
            f"{API}/uploads/chunk",
            headers=_demo_headers(),
            data={"upload_id": upload_id,
                  "chunk_index": "0",
                  "total_chunks": "1"},
            files={"file": ("c", os.urandom(2048), "application/octet-stream")},
            timeout=15,
        )
        assert r.status_code == 200

        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_demo_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id,
                  "filename": "x.mp4",
                  "mime_type": "video/mp4",
                  "total_chunks": 1},
            timeout=15,
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text}"
        assert "free" in r.text.lower() or "upgrade" in r.text.lower()

        # Cleanup: seed doc + orphan chunk dir + assembled file (none in this case)
        subprocess.run(["mongosh", "--quiet", "--eval",
                        "use('test_database'); db.analyses.deleteMany({analysis_id:'ana_TEST_quota01'});"],
                       check=False, capture_output=True, timeout=10)
        import shutil
        shutil.rmtree(CHUNKS_DIR / "user_demo_12345" / upload_id, ignore_errors=True)
