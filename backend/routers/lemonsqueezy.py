"""LemonSqueezy integration for SurfCoach23.

3-tier subscription model (in addition to Free):
  - learn     -> $90 / month  -> 1 video / day
  - advanced  -> $150 / month -> 3 videos / day
  - pro       -> $200 / month -> 10 videos / day

Free tier remains at 1 video LIFETIME.

This router is mounted under /api by the main server.
Endpoints:
  POST /payments/lemonsqueezy/checkout       -> create hosted checkout URL
  GET  /payments/lemonsqueezy/status/{id}    -> read local txn status
  POST /webhook/lemonsqueezy                 -> webhook receiver
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("surfai.lemonsqueezy")

LS_API_BASE = "https://api.lemonsqueezy.com/v1"
LS_API_KEY = os.environ.get("LEMONSQUEEZY_API_KEY", "")
LS_STORE_ID = os.environ.get("LEMONSQUEEZY_STORE_ID", "")
LS_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
LS_TEST_MODE = (os.environ.get("LEMONSQUEEZY_TEST_MODE", "true").lower() == "true")

# Map our internal tier id -> LemonSqueezy variant id
LS_VARIANTS = {
    "learn": os.environ.get("LEMONSQUEEZY_VARIANT_LEARN", ""),
    "advanced": os.environ.get("LEMONSQUEEZY_VARIANT_ADVANCED", ""),
    "pro": os.environ.get("LEMONSQUEEZY_VARIANT_PRO", ""),
    # One-time add-on: 1 credit = 1 multi-video (up to 3 clips) analysis
    "multi": os.environ.get("LEMONSQUEEZY_VARIANT_MULTI", ""),
}

# One-time purchases (not subscriptions)
LS_ADDONS = {
    "multi": {
        "name": "Multi-Video Analysis",
        "amount": 9.99,
        "currency": "usd",
    },
}

# Public plan catalogue (matches what the frontend paywall renders).
LS_PLANS = {
    "learn": {
        "name": "LEARN",
        "amount": 15.0,
        "currency": "usd",
        "interval_days": 30,
        "daily_limit": 1,
        "features": [
            "1 AI surf analysis per day",
            "Standard depth breakdown",
            "Personal session history",
        ],
    },
    "advanced": {
        "name": "Advanced",
        "amount": 25.0,
        "currency": "usd",
        "interval_days": 30,
        "daily_limit": 3,
        "features": [
            "3 AI analyses per day",
            "Deeper technical breakdown",
            "Priority queue",
            "Browse public coach directory",
        ],
    },
    "pro": {
        "name": "PRO",
        "amount": 35.0,
        "currency": "usd",
        "interval_days": 30,
        "daily_limit": 10,
        "features": [
            "10 AI analyses per day",
            "Pro-tour deeper breakdown",
            "Top-priority queue",
            "Browse public coach directory",
            "Share clips with any coach",
        ],
    },
}


router = APIRouter()


# -------- Models --------
class LSCheckoutRequest(BaseModel):
    plan_id: str  # "learn" | "advanced" | "pro"
    origin_url: str


class LSCheckoutOut(BaseModel):
    url: str
    session_id: str  # the checkout id returned by LemonSqueezy


# -------- Helpers --------
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {LS_API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not LS_WEBHOOK_SECRET:
        logger.warning("LEMONSQUEEZY_WEBHOOK_SECRET not configured")
        return False
    if not signature_header:
        return False
    expected = hmac.new(
        LS_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def attach(app_router: APIRouter, db, get_current_user, paid_tiers_setter):
    """Wire the LemonSqueezy endpoints into the provided api_router.

    Parameters
    ----------
    app_router : the main `/api` APIRouter from server.py
    db         : Motor MongoDB database
    get_current_user : dependency from server.py
    paid_tiers_setter : callable -> set ALL_PAID_TIERS in server (kept for future use)
    """

    @app_router.post(
        "/payments/lemonsqueezy/checkout", response_model=LSCheckoutOut
    )
    async def create_checkout(
        req: LSCheckoutRequest,
        request: Request,
        user=Depends(get_current_user),
    ):
        if req.plan_id not in LS_VARIANTS or not LS_VARIANTS[req.plan_id]:
            raise HTTPException(status_code=400, detail="Invalid plan")
        if not LS_API_KEY or not LS_STORE_ID:
            raise HTTPException(
                status_code=500, detail="LemonSqueezy not configured"
            )

        variant_id = LS_VARIANTS[req.plan_id]
        if not variant_id or not str(variant_id).strip('"'):
            raise HTTPException(
                status_code=503,
                detail="This product is not configured yet. Please try again later.",
            )
        origin = req.origin_url.rstrip("/")
        success_url = (
            f"{origin}/payment-success?ls_plan={req.plan_id}"
            "&session_id={checkout_id}"
        )
        # ^ LemonSqueezy doesn't substitute placeholders, but we encode plan
        # so the frontend success page can show the right tier name.

        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "email": user.email,
                        "custom": {
                            "user_id": user.user_id,
                            "plan_id": req.plan_id,
                        },
                    },
                    "checkout_options": {
                        "embed": False,
                        "media": True,
                        "logo": True,
                    },
                    "product_options": {
                        "redirect_url": success_url,
                    },
                    "test_mode": LS_TEST_MODE,
                },
                "relationships": {
                    "store": {
                        "data": {"type": "stores", "id": str(LS_STORE_ID)}
                    },
                    "variant": {
                        "data": {"type": "variants", "id": str(variant_id)}
                    },
                },
            }
        }

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{LS_API_BASE}/checkouts",
                headers=_headers(),
                json=payload,
            )
        if r.status_code >= 400:
            logger.error("LemonSqueezy checkout failed %s %s", r.status_code, r.text)
            raise HTTPException(
                status_code=502,
                detail=f"LemonSqueezy error: {r.text[:300]}",
            )
        data = r.json().get("data", {})
        attrs = data.get("attributes", {})
        checkout_id = data.get("id") or ""
        checkout_url = attrs.get("url") or ""
        if not checkout_url:
            raise HTTPException(
                status_code=502, detail="LemonSqueezy returned no checkout URL"
            )

        # Persist a local txn so we can correlate later.
        await db.payment_transactions.insert_one(
            {
                "session_id": checkout_id,
                "provider": "lemonsqueezy",
                "user_id": user.user_id,
                "email": user.email,
                "plan_id": req.plan_id,
                "amount": float(
                    (LS_PLANS.get(req.plan_id) or LS_ADDONS[req.plan_id])["amount"]
                ),
                "currency": (
                    LS_PLANS.get(req.plan_id) or LS_ADDONS[req.plan_id]
                )["currency"],
                "test_mode": LS_TEST_MODE,
                "status": "open",
                "payment_status": "initiated",
                "created_at": datetime.now(timezone.utc),
                "applied": False,
            }
        )

        return LSCheckoutOut(url=checkout_url, session_id=checkout_id or "ls_session")

    @app_router.get("/payments/lemonsqueezy/status/{session_id}")
    async def status(session_id: str, user=Depends(get_current_user)):
        txn = await db.payment_transactions.find_one(
            {"session_id": session_id, "user_id": user.user_id}, {"_id": 0}
        )
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {
            "session_id": session_id,
            "status": txn.get("status") or "open",
            "payment_status": txn.get("payment_status") or "initiated",
            "plan_id": txn.get("plan_id"),
            "tier": txn.get("plan_id") if txn.get("applied") else None,
        }

    @app_router.post("/webhook/lemonsqueezy")
    async def webhook(request: Request):
        raw = await request.body()
        sig = request.headers.get("X-Signature") or request.headers.get(
            "x-signature", ""
        )
        if not _verify_signature(raw, sig):
            logger.warning("LemonSqueezy webhook bad signature")
            raise HTTPException(status_code=400, detail="Invalid signature")

        try:
            event = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Bad JSON")

        meta = event.get("meta", {})
        event_name = meta.get("event_name", "")
        custom_data = (meta.get("custom_data") or {}) if isinstance(meta, dict) else {}
        data = event.get("data", {}) or {}
        attrs = data.get("attributes", {}) or {}

        user_id = (
            custom_data.get("user_id")
            or attrs.get("user_email")  # fallback nothing
        )
        plan_id = custom_data.get("plan_id")
        logger.info(
            "LemonSqueezy webhook: event=%s user=%s plan=%s status=%s",
            event_name,
            user_id,
            plan_id,
            attrs.get("status"),
        )

        if not user_id or not plan_id:
            return {"ignored": True, "reason": "missing user/plan"}

        # Activate / extend subscription on these events.
        if event_name in (
            "subscription_created",
            "subscription_updated",
            "subscription_payment_success",
            "order_created",
        ):
            sub_status = (attrs.get("status") or "").lower()
            # Treat these as "active" - covers paused-then-active, etc.
            active_states = {
                "active",
                "on_trial",
                "paid",
                "subscription_payment_success",
                "completed",
            }
            if event_name == "order_created":
                # order_created may not carry sub status; trust the event.
                active = True
            else:
                active = sub_status in active_states

            if active and plan_id == "multi":
                # One-time multi-video credit. Idempotent per LS order id.
                order_id = str(data.get("id") or "")
                now = datetime.now(timezone.utc)
                already = None
                if order_id:
                    already = await db.applied_orders.find_one(
                        {"order_id": order_id, "plan_id": "multi"}
                    )
                if not already:
                    if order_id:
                        await db.applied_orders.insert_one(
                            {
                                "order_id": order_id,
                                "plan_id": "multi",
                                "user_id": user_id,
                                "applied_at": now,
                            }
                        )
                    await db.users.update_one(
                        {"user_id": user_id},
                        {"$inc": {"multi_credits": 1}},
                    )
                    await db.payment_transactions.update_many(
                        {"user_id": user_id, "plan_id": "multi", "applied": False},
                        {
                            "$set": {
                                "applied": True,
                                "applied_at": now,
                                "status": "complete",
                                "payment_status": "paid",
                                "ls_order_id": order_id,
                            }
                        },
                    )
                    logger.info(
                        "Granted 1 multi-video credit to user=%s (order=%s)",
                        user_id,
                        order_id,
                    )
            elif active and plan_id in LS_PLANS:
                interval = LS_PLANS[plan_id]["interval_days"]
                now = datetime.now(timezone.utc)
                user_doc = await db.users.find_one(
                    {"user_id": user_id}, {"_id": 0}
                )
                base = now
                if user_doc and user_doc.get("subscription_expires_at"):
                    exp = user_doc.get("subscription_expires_at")
                    if isinstance(exp, str):
                        try:
                            exp = datetime.fromisoformat(exp)
                        except Exception:
                            exp = None
                    if exp and exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp and exp > now and user_doc.get("tier") == plan_id:
                        base = exp
                new_exp = base + timedelta(days=interval)
                await db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "tier": plan_id,
                            "subscription_status": "active",
                            "subscription_expires_at": new_exp,
                            "cancel_at_period_end": False,
                            "subscription_provider": "lemonsqueezy",
                            "ls_subscription_id": data.get("id"),
                        }
                    },
                )
                # Mark txn (best-effort)
                await db.payment_transactions.update_many(
                    {"user_id": user_id, "plan_id": plan_id, "applied": False},
                    {
                        "$set": {
                            "applied": True,
                            "applied_at": now,
                            "status": "complete",
                            "payment_status": "paid",
                            "ls_subscription_id": data.get("id"),
                        }
                    },
                )

        elif event_name in ("subscription_cancelled",):
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"cancel_at_period_end": True}},
            )
        elif event_name in ("subscription_expired",):
            await db.users.update_one(
                {"user_id": user_id, "tier": plan_id},
                {
                    "$set": {
                        "tier": "free",
                        "subscription_status": "expired",
                        "cancel_at_period_end": False,
                    }
                },
            )

        # Always log raw for audit
        await db.webhook_events.insert_one(
            {
                "provider": "lemonsqueezy",
                "event_name": event_name,
                "user_id": user_id,
                "plan_id": plan_id,
                "received_at": datetime.now(timezone.utc),
                "raw": event,
            }
        )

        return {"ok": True, "event": event_name}

    # Done wiring routes.
    return None
