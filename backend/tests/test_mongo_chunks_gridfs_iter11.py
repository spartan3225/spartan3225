"""
Iteration 11 backend tests — verifies the multi-replica bugfix:

 (1) Chunks are stored in MongoDB (db.upload_chunks) — shared by all replicas.
 (2) Finalize counts/reads chunks from Mongo, assembles to a local file, deletes chunks.
 (3) Videos are persisted to GridFS bucket 'videos' (filename=analysis_id) in the
     background task after ffmpeg conversion.
 (4) GET /api/analyses/{id}/video falls back to streaming from GridFS when the
     local file is missing (simulates a different pod).
 (5) Startup created TTL index (24h) on upload_chunks.created_at + unique compound
     index on (user_id, upload_id, chunk_index).

Regression:
 - Legacy POST /api/analyses still returns 200 processing fast (<10s).
 - /api/plans -> 200; / serves HTML.

All test data is cleaned up (analyses docs, local video files, upload_chunks
docs, GridFS videos.files/videos.chunks).
"""
import base64
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://wave-motion-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

COACH_TOKEN = "demo_coach_token"          # unlimited quota
COACH_USER_ID = "user_coach_67890"

UPLOAD_DIR = Path("/app/backend/uploads/videos")
CHUNKS_DIR = Path("/app/backend/uploads/chunks")

DB = "test_database"


def _mongo_eval(js: str, timeout: int = 15) -> str:
    """Run a mongosh eval and return stdout."""
    r = subprocess.run(
        ["mongosh", "--quiet", "--eval", f"use('{DB}'); {js}"],
        capture_output=True, timeout=timeout,
    )
    return (r.stdout or b"").decode("utf-8", "ignore")


def _headers():
    return {"Authorization": f"Bearer {COACH_TOKEN}"}


def _cleanup_analysis(analysis_id: str, user_id: str = COACH_USER_ID) -> None:
    """Delete DB doc + local videos + GridFS entries + orphan chunk docs."""
    try:
        _mongo_eval(
            f"db.analyses.deleteMany({{analysis_id:'{analysis_id}'}});"
            f"db.upload_chunks.deleteMany({{user_id:'{user_id}'}});"
            "var b = db.getSiblingDB('test_database');"
            f"b['videos.files'].find({{filename:'{analysis_id}'}}, {{_id:1}})"
            ".forEach(function(f){"
            f"  b['videos.chunks'].deleteMany({{files_id:f._id}});"
            f"  b['videos.files'].deleteOne({{_id:f._id}});"
            "});"
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


def _post_chunk(upload_id: str, idx: int, total: int, data: bytes,
                token: str = COACH_TOKEN, b64: bool = False, timeout: int = 60):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    form = {"upload_id": upload_id,
            "chunk_index": str(idx),
            "total_chunks": str(total)}
    files = None
    if b64:
        form["chunk_b64"] = base64.b64encode(data).decode()
    else:
        files = {"file": ("chunk", data, "application/octet-stream")}
    return requests.post(f"{API}/uploads/chunk", headers=headers,
                         data=form, files=files, timeout=timeout)


# ---------------------------------------------------------------------------
# 1. Chunked upload via Mongo (happy path)
# ---------------------------------------------------------------------------
class TestChunkedUploadMongo:
    """Upload 3 chunks (3MB each; middle chunk via chunk_b64) -> finalize."""

    def test_chunks_stored_in_mongo_and_finalize(self):
        upload_id = secrets.token_hex(16)
        chunk_size = 3 * 1024 * 1024
        total = 3
        # Build 3 distinct payload pieces so we can verify byte-for-byte assembly
        header = b"\x00\x00\x00\x18ftypmp42"
        pieces = [
            header + os.urandom(chunk_size - len(header)),
            os.urandom(chunk_size),
            os.urandom(chunk_size),
        ]
        expected_total_bytes = sum(len(p) for p in pieces)

        # POST 3 chunks (chunk 1 uses base64 variant)
        for i, piece in enumerate(pieces):
            r = _post_chunk(upload_id, i, total, piece, b64=(i == 1))
            assert r.status_code == 200, f"chunk {i} -> {r.status_code} {r.text}"
            j = r.json()
            assert j["received"] == i + 1, (
                f"cumulative received wrong at i={i}: {j}"
            )
            assert j["total"] == total

        # Verify docs exist in db.upload_chunks with binary data and correct index
        out = _mongo_eval(
            f"var arr = db.upload_chunks.find("
            f"  {{user_id:'{COACH_USER_ID}', upload_id:'{upload_id}'}}"
            f").sort({{chunk_index:1}}).toArray();"
            "print(JSON.stringify(arr.map(function(d){"
            "  return {i:d.chunk_index, size:(d.data && d.data.length()) || 0, "
            "          hasData: !!d.data, ts: !!d.created_at};"
            "})));"
        )
        # find the JSON line in mongosh output
        parsed = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("["):
                try:
                    parsed = json.loads(line)
                    break
                except Exception:
                    pass
        assert parsed and len(parsed) == total, f"expected 3 chunk docs, got {out}"
        # index 0..2, each with binary data
        for i, d in enumerate(parsed):
            assert d["i"] == i
            assert d["hasData"] is True
            assert d["ts"] is True
            assert d["size"] == chunk_size, (
                f"chunk {i} size in mongo={d['size']} expected={chunk_size}"
            )

        # Finalize
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id,
                  "filename": "iter11_mongochunks.mp4",
                  "mime_type": "video/mp4",
                  "total_chunks": total},
            timeout=60,
        )
        assert r.status_code == 200, f"finalize -> {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "processing"
        analysis_id = data.get("id") or data.get("analysis_id")
        assert analysis_id and analysis_id.startswith("ana_")

        try:
            # Assembled file present with sum-of-chunks size
            assembled = UPLOAD_DIR / COACH_USER_ID / f"{analysis_id}.mp4"
            for _ in range(15):
                if assembled.exists():
                    break
                time.sleep(0.2)
            assert assembled.exists(), f"assembled file missing at {assembled}"
            actual_size = assembled.stat().st_size
            assert actual_size == expected_total_bytes, (
                f"assembled size {actual_size} != sum of chunks {expected_total_bytes}"
            )

            # upload_chunks docs for this upload_id are deleted after finalize
            n_after = _mongo_eval(
                f"print(db.upload_chunks.countDocuments("
                f"  {{user_id:'{COACH_USER_ID}', upload_id:'{upload_id}'}}));"
            ).strip().splitlines()[-1]
            assert n_after == "0", f"chunks not deleted after finalize: {n_after}"
        finally:
            _cleanup_analysis(analysis_id)


# ---------------------------------------------------------------------------
# 2. Retry / idempotency: same chunk_index uploaded twice does NOT double count
# ---------------------------------------------------------------------------
class TestChunkIdempotency:
    def test_reupload_same_chunk_index_no_double_count(self):
        upload_id = secrets.token_hex(16)
        total = 2
        chunk_size = 64 * 1024
        c0_a = b"AAAA" + os.urandom(chunk_size - 4)
        c0_b = b"BBBB" + os.urandom(chunk_size - 4)   # rewrite of index 0
        c1 = b"CCCC" + os.urandom(chunk_size - 4)

        r = _post_chunk(upload_id, 0, total, c0_a)
        assert r.status_code == 200 and r.json()["received"] == 1
        # Retry same index 0 with different bytes -> should still be received==1
        r = _post_chunk(upload_id, 0, total, c0_b)
        assert r.status_code == 200
        assert r.json()["received"] == 1, (
            f"upsert doubled-counted: {r.json()}"
        )
        r = _post_chunk(upload_id, 1, total, c1)
        assert r.status_code == 200 and r.json()["received"] == 2

        # Finalize -> assembled should be the *latest* c0_b + c1
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id, "filename": "retry.mp4",
                  "mime_type": "video/mp4", "total_chunks": total},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        aid = r.json().get("id") or r.json().get("analysis_id")
        try:
            assembled = UPLOAD_DIR / COACH_USER_ID / f"{aid}.mp4"
            for _ in range(15):
                if assembled.exists():
                    break
                time.sleep(0.2)
            assert assembled.exists()
            content = assembled.read_bytes()
            # Wait up to ~4s: the background task may rewrite/rename to mp4
            # after ffmpeg — but our file has no real header so ffmpeg will
            # fail and leave the original untouched. In either case the size
            # should match c0_b + c1 (2*chunk_size).
            assert len(content) == 2 * chunk_size, (
                f"assembled size {len(content)} != {2*chunk_size}"
            )
            # First 4 bytes should be 'BBBB' (the retry), NOT 'AAAA'.
            assert content[:4] == b"BBBB", (
                f"retry upload did not overwrite; first bytes={content[:4]!r}"
            )
            assert content[chunk_size:chunk_size + 4] == b"CCCC"
        finally:
            _cleanup_analysis(aid)


# ---------------------------------------------------------------------------
# 3. Validations
# ---------------------------------------------------------------------------
class TestFinalizeValidations:
    def test_finalize_unknown_upload_id(self):
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": secrets.token_hex(16),
                  "filename": "x.mp4", "mime_type": "video/mp4",
                  "total_chunks": 1},
            timeout=15,
        )
        assert r.status_code == 400
        assert "not found" in r.text.lower()

    def test_finalize_incomplete_2_of_3(self):
        upload_id = secrets.token_hex(16)
        # send 2 of 3 chunks
        for i in range(2):
            r = _post_chunk(upload_id, i, 3, os.urandom(2048))
            assert r.status_code == 200
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id, "filename": "x.mp4",
                  "mime_type": "video/mp4", "total_chunks": 3},
            timeout=15,
        )
        assert r.status_code == 400
        # exact message: "Upload incomplete: 2/3 chunks received"
        assert "incomplete" in r.text.lower()
        assert "2/3" in r.text
        # cleanup orphan mongo chunks
        _mongo_eval(
            f"db.upload_chunks.deleteMany({{user_id:'{COACH_USER_ID}', "
            f"upload_id:'{upload_id}'}});"
        )

    def test_finalize_bad_upload_id(self):
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": "../evil",
                  "filename": "x.mp4", "mime_type": "video/mp4",
                  "total_chunks": 1},
            timeout=15,
        )
        assert r.status_code == 400

    def test_finalize_unauth(self):
        r = requests.post(
            f"{API}/analyses/finalize",
            headers={"Content-Type": "application/json"},
            json={"upload_id": secrets.token_hex(16),
                  "filename": "x.mp4", "mime_type": "video/mp4",
                  "total_chunks": 1},
            timeout=15,
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 4. GridFS store + streaming fallback (other-replica case)
# ---------------------------------------------------------------------------
class TestGridFSFallback:
    def test_video_persisted_and_streamed_from_gridfs(self):
        # Small chunked upload so ffmpeg is fast (or fails fast on random bytes).
        # Use a plain .mp4 filename so no ffmpeg conversion is attempted; the
        # bg task will call _store_video_in_gridfs directly.
        upload_id = secrets.token_hex(16)
        total = 1
        payload = b"\x00\x00\x00\x18ftypmp42" + os.urandom(200_000)
        r = _post_chunk(upload_id, 0, total, payload)
        assert r.status_code == 200

        r = requests.post(
            f"{API}/analyses/finalize",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"upload_id": upload_id, "filename": "iter11_gridfs.mp4",
                  "mime_type": "video/mp4", "total_chunks": total},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        analysis_id = r.json().get("id") or r.json().get("analysis_id")

        try:
            # Wait for background task to store into GridFS
            gridfs_length = 0
            for _ in range(30):  # up to ~9s
                out = _mongo_eval(
                    "var f = db.getSiblingDB('test_database')"
                    "['videos.files'].findOne("
                    f"  {{filename:'{analysis_id}'}}, {{length:1}});"
                    "print('LEN=' + (f ? Number(f.length) : 0));"
                )
                for ln in out.splitlines():
                    ln = ln.strip()
                    if ln.startswith("LEN="):
                        try:
                            gridfs_length = int(ln[4:])
                        except Exception:
                            gridfs_length = 0
                if gridfs_length:
                    break
                time.sleep(0.3)
            assert gridfs_length > 0, (
                f"GridFS videos.files entry for {analysis_id} not created within 9s"
            )
            # Expected size == payload size (no ffmpeg conversion for .mp4)
            assert gridfs_length == len(payload), (
                f"GridFS length {gridfs_length} != payload {len(payload)}"
            )

            # First: hit /video WITH local file present — sanity check 200
            r = requests.get(
                f"{API}/analyses/{analysis_id}/video?token={COACH_TOKEN}",
                timeout=30,
            )
            assert r.status_code == 200
            local_bytes = r.content
            assert len(local_bytes) == len(payload)

            # Now simulate other-replica case: move local file away
            local_file = UPLOAD_DIR / COACH_USER_ID / f"{analysis_id}.mp4"
            assert local_file.exists()
            hidden = local_file.with_suffix(".mp4.hidden")
            local_file.rename(hidden)
            try:
                r = requests.get(
                    f"{API}/analyses/{analysis_id}/video?token={COACH_TOKEN}",
                    timeout=30,
                )
                assert r.status_code == 200, (
                    f"GridFS fallback failed: {r.status_code} {r.text[:200]}"
                )
                gridfs_bytes = r.content
                assert len(gridfs_bytes) == len(payload), (
                    f"GridFS-streamed size {len(gridfs_bytes)} != {len(payload)}"
                )
                # Must be byte-identical to what we uploaded
                assert gridfs_bytes == payload, (
                    "GridFS-streamed bytes differ from uploaded payload"
                )
            finally:
                # restore the file so cleanup can delete it
                try:
                    hidden.rename(local_file)
                except Exception:
                    pass

            # Missing token -> 401
            r = requests.get(f"{API}/analyses/{analysis_id}/video", timeout=10)
            assert r.status_code == 401
        finally:
            _cleanup_analysis(analysis_id)


# ---------------------------------------------------------------------------
# 5. Startup indexes on db.upload_chunks
# ---------------------------------------------------------------------------
class TestStartupIndexes:
    def test_ttl_and_unique_compound_indexes_exist(self):
        out = _mongo_eval(
            "print(JSON.stringify(db.upload_chunks.getIndexes()));"
        )
        parsed = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("["):
                try:
                    parsed = json.loads(line)
                    break
                except Exception:
                    pass
        assert parsed, f"could not parse indexes: {out}"

        # TTL index on created_at with expireAfterSeconds=86400
        ttl = [i for i in parsed
               if i.get("key") == {"created_at": 1}
               and i.get("expireAfterSeconds") == 86400]
        assert ttl, f"TTL index missing/wrong: {parsed}"

        # unique compound index on (user_id, upload_id, chunk_index)
        uniq = [i for i in parsed
                if i.get("key") == {"user_id": 1, "upload_id": 1, "chunk_index": 1}
                and i.get("unique") is True]
        assert uniq, f"unique compound index missing/wrong: {parsed}"


# ---------------------------------------------------------------------------
# 6. Regressions
# ---------------------------------------------------------------------------
class TestRegressions:
    def test_legacy_small_file_upload(self):
        payload = b"\x00\x00\x00\x18ftypmp42" + os.urandom(64 * 1024)
        t0 = time.time()
        r = requests.post(
            f"{API}/analyses",
            headers=_headers(),
            files={"file": ("legacy.mp4", payload, "video/mp4")},
            timeout=30,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, f"legacy -> {r.status_code} {r.text}"
        assert elapsed < 10, f"legacy /api/analyses too slow: {elapsed:.1f}s"
        data = r.json()
        assert data.get("status") == "processing"
        aid = data.get("id") or data.get("analysis_id")
        assert aid and aid.startswith("ana_")
        _cleanup_analysis(aid)

    def test_plans_endpoint(self):
        r = requests.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200
        j = r.json()
        # plans response should have entries with price info
        assert isinstance(j, (list, dict))

    def test_root_serves_html(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()
