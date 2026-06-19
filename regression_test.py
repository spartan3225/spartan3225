"""Quick regression test for SurfCoach23 backend after Stripe legacy cleanup."""
import os
import sys
import requests

BASE = "https://wave-motion-ai.preview.emergentagent.com/api"
FREE_TOKEN = "demo_token_active"
COACH_TOKEN = "demo_coach_token"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


results = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    results.append((name, status, extra))
    print(f"[{status}] {name}  {extra}")


# 1. /api/health
r = requests.get(f"{BASE}/health", timeout=15)
check("1. GET /api/health -> 200", r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")

# 2. /api/plans -> 4 plans free/learn/advanced/pro, SAR currency for paid
r = requests.get(f"{BASE}/plans", timeout=15)
ok = r.status_code == 200
data = r.json() if ok else {}
plans = data.get("plans", [])
ids = [p.get("plan_id") for p in plans]
check("2a. /api/plans status 200", ok, f"status={r.status_code}")
check("2b. /api/plans returns 4 plans free/learn/advanced/pro",
      ids == ["free", "learn", "advanced", "pro"],
      f"got={ids}")
paid_plans = [p for p in plans if p.get("plan_id") != "free"]
sar_ok = all((p.get("currency") or "").lower() == "sar" for p in paid_plans)
check("2c. Paid plans currency=SAR", sar_ok,
      f"currencies={[p.get('currency') for p in plans]}")

# 3. POST /api/payments/checkout -> 410 Gone
r = requests.post(f"{BASE}/payments/checkout",
                  headers=auth(FREE_TOKEN),
                  json={"plan_id": "learn", "origin_url": "https://x.test"},
                  timeout=15)
check("3. POST /api/payments/checkout -> 410", r.status_code == 410,
      f"status={r.status_code} body={r.text[:200]}")

# 4. POST /api/payments/lemonsqueezy/checkout
# 4a. valid plan -> 200 + URL
r = requests.post(f"{BASE}/payments/lemonsqueezy/checkout",
                  headers=auth(FREE_TOKEN),
                  json={"plan_id": "learn",
                        "origin_url": "https://wave-motion-ai.preview.emergentagent.com"},
                  timeout=30)
ok = r.status_code == 200
url = ""
if ok:
    try:
        url = r.json().get("url", "")
    except Exception:
        url = ""
check("4a. LS checkout (plan=learn) -> 200 with URL",
      ok and "lemonsqueezy" in url.lower(),
      f"status={r.status_code} url={url[:80]} body={r.text[:200] if not ok else ''}")

# Also test advanced + pro briefly
for plan_id in ("advanced", "pro"):
    r = requests.post(f"{BASE}/payments/lemonsqueezy/checkout",
                      headers=auth(FREE_TOKEN),
                      json={"plan_id": plan_id,
                            "origin_url": "https://wave-motion-ai.preview.emergentagent.com"},
                      timeout=30)
    ok = r.status_code == 200
    url = ""
    if ok:
        try:
            url = r.json().get("url", "")
        except Exception:
            url = ""
    check(f"4a.{plan_id} LS checkout (plan={plan_id}) -> 200 with URL",
          ok and "lemonsqueezy" in url.lower(),
          f"status={r.status_code} body={r.text[:200] if not ok else ''}")

# 4b. invalid plan -> 400
r = requests.post(f"{BASE}/payments/lemonsqueezy/checkout",
                  headers=auth(FREE_TOKEN),
                  json={"plan_id": "totally_bogus",
                        "origin_url": "https://wave-motion-ai.preview.emergentagent.com"},
                  timeout=15)
check("4b. LS checkout invalid plan -> 400", r.status_code == 400,
      f"status={r.status_code} body={r.text[:200]}")

# 5. /api/analyses/quota -> is_lifetime bool
r = requests.get(f"{BASE}/analyses/quota", headers=auth(FREE_TOKEN), timeout=15)
ok = r.status_code == 200
js = r.json() if ok else {}
check("5a. quota (free) is_lifetime=True",
      ok and js.get("is_lifetime") is True,
      f"status={r.status_code} body={js}")

r = requests.get(f"{BASE}/analyses/quota", headers=auth(COACH_TOKEN), timeout=15)
ok = r.status_code == 200
js = r.json() if ok else {}
check("5b. quota (coach) is_lifetime=False",
      ok and js.get("is_lifetime") is False,
      f"status={r.status_code} body={js}")

# 6. POST /api/payments/cancel-renewal
# 6a. free user -> 400
r = requests.post(f"{BASE}/payments/cancel-renewal",
                  headers=auth(FREE_TOKEN), timeout=15)
check("6a. cancel-renewal free user -> 400", r.status_code == 400,
      f"status={r.status_code} body={r.text[:200]}")

# 6b. As a learn user -> 200. Need to seed a learn-tier user.
# We'll temporarily promote the demo user to 'learn' tier via mongosh,
# then call the endpoint, then restore.
import subprocess

MONGO_PROMOTE = (
    "use('test_database');"
    "db.users.updateOne({user_id:'user_demo_12345'},"
    "{$set:{tier:'learn',subscription_status:'active',"
    "subscription_expires_at:new Date(Date.now()+30*24*60*60*1000),"
    "cancel_at_period_end:false}});"
)
MONGO_RESTORE = (
    "use('test_database');"
    "db.users.updateOne({user_id:'user_demo_12345'},"
    "{$set:{tier:'free',subscription_status:null,"
    "subscription_expires_at:null,cancel_at_period_end:false}});"
)

mongo_url = None
with open("/app/backend/.env") as f:
    for line in f:
        if line.startswith("MONGO_URL="):
            mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

try:
    subprocess.run(["mongosh", mongo_url or "mongodb://localhost:27017",
                    "--quiet", "--eval", MONGO_PROMOTE],
                   check=True, capture_output=True, timeout=15)
    r = requests.post(f"{BASE}/payments/cancel-renewal",
                      headers=auth(FREE_TOKEN), timeout=15)
    check("6b. cancel-renewal learn-tier user -> 200",
          r.status_code == 200,
          f"status={r.status_code} body={r.text[:200]}")
finally:
    subprocess.run(["mongosh", mongo_url or "mongodb://localhost:27017",
                    "--quiet", "--eval", MONGO_RESTORE],
                   check=False, capture_output=True, timeout=15)

# Summary
print("\n===== SUMMARY =====")
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print(f"{passed} passed, {failed} failed")
for name, status, extra in results:
    if status == "FAIL":
        print(f"  FAIL: {name}  {extra}")
sys.exit(0 if failed == 0 else 1)
