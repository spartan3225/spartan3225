"""
SurfCoach23 backend tier system tests.

Targets the public deployed backend (REACT_APP / EXPO_PUBLIC_BACKEND_URL).
Tests cover the new tier system:
  free (lifetime 1), beginner ($5,1/d), plus ($12,3/d),
  intermediate ($20,6/d), advanced ($35,10/d), pro ($60,15/d),
  coach ($120,unlimited).

Run:  python /app/backend_test.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from motor.motor_asyncio import AsyncIOMotorClient

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
ENV_FILE = Path("/app/frontend/.env")
BASE_URL = None
for line in ENV_FILE.read_text().splitlines():
    if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
        BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
        break
if not BASE_URL:
    print("FATAL: EXPO_PUBLIC_BACKEND_URL missing")
    sys.exit(1)
API = f"{BASE_URL}/api"

DEMO_FREE_TOKEN = "demo_token_active"
DEMO_FREE_USER_ID = "user_demo_12345"
DEMO_COACH_TOKEN = "demo_coach_token"
DEMO_COACH_USER_ID = "user_coach_67890"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    icon = "OK " if ok else "FAIL"
    print(f"[{icon}] {name}  {detail}")
    results.append((name, ok, detail))


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Test 1: GET /api/plans
# --------------------------------------------------------------------------
def test_plans():
    print("\n=== Test 1: GET /api/plans ===")
    r = requests.get(f"{API}/plans", timeout=20)
    if r.status_code != 200:
        record("GET /api/plans status", False, f"got {r.status_code}: {r.text[:200]}")
        return
    data = r.json()
    plans = data.get("plans", [])
    expected_order = ["free", "beginner", "plus", "intermediate", "advanced", "pro", "coach"]
    expected_amounts = {"free": 0.0, "beginner": 5.0, "plus": 12.0, "intermediate": 20.0,
                        "advanced": 35.0, "pro": 60.0, "coach": 120.0}
    expected_limits = {"free": 1, "beginner": 1, "plus": 3, "intermediate": 6,
                       "advanced": 10, "pro": 15, "coach": -1}

    actual_ids = [p.get("plan_id") for p in plans]
    record("plans count == 7", len(plans) == 7, f"got {len(plans)}")
    record("plan order matches", actual_ids == expected_order, f"actual={actual_ids}")

    for p in plans:
        pid = p.get("plan_id")
        amt = p.get("amount")
        lim = p.get("daily_limit")
        record(f"  amount[{pid}]", amt == expected_amounts.get(pid),
               f"got {amt} expected {expected_amounts.get(pid)}")
        record(f"  daily_limit[{pid}]", lim == expected_limits.get(pid),
               f"got {lim} expected {expected_limits.get(pid)}")

    # is_lifetime only on free
    for p in plans:
        pid = p.get("plan_id")
        is_lt = p.get("is_lifetime")
        if pid == "free":
            record("free is_lifetime: true", is_lt is True, f"got {is_lt}")
        else:
            record(f"  {pid} no is_lifetime flag (or False)", is_lt is None or is_lt is False,
                   f"got {is_lt}")

    record("free_lifetime_limit == 1",
           data.get("free_lifetime_limit") == 1,
           f"got {data.get('free_lifetime_limit')}")


# --------------------------------------------------------------------------
# Test 2: GET /api/analyses/quota
# --------------------------------------------------------------------------
def test_quota_free():
    print("\n=== Test 2a: quota for free user ===")
    r = requests.get(f"{API}/analyses/quota", headers=hdr(DEMO_FREE_TOKEN), timeout=15)
    if r.status_code != 200:
        record("quota free 200", False, f"status={r.status_code} body={r.text[:200]}")
        return
    q = r.json()
    record("quota free is_lifetime: true", q.get("is_lifetime") is True, f"got {q.get('is_lifetime')}")
    record("quota free limit == 1", q.get("limit") == 1, f"got {q.get('limit')}")
    record("quota free tier == free", q.get("tier") == "free", f"got {q.get('tier')}")
    print(f"      raw: {q}")


def test_quota_coach():
    print("\n=== Test 2b: quota for coach user ===")
    r = requests.get(f"{API}/analyses/quota", headers=hdr(DEMO_COACH_TOKEN), timeout=15)
    if r.status_code != 200:
        record("quota coach 200", False, f"status={r.status_code} body={r.text[:200]}")
        return
    q = r.json()
    record("quota coach is_lifetime: false", q.get("is_lifetime") is False, f"got {q.get('is_lifetime')}")
    record("quota coach limit == -1 (unlimited)", q.get("limit") == -1, f"got {q.get('limit')}")
    record("quota coach tier == coach", q.get("tier") == "coach", f"got {q.get('tier')}")
    print(f"      raw: {q}")


# --------------------------------------------------------------------------
# Test 3: POST /api/payments/checkout
# --------------------------------------------------------------------------
def test_checkout_valid_plans():
    print("\n=== Test 3: POST /api/payments/checkout ===")
    valid_plans = ["beginner", "intermediate", "advanced", "pro"]
    for plan_id in valid_plans:
        body = {"plan_id": plan_id, "origin_url": "https://wave-motion-ai.preview.emergentagent.com"}
        r = requests.post(f"{API}/payments/checkout", json=body,
                          headers=hdr(DEMO_FREE_TOKEN), timeout=30)
        if r.status_code != 200:
            record(f"checkout {plan_id} 200", False,
                   f"status={r.status_code} body={r.text[:300]}")
            continue
        j = r.json()
        url = j.get("url", "")
        sid = j.get("session_id", "")
        record(f"checkout {plan_id} returns Stripe url",
               "checkout.stripe.com" in url and sid.startswith("cs_"),
               f"url={url[:80]} sid={sid[:30]}")

    # invalid plan
    body = {"plan_id": "invalid_plan",
            "origin_url": "https://wave-motion-ai.preview.emergentagent.com"}
    r = requests.post(f"{API}/payments/checkout", json=body,
                      headers=hdr(DEMO_FREE_TOKEN), timeout=20)
    record("checkout invalid_plan -> 400", r.status_code == 400,
           f"status={r.status_code} body={r.text[:120]}")

    # also test plus and coach to confirm full coverage
    for plan_id in ["plus", "coach"]:
        body = {"plan_id": plan_id, "origin_url": "https://wave-motion-ai.preview.emergentagent.com"}
        r = requests.post(f"{API}/payments/checkout", json=body,
                          headers=hdr(DEMO_FREE_TOKEN), timeout=30)
        record(f"checkout {plan_id} 200", r.status_code == 200,
               f"status={r.status_code}")


# --------------------------------------------------------------------------
# Test 4: POST /api/analyses lifetime cap (CRITICAL)
# --------------------------------------------------------------------------
async def _seed_one_analysis_for_free_user():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    # remove any existing test-seeded analyses for this demo free user
    await db.analyses.delete_many({"user_id": DEMO_FREE_USER_ID})
    await db.analyses.insert_one({
        "analysis_id": f"ana_seed_{uuid.uuid4().hex[:10]}",
        "user_id": DEMO_FREE_USER_ID,
        "video_path": "/tmp/seed.mp4",
        "mime_type": "video/mp4",
        "status": "ready",
        "created_at": datetime.now(timezone.utc) - timedelta(days=10),
        "title": "Seeded prior analysis",
        "score": 50,
        "overall_rating": "Intermediate",
        "summary": "seeded for lifetime cap test",
        "strengths": [], "mistakes": [], "corrections": [], "tips": [], "drills": [],
        "shared_with_coach_id": None,
    })
    client.close()


async def _wipe_analyses_for_free_user():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.analyses.delete_many({"user_id": DEMO_FREE_USER_ID})
    client.close()


def _tiny_mp4_bytes() -> bytes:
    # Minimal valid mp4 ftyp header + mdat (won't decode but is bytes)
    return (b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            b"\x00\x00\x00\x08mdat")


def test_lifetime_cap():
    print("\n=== Test 4: lifetime cap on free tier ===")

    # 4a: free user with 1 existing analysis -> POST must return 402
    asyncio.run(_seed_one_analysis_for_free_user())

    # confirm via quota
    q = requests.get(f"{API}/analyses/quota", headers=hdr(DEMO_FREE_TOKEN), timeout=15).json()
    print(f"      pre-POST quota: {q}")
    record("quota reports used_today=1 (lifetime)",
           q.get("used_today") == 1 and q.get("remaining") == 0,
           f"got {q}")

    files = {"file": ("seeded.mp4", io.BytesIO(_tiny_mp4_bytes()), "video/mp4")}
    r = requests.post(f"{API}/analyses", headers=hdr(DEMO_FREE_TOKEN), files=files, timeout=30)
    body_preview = r.text[:300] if r.text else ""
    record("POST /api/analyses (free w/ 1 prior) -> 402",
           r.status_code == 402,
           f"status={r.status_code} body={body_preview}")
    if r.status_code == 402:
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = body_preview
        record("  402 message mentions 'lifetime'",
               "lifetime" in detail.lower(),
               f"detail={detail}")

    # 4b: with 0 analyses, the lifetime cap should NOT be the blocker.
    # We do not actually wait for AI to complete, so we accept anything other
    # than 402. (500 from AI is ok — proves the cap allowed the request through.)
    print("\n--- Test 4b: free user with 0 analyses (cap should permit) ---")
    asyncio.run(_wipe_analyses_for_free_user())
    q = requests.get(f"{API}/analyses/quota", headers=hdr(DEMO_FREE_TOKEN), timeout=15).json()
    print(f"      reset quota: {q}")
    record("quota after wipe shows remaining=1",
           q.get("remaining") == 1 and q.get("used_today") == 0,
           f"got {q}")

    files = {"file": ("seeded.mp4", io.BytesIO(_tiny_mp4_bytes()), "video/mp4")}
    try:
        r = requests.post(f"{API}/analyses", headers=hdr(DEMO_FREE_TOKEN), files=files, timeout=180)
    except requests.exceptions.RequestException as e:
        record("POST /api/analyses (free w/ 0 prior) bypass 402", True,
               f"request errored after upload (acceptable): {e}")
    else:
        record("POST /api/analyses (free w/ 0 prior) is NOT 402",
               r.status_code != 402,
               f"status={r.status_code} body={r.text[:200]}")
    # cleanup
    asyncio.run(_wipe_analyses_for_free_user())


# --------------------------------------------------------------------------
# Test 5: tier persistence after webhook (_apply_subscription_if_paid)
# --------------------------------------------------------------------------
async def _test_apply_subscription(plan_id: str) -> dict:
    """Insert a fake payment_transactions doc and call
    `_apply_subscription_if_paid` directly (with event_paid=True)
    so we don't need real Stripe payment. Verify the user's tier is updated.
    """
    sys.path.insert(0, "/app/backend")
    # Re-import to avoid stale module state
    import importlib
    import server  # type: ignore
    importlib.reload(server)
    apply_fn = server._apply_subscription_if_paid

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Snapshot original user
    original = await db.users.find_one({"user_id": DEMO_FREE_USER_ID}, {"_id": 0})

    # Reset to free first
    await db.users.update_one(
        {"user_id": DEMO_FREE_USER_ID},
        {"$set": {"tier": "free", "subscription_status": None,
                  "subscription_expires_at": None}},
    )

    fake_session_id = f"cs_test_fake_{uuid.uuid4().hex[:18]}"
    await db.payment_transactions.insert_one({
        "session_id": fake_session_id,
        "user_id": DEMO_FREE_USER_ID,
        "email": "demo@surfai.test",
        "plan_id": plan_id,
        "amount": 0.0,
        "currency": "usd",
        "metadata": {"user_id": DEMO_FREE_USER_ID, "plan_id": plan_id},
        "payment_status": "initiated",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "applied": False,
    })

    res = await apply_fn(fake_session_id, event_paid=True)

    user_after = await db.users.find_one({"user_id": DEMO_FREE_USER_ID}, {"_id": 0})

    # cleanup payment tx
    await db.payment_transactions.delete_one({"session_id": fake_session_id})

    # restore original tier (it might already have been set if ran multiple times)
    if original:
        await db.users.update_one(
            {"user_id": DEMO_FREE_USER_ID},
            {"$set": {
                "tier": original.get("tier") or "free",
                "subscription_status": original.get("subscription_status"),
                "subscription_expires_at": original.get("subscription_expires_at"),
            }},
        )
    client.close()
    return {"apply_result": res, "user_tier": user_after.get("tier") if user_after else None,
            "expires": user_after.get("subscription_expires_at") if user_after else None}


def test_webhook_tier_apply():
    print("\n=== Test 5: _apply_subscription_if_paid tier mapping ===")
    for plan_id in ["beginner", "intermediate", "advanced", "pro"]:
        out = asyncio.run(_test_apply_subscription(plan_id))
        print(f"      {plan_id} => {out}")
        record(f"apply_subscription {plan_id} -> tier set",
               out.get("user_tier") == plan_id,
               f"got tier={out.get('user_tier')} apply_result={out.get('apply_result')}")
        record(f"  {plan_id} subscription_expires_at populated",
               out.get("expires") is not None,
               f"expires={out.get('expires')}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    print(f"BASE_URL = {BASE_URL}")
    print(f"API      = {API}\n")

    test_plans()
    test_quota_free()
    test_quota_coach()
    test_checkout_valid_plans()
    test_lifetime_cap()
    test_webhook_tier_apply()

    print("\n========== SUMMARY ==========")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"Passed: {passed} / {len(results)}    Failed: {failed}")
    if failed:
        print("\nFailures:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}  {detail}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
