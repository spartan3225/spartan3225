"""
Iteration 10 — verify ffmpeg MOV->MP4 conversion moved OUT of HTTP request
into the background task. Both POST /api/analyses (legacy) and POST
/api/analyses/finalize (chunked) must return in <10s for .mov filenames,
and the background task must eventually update the doc (typically to
'failed' since we use fake bytes — the point is the HTTP response is fast
and the server doesn't crash).
"""
import base64
import os
import secrets
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
COACH_TOKEN = "demo_coach_token"           # unlimited quota
AUTH = {"Authorization": f"Bearer {COACH_TOKEN}"}

# Track created analysis IDs so we can clean up
_created_analysis_ids: list[str] = []


def _new_upload_id() -> str:
    return secrets.token_hex(16)  # 32 hex chars -> matches ^[a-f0-9]{16,64}$


# ---------- 1. legacy POST /api/analyses with .mov filename returns fast ----------
class TestLegacyMovFastResponse:
    def test_legacy_mov_upload_returns_fast_processing(self):
        """Upload ~1MB fake .mov via legacy /api/analyses — must return <10s
        with status='processing' (no inline ffmpeg)."""
        fake_bytes = b"\x00\x00\x00\x20ftypqt  " + os.urandom(1_000_000)  # ~1MB
        files = {"file": ("clip.mov", fake_bytes, "video/quicktime")}

        t0 = time.time()
        r = requests.post(f"{API}/analyses", headers=AUTH, files=files, timeout=30)
        elapsed = time.time() - t0
        print(f"[legacy .mov] elapsed={elapsed:.2f}s status={r.status_code}")

        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        assert elapsed < 10, f"HTTP response too slow ({elapsed:.2f}s) — ffmpeg likely still inline"
        body = r.json()
        assert body["status"] == "processing", f"expected processing, got {body.get('status')}"
        assert body["analysis_id"].startswith("ana_")
        _created_analysis_ids.append(body["analysis_id"])

    def test_legacy_mov_bg_task_updates_doc(self):
        """After the fast return, background task should mark this analysis
        'failed' (fake bytes -> ffmpeg fails or AI fails). Confirms background
        pipeline ran & updated the doc without crashing the server."""
        assert _created_analysis_ids, "previous test must create an analysis"
        analysis_id = _created_analysis_ids[-1]

        final_status = None
        for i in range(30):  # ~60s max
            r = requests.get(f"{API}/analyses/{analysis_id}", headers=AUTH, timeout=15)
            assert r.status_code == 200, r.text[:200]
            final_status = r.json().get("status")
            if final_status in ("failed", "ready"):
                print(f"[legacy .mov] bg task settled after {i*2}s -> status={final_status}")
                break
            time.sleep(2)

        assert final_status in ("failed", "ready"), (
            f"background task never settled — still status={final_status}. "
            f"Suggests the bg task crashed or never ran."
        )


# ---------- 2. chunked flow with .mov filename returns fast ----------
class TestChunkedMovFastResponse:
    upload_id: str = ""
    total_chunks: int = 2
    chunk_size: int = 3 * 1024 * 1024  # 3MB

    def test_upload_two_3mb_chunks(self):
        TestChunkedMovFastResponse.upload_id = _new_upload_id()
        for i in range(self.total_chunks):
            data = os.urandom(self.chunk_size)
            files = {"file": (f"c{i}.bin", data, "application/octet-stream")}
            form = {
                "upload_id": self.upload_id,
                "chunk_index": str(i),
                "total_chunks": str(self.total_chunks),
            }
            r = requests.post(
                f"{API}/uploads/chunk", headers=AUTH, files=files, data=form, timeout=60
            )
            assert r.status_code == 200, f"chunk {i} failed: {r.status_code} {r.text[:200]}"
            body = r.json()
            assert body["received"] == i + 1

    def test_finalize_mov_returns_fast_processing(self):
        assert self.upload_id, "upload_id must be set from previous test"
        payload = {
            "upload_id": self.upload_id,
            "filename": "myclip.mov",
            "mime_type": "video/quicktime",
            "total_chunks": self.total_chunks,
        }
        t0 = time.time()
        r = requests.post(
            f"{API}/analyses/finalize", headers=AUTH, json=payload, timeout=30
        )
        elapsed = time.time() - t0
        print(f"[chunked .mov finalize] elapsed={elapsed:.2f}s status={r.status_code}")

        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        assert elapsed < 10, f"finalize too slow ({elapsed:.2f}s) — ffmpeg likely still inline"
        body = r.json()
        assert body["status"] == "processing"
        assert body["analysis_id"].startswith("ana_")
        _created_analysis_ids.append(body["analysis_id"])

    def test_finalize_bg_task_updates_video_path(self):
        """Wait for bg task; verify the doc got video_path updated by conversion
        step (or remained pointing at original file after ffmpeg fell back).
        Either way, no crash and status must settle."""
        assert _created_analysis_ids
        analysis_id = _created_analysis_ids[-1]

        final_status = None
        for i in range(30):  # ~60s
            r = requests.get(f"{API}/analyses/{analysis_id}", headers=AUTH, timeout=15)
            assert r.status_code == 200
            final_status = r.json().get("status")
            if final_status in ("failed", "ready"):
                print(f"[chunked .mov] bg settled after {i*2}s -> status={final_status}")
                break
            time.sleep(2)
        assert final_status in ("failed", "ready"), f"bg task never settled: {final_status}"


# ---------- 3. regression: finalize validations still work ----------
class TestFinalizeValidations:
    def test_finalize_unknown_upload_id_returns_400(self):
        payload = {
            "upload_id": _new_upload_id(),  # never uploaded to
            "filename": "x.mp4",
            "mime_type": "video/mp4",
            "total_chunks": 1,
        }
        r = requests.post(f"{API}/analyses/finalize", headers=AUTH, json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        assert "not found" in r.text.lower() or "upload" in r.text.lower()

    def test_finalize_incomplete_chunks_returns_400(self):
        upload_id = _new_upload_id()
        # upload only 1 of 3 chunks
        data = os.urandom(1024)
        files = {"file": ("c0.bin", data, "application/octet-stream")}
        form = {"upload_id": upload_id, "chunk_index": "0", "total_chunks": "3"}
        r = requests.post(f"{API}/uploads/chunk", headers=AUTH, files=files, data=form, timeout=30)
        assert r.status_code == 200

        payload = {
            "upload_id": upload_id,
            "filename": "x.mp4",
            "mime_type": "video/mp4",
            "total_chunks": 3,
        }
        r = requests.post(f"{API}/analyses/finalize", headers=AUTH, json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        assert "incomplete" in r.text.lower() or "chunk" in r.text.lower()


# ---------- 4. regression: /api/plans + static site ----------
class TestBasicRegressions:
    def test_plans_endpoint_ok(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert isinstance(r.json(), (list, dict))

    def test_static_web_root_html(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200, r.text[:200]
        ctype = r.headers.get("content-type", "")
        assert "text/html" in ctype.lower(), f"expected html, got {ctype}"


# ---------- 5. cleanup: delete created analyses + files ----------
@pytest.fixture(scope="module", autouse=True)
def _cleanup_created_analyses():
    yield
    # remove any test analyses from DB and disk
    if not _created_analysis_ids:
        return
    print(f"\n[cleanup] removing {len(_created_analysis_ids)} test analyses")
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        client = MongoClient(mongo_url)
        db = client[db_name]
        docs = list(db.analyses.find({"analysis_id": {"$in": _created_analysis_ids}}))
        for d in docs:
            vp = d.get("video_path")
            if vp:
                try:
                    p = Path(vp)
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    print(f"  failed to unlink {vp}: {e}")
        db.analyses.delete_many({"analysis_id": {"$in": _created_analysis_ids}})
        client.close()
    except Exception as e:
        print(f"[cleanup] error: {e}")
