from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Header, Request, Body
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
import re
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import httpx

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
)


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
EMERGENT_AUTH_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)

# Server-defined plans (NEVER trust frontend for amount)
PLANS: dict[str, dict] = {
    "coach": {
        "name": "Coach",
        "amount": 120.00,
        "currency": "usd",
        "interval_days": 30,
        "description": "Coach Plan – Monthly",
    }
}

FREE_DAILY_LIMIT = 1

app = FastAPI()
api_router = APIRouter(prefix="/api")

logger = logging.getLogger("surfai")


# ---------------- Models ----------------
class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime
    tier: str = "free"  # free | coach
    subscription_status: Optional[str] = None  # active | expired | none
    subscription_expires_at: Optional[datetime] = None
    coach_bio: Optional[str] = None
    coach_specialty: Optional[str] = None
    coach_location: Optional[str] = None
    coach_public: bool = False


class SessionExchangeRequest(BaseModel):
    session_id: str


class AuthResponse(BaseModel):
    session_token: str
    user: User


class Mistake(BaseModel):
    title: str
    detail: str
    severity: str
    timestamp: Optional[str] = None


class AnalysisOut(BaseModel):
    analysis_id: str
    user_id: str
    title: str
    score: int
    overall_rating: str
    summary: str
    strengths: List[str]
    mistakes: List[Mistake]
    corrections: List[str]
    tips: List[str]
    drills: List[str]
    duration_seconds: Optional[float] = None
    status: str
    created_at: datetime
    shared_with_coach_id: Optional[str] = None


class AnalysisListItem(BaseModel):
    analysis_id: str
    title: str
    score: int
    overall_rating: str
    summary: str
    status: str
    created_at: datetime
    shared_with_coach_id: Optional[str] = None


class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str  # frontend window.location.origin


class CheckoutSessionOut(BaseModel):
    url: str
    session_id: str


class PaymentStatusOut(BaseModel):
    session_id: str
    status: str  # open | complete | expired
    payment_status: str
    plan_id: Optional[str] = None
    tier: Optional[str] = None


class CoachProfileUpdate(BaseModel):
    bio: Optional[str] = None
    specialty: Optional[str] = None
    location: Optional[str] = None
    public: Optional[bool] = None


class CoachListItem(BaseModel):
    user_id: str
    name: str
    picture: Optional[str] = None
    coach_bio: Optional[str] = None
    coach_specialty: Optional[str] = None
    coach_location: Optional[str] = None


class ShareRequest(BaseModel):
    coach_user_id: str


class CommentCreate(BaseModel):
    text: str


class Comment(BaseModel):
    comment_id: str
    analysis_id: str
    author_id: str
    author_name: str
    author_picture: Optional[str] = None
    is_coach: bool
    text: str
    created_at: datetime


# ---------------- Helpers ----------------
def _user_to_model(doc: dict) -> User:
    keys = User.model_fields.keys()
    return User(**{k: doc.get(k) for k in keys if k in doc})


def _is_coach_active(user_doc: dict) -> bool:
    if user_doc.get("tier") != "coach":
        return False
    exp = user_doc.get("subscription_expires_at")
    if exp is None:
        return False
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc)


async def _refresh_tier_if_expired(user_doc: dict) -> dict:
    """Demote a user back to 'free' if subscription expired."""
    if user_doc.get("tier") == "coach" and not _is_coach_active(user_doc):
        await db.users.update_one(
            {"user_id": user_doc["user_id"]},
            {"$set": {"tier": "free", "subscription_status": "expired"}},
        )
        user_doc["tier"] = "free"
        user_doc["subscription_status"] = "expired"
    return user_doc


async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "").strip()
    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    user_doc = await _refresh_tier_if_expired(user_doc)
    return _user_to_model(user_doc)


# ---------------- Auth routes ----------------
@api_router.post("/auth/session", response_model=AuthResponse)
async def exchange_session(req: SessionExchangeRequest):
    """Exchange Emergent session_id for our session_token."""
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient(timeout=15) as http_client:
        try:
            resp = await http_client.get(
                EMERGENT_AUTH_SESSION_URL,
                headers={"X-Session-ID": req.session_id},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Auth provider error: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Emergent session")
    data = resp.json()

    email = data["email"]
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture")
    session_token = data["session_token"]

    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc),
            "tier": "free",
            "subscription_status": None,
            "subscription_expires_at": None,
            "coach_bio": None,
            "coach_specialty": None,
            "coach_location": None,
            "coach_public": False,
        }
        await db.users.insert_one(dict(user_doc))
    else:
        await db.users.update_one(
            {"user_id": user_doc["user_id"]},
            {"$set": {"name": name, "picture": picture}},
        )
        user_doc["name"] = name
        user_doc["picture"] = picture
        user_doc = await _refresh_tier_if_expired(user_doc)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {
            "$set": {
                "user_id": user_doc["user_id"],
                "session_token": session_token,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    return AuthResponse(session_token=session_token, user=_user_to_model(user_doc))


@api_router.get("/auth/me", response_model=User)
async def auth_me(user: User = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}


# ---------------- AI core ----------------
SYSTEM_PROMPT_BASE = """You are SurfAI Coach, an elite surfing technique analyst with the experience of a world-tour coach.
You receive a short video of a surfer attempting a wave. Your job is to analyse the surfer's MOVEMENT,
STANCE, BALANCE, TIMING, POP-UP, BOTTOM-TURN, TOP-TURN, RAIL CONTROL and OVERALL FLOW.

Be specific, candid and actionable. Do NOT be generic. If you cannot see a clear surfer in the video,
say so honestly in the summary and use a low score.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema EXACTLY:

{
  "title": "<3-6 word session title>",
  "score": <integer 0-100>,
  "overall_rating": "<one of: Beginner, Intermediate, Advanced, Pro>",
  "summary": "<2-3 sentence overall verdict>",
  "strengths": ["<short bullet>", "..."],
  "mistakes": [
    {
      "title": "<short mistake name>",
      "detail": "<1-2 sentences explaining WHAT is wrong and WHY it hurts performance>",
      "severity": "<low|medium|high>",
      "timestamp": "<mm:ss in the video where it occurs, or null>"
    }
  ],
  "corrections": ["<actionable fix>", "..."],
  "tips": ["<tip>", "..."],
  "drills": ["<drill>", "..."]
}

Provide AT LEAST 3 mistakes (or fewer if surfing is exceptional), 3 corrections, 3 tips, 2 drills."""

SYSTEM_PROMPT_COACH_EXTRA = """

Because this surfer is on the COACH plan, deliver an even DEEPER, more advanced analysis:
- 5+ mistakes with frame-precise timestamps
- 5+ corrections including specific muscle/joint cues
- 5+ tips referencing pro-tour technique vocabulary
- 3+ drills (mix of dry-land, balance-board and in-water)
- Mention specific equipment/board recommendations if visible weaknesses suggest a fin or volume issue."""


def _strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    if "{" in text and "}" in text:
        text = text[text.index("{") : text.rindex("}") + 1]
    return text


async def analyse_video_with_gemini(
    file_path: Path, mime_type: str, deep: bool = False
) -> dict:
    sys_msg = SYSTEM_PROMPT_BASE + (SYSTEM_PROMPT_COACH_EXTRA if deep else "")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"analysis_{uuid.uuid4().hex[:8]}",
        system_message=sys_msg,
    ).with_model("gemini", "gemini-2.5-pro")
    video_file = FileContentWithMimeType(
        file_path=str(file_path), mime_type=mime_type
    )
    msg = UserMessage(
        text="Analyse this surfing clip in depth and respond with the strict JSON schema.",
        file_contents=[video_file],
    )
    response = await chat.send_message(msg)
    raw = response if isinstance(response, str) else str(response)
    cleaned = _strip_json(raw)
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed JSON parse from Gemini: {e}\nRAW={raw[:500]}")
        return {
            "title": "Surfing Session",
            "score": 50,
            "overall_rating": "Intermediate",
            "summary": (raw[:240] if raw else "AI analysis unavailable.").strip(),
            "strengths": [],
            "mistakes": [
                {
                    "title": "Analysis incomplete",
                    "detail": "The AI could not produce structured feedback for this clip.",
                    "severity": "low",
                    "timestamp": None,
                }
            ],
            "corrections": [],
            "tips": [],
            "drills": [],
        }


# ---------------- Analysis routes ----------------
@api_router.get("/analyses/quota")
async def get_quota(user: User = Depends(get_current_user)):
    if user.tier == "coach":
        return {"tier": "coach", "remaining": -1, "limit": -1, "used_today": 0}
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    used = await db.analyses.count_documents(
        {"user_id": user.user_id, "created_at": {"$gte": today_start}}
    )
    return {
        "tier": "free",
        "remaining": max(0, FREE_DAILY_LIMIT - used),
        "limit": FREE_DAILY_LIMIT,
        "used_today": used,
    }


def _coerce_str_list(items) -> List[str]:
    """Gemini sometimes returns dicts inside string-only lists; flatten them."""
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for it in items:
        if isinstance(it, str):
            s = it.strip()
            if s:
                out.append(s)
        elif isinstance(it, dict):
            title = str(it.get("title") or it.get("name") or "").strip()
            detail = str(
                it.get("detail")
                or it.get("description")
                or it.get("text")
                or ""
            ).strip()
            if title and detail:
                out.append(f"{title} — {detail}")
            elif title:
                out.append(title)
            elif detail:
                out.append(detail)
        else:
            out.append(str(it))
    return out


@api_router.post("/analyses", response_model=AnalysisOut)
async def create_analysis(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    # Enforce free-tier daily limit
    if user.tier != "coach":
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        used = await db.analyses.count_documents(
            {"user_id": user.user_id, "created_at": {"$gte": today_start}}
        )
        if used >= FREE_DAILY_LIMIT:
            raise HTTPException(
                status_code=402,
                detail=f"Free plan limit of {FREE_DAILY_LIMIT} analysis per day reached. Upgrade to Coach for unlimited analyses.",
            )

    analysis_id = f"ana_{uuid.uuid4().hex[:14]}"
    ext = (file.filename or "video.mp4").split(".")[-1].lower()
    if ext not in {"mp4", "mov", "m4v", "webm", "avi"}:
        ext = "mp4"
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    save_path = user_dir / f"{analysis_id}.{ext}"

    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    mime = file.content_type or "video/mp4"

    doc = {
        "analysis_id": analysis_id,
        "user_id": user.user_id,
        "video_path": str(save_path),
        "mime_type": mime,
        "status": "processing",
        "created_at": datetime.now(timezone.utc),
        "title": "Analysing...",
        "score": 0,
        "overall_rating": "",
        "summary": "",
        "strengths": [],
        "mistakes": [],
        "corrections": [],
        "tips": [],
        "drills": [],
        "shared_with_coach_id": None,
    }
    await db.analyses.insert_one(dict(doc))

    try:
        result = await analyse_video_with_gemini(
            save_path, mime, deep=(user.tier == "coach")
        )
    except Exception as e:
        logger.exception("AI analysis failed")
        await db.analyses.update_one(
            {"analysis_id": analysis_id},
            {"$set": {"status": "failed", "summary": f"Analysis failed: {e}"}},
        )
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")

    update = {
        "status": "ready",
        "title": result.get("title") or "Surf Session",
        "score": int(result.get("score") or 0),
        "overall_rating": result.get("overall_rating") or "Intermediate",
        "summary": result.get("summary") or "",
        "strengths": _coerce_str_list(result.get("strengths")),
        "mistakes": result.get("mistakes") or [],
        "corrections": _coerce_str_list(result.get("corrections")),
        "tips": _coerce_str_list(result.get("tips")),
        "drills": _coerce_str_list(result.get("drills")),
    }
    await db.analyses.update_one({"analysis_id": analysis_id}, {"$set": update})

    final = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return AnalysisOut(
        **{k: final[k] for k in AnalysisOut.model_fields if k in final}
    )


@api_router.get("/analyses", response_model=List[AnalysisListItem])
async def list_analyses(user: User = Depends(get_current_user)):
    cursor = db.analyses.find(
        {"user_id": user.user_id},
        {
            "_id": 0,
            "analysis_id": 1,
            "title": 1,
            "score": 1,
            "overall_rating": 1,
            "summary": 1,
            "status": 1,
            "created_at": 1,
            "shared_with_coach_id": 1,
        },
    ).sort("created_at", -1)
    items = await cursor.to_list(200)
    return [AnalysisListItem(**i) for i in items]


@api_router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(analysis_id: str, user: User = Depends(get_current_user)):
    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    # Owner can always read; coach can read if shared with them
    if doc.get("user_id") != user.user_id and doc.get("shared_with_coach_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return AnalysisOut(**{k: doc[k] for k in AnalysisOut.model_fields if k in doc})


@api_router.get("/analyses/{analysis_id}/video")
async def get_analysis_video(analysis_id: str, token: Optional[str] = None):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid token")

    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        doc.get("user_id") != session_doc["user_id"]
        and doc.get("shared_with_coach_id") != session_doc["user_id"]
    ):
        raise HTTPException(status_code=404, detail="Not found")
    path = doc.get("video_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Video file missing")
    return FileResponse(path, media_type=doc.get("mime_type") or "video/mp4")


# ---------------- Sharing & Comments ----------------
@api_router.post("/analyses/{analysis_id}/share")
async def share_with_coach(
    analysis_id: str,
    req: ShareRequest,
    user: User = Depends(get_current_user),
):
    doc = await db.analyses.find_one(
        {"analysis_id": analysis_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    coach = await db.users.find_one(
        {"user_id": req.coach_user_id, "tier": "coach"}, {"_id": 0}
    )
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found")
    await db.analyses.update_one(
        {"analysis_id": analysis_id},
        {"$set": {"shared_with_coach_id": req.coach_user_id}},
    )
    return {"ok": True, "coach_user_id": req.coach_user_id}


@api_router.post("/analyses/{analysis_id}/comments", response_model=Comment)
async def add_comment(
    analysis_id: str,
    body: CommentCreate,
    user: User = Depends(get_current_user),
):
    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        doc.get("user_id") != user.user_id
        and doc.get("shared_with_coach_id") != user.user_id
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    comment_id = f"cmt_{uuid.uuid4().hex[:12]}"
    comment = {
        "comment_id": comment_id,
        "analysis_id": analysis_id,
        "author_id": user.user_id,
        "author_name": user.name,
        "author_picture": user.picture,
        "is_coach": user.tier == "coach",
        "text": body.text.strip(),
        "created_at": datetime.now(timezone.utc),
    }
    await db.analysis_comments.insert_one(dict(comment))
    return Comment(**comment)


@api_router.get("/analyses/{analysis_id}/comments", response_model=List[Comment])
async def list_comments(
    analysis_id: str, user: User = Depends(get_current_user)
):
    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        doc.get("user_id") != user.user_id
        and doc.get("shared_with_coach_id") != user.user_id
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    cursor = db.analysis_comments.find(
        {"analysis_id": analysis_id}, {"_id": 0}
    ).sort("created_at", 1)
    items = await cursor.to_list(500)
    return [Comment(**i) for i in items]


# ---------------- Coach routes ----------------
@api_router.get("/coach/inbox", response_model=List[AnalysisListItem])
async def coach_inbox(user: User = Depends(get_current_user)):
    if user.tier != "coach":
        raise HTTPException(status_code=403, detail="Coach plan required")
    cursor = db.analyses.find(
        {"shared_with_coach_id": user.user_id},
        {
            "_id": 0,
            "analysis_id": 1,
            "title": 1,
            "score": 1,
            "overall_rating": 1,
            "summary": 1,
            "status": 1,
            "created_at": 1,
            "shared_with_coach_id": 1,
        },
    ).sort("created_at", -1)
    items = await cursor.to_list(200)
    return [AnalysisListItem(**i) for i in items]


@api_router.put("/coach/profile", response_model=User)
async def update_coach_profile(
    body: CoachProfileUpdate, user: User = Depends(get_current_user)
):
    if user.tier != "coach":
        raise HTTPException(status_code=403, detail="Coach plan required")
    update = {}
    if body.bio is not None:
        update["coach_bio"] = body.bio.strip()[:600]
    if body.specialty is not None:
        update["coach_specialty"] = body.specialty.strip()[:120]
    if body.location is not None:
        update["coach_location"] = body.location.strip()[:120]
    if body.public is not None:
        update["coach_public"] = bool(body.public)
    if update:
        await db.users.update_one({"user_id": user.user_id}, {"$set": update})
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    return _user_to_model(doc)


@api_router.get("/coaches", response_model=List[CoachListItem])
async def list_public_coaches():
    cursor = db.users.find(
        {"tier": "coach", "coach_public": True},
        {
            "_id": 0,
            "user_id": 1,
            "name": 1,
            "picture": 1,
            "coach_bio": 1,
            "coach_specialty": 1,
            "coach_location": 1,
        },
    ).sort("name", 1)
    items = await cursor.to_list(200)
    return [CoachListItem(**i) for i in items]


@api_router.get("/coaches/{user_id}", response_model=CoachListItem)
async def get_public_coach(user_id: str):
    doc = await db.users.find_one(
        {"user_id": user_id, "tier": "coach", "coach_public": True}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Coach not found")
    return CoachListItem(
        user_id=doc["user_id"],
        name=doc["name"],
        picture=doc.get("picture"),
        coach_bio=doc.get("coach_bio"),
        coach_specialty=doc.get("coach_specialty"),
        coach_location=doc.get("coach_location"),
    )


# ---------------- Plans & Stripe ----------------
@api_router.get("/plans")
async def get_plans():
    return {
        "plans": [
            {
                "plan_id": "free",
                "name": "Free",
                "amount": 0.0,
                "currency": "usd",
                "features": [
                    f"{FREE_DAILY_LIMIT} AI video analysis per day",
                    "Standard depth analysis",
                    "Personal session history",
                ],
            },
            {
                "plan_id": "coach",
                "name": "Coach",
                "amount": PLANS["coach"]["amount"],
                "currency": PLANS["coach"]["currency"],
                "features": [
                    "UNLIMITED AI video analyses",
                    "Deeper, frame-precise pro breakdown",
                    "Public coach profile in directory",
                    "Receive shared clips from students",
                    "Comment on student analyses",
                ],
                "interval": "month",
            },
        ],
        "free_daily_limit": FREE_DAILY_LIMIT,
    }


@api_router.post("/payments/checkout", response_model=CheckoutSessionOut)
async def create_checkout(
    req: CheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    if req.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    plan = PLANS[req.plan_id]

    # Build dynamic URLs from frontend origin
    origin = req.origin_url.rstrip("/")
    success_url = f"{origin}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/payment-cancel"

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY, webhook_url=webhook_url
    )

    metadata = {
        "user_id": user.user_id,
        "email": user.email,
        "plan_id": req.plan_id,
        "source": "surfai_mobile",
    }
    checkout_request = CheckoutSessionRequest(
        amount=float(plan["amount"]),
        currency=plan["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe_checkout.create_checkout_session(checkout_request)

    # Store transaction (initiated)
    await db.payment_transactions.insert_one(
        {
            "session_id": session.session_id,
            "user_id": user.user_id,
            "email": user.email,
            "plan_id": req.plan_id,
            "amount": float(plan["amount"]),
            "currency": plan["currency"],
            "metadata": metadata,
            "payment_status": "initiated",
            "status": "open",
            "created_at": datetime.now(timezone.utc),
            "applied": False,
        }
    )

    return CheckoutSessionOut(url=session.url, session_id=session.session_id)


async def _apply_subscription_if_paid(session_id: str) -> dict:
    """Idempotently activate Coach subscription when payment is paid."""
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not txn:
        return {"applied": False, "reason": "txn_not_found"}

    if txn.get("payment_status") == "paid" and txn.get("applied"):
        return {"applied": True, "already": True, "plan_id": txn.get("plan_id")}

    host_dummy = "http://localhost:8001"
    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY, webhook_url=f"{host_dummy}/api/webhook/stripe"
    )
    try:
        status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(
            session_id
        )
        update = {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total": status.amount_total,
            "currency": status.currency,
            "last_checked_at": datetime.now(timezone.utc),
        }
        is_paid = status.payment_status == "paid"
    except Exception as e:
        # emergentintegrations may fail to validate Stripe metadata; degrade gracefully
        logger.warning(f"get_checkout_status failed for {session_id}: {e}")
        update = {"last_checked_at": datetime.now(timezone.utc)}
        is_paid = txn.get("payment_status") == "paid"

    if is_paid and not txn.get("applied"):
        plan_id = txn.get("plan_id")
        if plan_id in PLANS and txn.get("user_id"):
            interval = PLANS[plan_id]["interval_days"]
            now = datetime.now(timezone.utc)
            user_doc = await db.users.find_one(
                {"user_id": txn["user_id"]}, {"_id": 0}
            )
            base_expiry = now
            if user_doc and _is_coach_active(user_doc):
                exp = user_doc.get("subscription_expires_at")
                if isinstance(exp, str):
                    exp = datetime.fromisoformat(exp)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                base_expiry = max(base_expiry, exp)
            new_expiry = base_expiry + timedelta(days=interval)
            await db.users.update_one(
                {"user_id": txn["user_id"]},
                {
                    "$set": {
                        "tier": "coach",
                        "subscription_status": "active",
                        "subscription_expires_at": new_expiry,
                    }
                },
            )
            update["applied"] = True
            update["applied_at"] = now

    await db.payment_transactions.update_one(
        {"session_id": session_id}, {"$set": update}
    )

    txn = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    return {
        "applied": bool(txn.get("applied")),
        "plan_id": txn.get("plan_id"),
        "status": txn.get("status"),
        "payment_status": txn.get("payment_status"),
    }


@api_router.get("/payments/status/{session_id}", response_model=PaymentStatusOut)
async def payment_status(
    session_id: str, user: User = Depends(get_current_user)
):
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await _apply_subscription_if_paid(session_id)
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    return PaymentStatusOut(
        session_id=session_id,
        status=txn.get("status") or "open",
        payment_status=txn.get("payment_status") or "initiated",
        plan_id=txn.get("plan_id"),
        tier="coach" if txn.get("applied") else None,
    )


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    host_url = str(request.base_url).rstrip("/")
    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY, webhook_url=f"{host_url}/api/webhook/stripe"
    )
    try:
        evt = await stripe_checkout.handle_webhook(body, signature)
    except Exception as e:
        logger.warning(f"Webhook verify failed: {e}")
        raise HTTPException(status_code=400, detail="invalid webhook")
    if evt.session_id:
        await _apply_subscription_if_paid(evt.session_id)
    return {"ok": True}


# ---------------- Misc ----------------
@api_router.get("/")
async def root():
    return {"service": "SurfAI", "ok": True}


@api_router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
