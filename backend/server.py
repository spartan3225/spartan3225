from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Header, Request, Body, Form
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
import os
import logging
import uuid
import json
import re
import base64
import shutil
import asyncio
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, EmailStr
import httpx

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import stripe


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Pose extraction runs in a dedicated single-worker process pool ---
# MediaPipe/OpenCV are native and hold the GIL; running them in-process (even in
# a thread) stalls the FastAPI event loop and makes concurrent video streaming
# slow / 502. A separate process keeps the API responsive. max_workers=1 bounds
# memory (MediaPipe is heavy).
_pose_pool: Optional[ProcessPoolExecutor] = None


def _pose_worker(path: str) -> dict:
    # Imported inside the child process so the model loads there, not in the API.
    from pose_tracker import extract_pose_data

    return extract_pose_data(path)


def _get_pose_pool() -> ProcessPoolExecutor:
    global _pose_pool
    if _pose_pool is None:
        _pose_pool = ProcessPoolExecutor(max_workers=1)
    return _pose_pool


def _reset_pose_pool() -> None:
    global _pose_pool
    old = _pose_pool
    _pose_pool = None
    if old is not None:
        try:
            old.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
# GridFS bucket for video storage — shared across all deployment replicas
# (local pod disk is NOT shared when the app runs with >1 replica).
gridfs_videos = AsyncIOMotorGridFSBucket(db, bucket_name="videos")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
# Prefer real Stripe secret key when provided; fall back to legacy proxy key
STRIPE_SECRET_KEY = (
    os.environ.get("STRIPE_SECRET_KEY")
    or os.environ.get("STRIPE_API_KEY")
    or ""
)
STRIPE_API_KEY = STRIPE_SECRET_KEY  # keep legacy name in scope
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
stripe.api_key = STRIPE_SECRET_KEY
EMERGENT_AUTH_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)

# Server-defined plans (NEVER trust frontend for amount)
# NOTE: "free" is NOT in PLANS — it has no Stripe checkout. Free tier limit
# is enforced as a *lifetime* cap (1 analysis ever), not a daily cap.
#
# LemonSqueezy is the active payment provider (3 paid tiers).
# Stripe entries are kept for backwards-compat with existing users only.
PLANS: dict[str, dict] = {
    "learn": {
        "name": "LEARN",
        "amount": 15.00,
        "currency": "usd",
        "interval_days": 30,
        "description": "LEARN Plan – Monthly",
        "daily_limit": 1,
    },
    "advanced": {
        "name": "Advanced",
        "amount": 25.00,
        "currency": "usd",
        "interval_days": 30,
        "description": "Advanced Plan – Monthly",
        "daily_limit": 3,
    },
    "pro": {
        "name": "PRO",
        "amount": 35.00,
        "currency": "usd",
        "interval_days": 30,
        "description": "PRO Plan – Monthly",
        "daily_limit": 10,
    },
    # Legacy / hidden tier used internally for community coaches.
    # Not sold via paywall — assigned by admin or via legacy Stripe data.
    "coach": {
        "name": "Coach Elite",
        "amount": 120.00,
        "currency": "usd",
        "interval_days": 30,
        "description": "Coach Elite Plan – Monthly",
        "daily_limit": -1,  # unlimited
    },
}

# Free tier has a LIFETIME cap, not a daily cap.
FREE_LIFETIME_LIMIT = 1

# Daily limits map for paid tiers (free tier handled separately as lifetime).
TIER_DAILY_LIMITS: dict[str, int] = {
    plan_id: plan["daily_limit"] for plan_id, plan in PLANS.items()
}
# Backwards compat for any legacy tier IDs that may still exist in DB.
for legacy_id in ("beginner", "plus", "intermediate"):
    TIER_DAILY_LIMITS.setdefault(legacy_id, 3)

# All tiers that count as "paid" subscriptions (used for expiry checks etc.).
PAID_TIERS = set(PLANS.keys()) | {"beginner", "plus", "intermediate"}

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
    tier: str = "free"
    subscription_status: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    coach_bio: Optional[str] = None
    coach_specialty: Optional[str] = None
    coach_location: Optional[str] = None
    coach_public: bool = False
    preferred_language: str = "en"
    multi_credits: int = 0


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
    scores: Optional[List[dict]] = None
    main_mistake: Optional[dict] = None
    key_moments: Optional[List[dict]] = None
    video_count: Optional[int] = None
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


class CancelRenewalResponse(BaseModel):
    cancel_at_period_end: bool
    subscription_expires_at: Optional[datetime] = None


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
    if user_doc.get("tier") in PAID_TIERS and not _is_paid_active(user_doc):
        await db.users.update_one(
            {"user_id": user_doc["user_id"]},
            {"$set": {"tier": "free", "subscription_status": "expired"}},
        )
        user_doc["tier"] = "free"
        user_doc["subscription_status"] = "expired"
    return user_doc


def _is_paid_active(user_doc: dict) -> bool:
    if user_doc.get("tier") not in PAID_TIERS:
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


# ---- Email/password + Sign in with Apple auth ----
from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()


def _new_session_token() -> str:
    import secrets

    return secrets.token_urlsafe(32)


async def _create_session(user_id: str) -> str:
    token = _new_session_token()
    await db.user_sessions.insert_one(
        {
            "user_id": user_id,
            "session_token": token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "created_at": datetime.now(timezone.utc),
        }
    )
    return token


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    name: Optional[str] = None


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


@api_router.post("/auth/register", response_model=AuthResponse)
async def email_register(req: EmailRegisterRequest):
    email = req.email.lower().strip()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing and existing.get("password_hash"):
        raise HTTPException(
            status_code=409, detail="An account with this email already exists. Please log in."
        )
    password_hash = _password_hasher.hash(req.password)
    if existing:
        # Google-created account adding a password — link, don't duplicate
        await db.users.update_one(
            {"user_id": existing["user_id"]}, {"$set": {"password_hash": password_hash}}
        )
        user_doc = existing
    else:
        user_doc = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": email,
            "name": (req.name or email.split("@")[0]).strip(),
            "picture": None,
            "password_hash": password_hash,
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
    token = await _create_session(user_doc["user_id"])
    return AuthResponse(session_token=token, user=_user_to_model(user_doc))


@api_router.post("/auth/login", response_model=AuthResponse)
async def email_login(req: EmailLoginRequest):
    email = req.email.lower().strip()
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc or not user_doc.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        ok = _password_hasher.verify(req.password, user_doc["password_hash"])
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user_doc = await _refresh_tier_if_expired(user_doc)
    token = await _create_session(user_doc["user_id"])
    return AuthResponse(session_token=token, user=_user_to_model(user_doc))


APPLE_AUDIENCES = [
    a.strip() for a in os.environ.get("APPLE_AUDIENCES", "").split(",") if a.strip()
]
_apple_jwks_client = None


class AppleLoginRequest(BaseModel):
    identity_token: str
    name: Optional[str] = None
    email: Optional[str] = None


@api_router.post("/auth/apple", response_model=AuthResponse)
async def apple_login(req: AppleLoginRequest):
    import jwt as pyjwt
    from jwt import PyJWKClient

    global _apple_jwks_client
    if _apple_jwks_client is None:
        _apple_jwks_client = PyJWKClient("https://appleid.apple.com/auth/keys")
    try:
        signing_key = _apple_jwks_client.get_signing_key_from_jwt(req.identity_token)
        claims = pyjwt.decode(
            req.identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=APPLE_AUDIENCES,
            issuer="https://appleid.apple.com",
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Apple identity token")

    apple_sub = claims["sub"]
    token_email = (claims.get("email") or req.email or "").lower().strip() or None

    user_doc = await db.users.find_one({"apple_sub": apple_sub}, {"_id": 0})
    if not user_doc and token_email:
        # Link to an existing Google/email account with the same email
        user_doc = await db.users.find_one({"email": token_email}, {"_id": 0})
        if user_doc:
            await db.users.update_one(
                {"user_id": user_doc["user_id"]}, {"$set": {"apple_sub": apple_sub}}
            )
    if not user_doc:
        name = (req.name or (token_email.split("@")[0] if token_email else "Surfer")).strip()
        user_doc = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": token_email or f"{apple_sub}@privaterelay.appleid.com",
            "name": name,
            "picture": None,
            "apple_sub": apple_sub,
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
        user_doc = await _refresh_tier_if_expired(user_doc)
    token = await _create_session(user_doc["user_id"])
    return AuthResponse(session_token=token, user=_user_to_model(user_doc))


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
SYSTEM_PROMPT_BASE = """You are SurfCoach23 — an elite, world-tour-grade surf technique analyst.
Your knowledge fuses the methodologies of:
- Martin Dunn (Surfing Coach International) for performance progression frameworks
- Andy King (mentor of John John Florence) for power-surfing & rail engagement
- Carlos Burle (big-wave) for paddle, drop and commitment cues
- Brad Gerlach's "Wave Ki" for body alignment and stance
- Filipe Toledo / Italo Ferreira aerial mechanics
- Kelly Slater's flow & line theory
- Gabriel Medina's barrel reading & turn timing
- ISA / WSL judging criteria (commitment, difficulty, innovation, combination, variety, speed-power-flow)

You receive a short video of a surfer attempting a wave. Your job is to deliver a
PROFESSIONAL, frame-precise analysis of:
- POSITIONING (lineup read, take-off zone)
- POP-UP mechanics (timing, foot placement, hip drive)
- STANCE (front-foot angle, knee bend, hip stack, head over toes)
- BOTTOM TURN (compression, eye-line, rail-set, drive)
- TOP TURN / SNAP (pivot point, weight transfer, recovery)
- CARVE / CUTBACK (arc shape, spray release, re-engagement)
- BARREL RIDING (line, stall, exit)
- AERIALS (launch, rotation, landing)
- RAIL CONTROL & RHYTHM (toe/heel transitions, flow between maneuvers)
- COMMITMENT & RISK (does the surfer go FOR it?)

Be specific, candid and actionable. Reference the body part / board area / wave
section explicitly. Use precise surfing vocabulary (e.g., "lay-back snap",
"floater re-entry", "frontside hack", "stink-bug stance", "trim line").
If you cannot see a clear surfer in the video, say so honestly in the summary
and use a low score.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema EXACTLY:

{
  "title": "<3-6 word session title>",
  "score": <integer 0-100>,
  "overall_rating": "<one of: Beginner, Intermediate, Advanced, Pro>",
  "summary": "<2-3 sentence world-tour-coach verdict>",
  "strengths": ["<short bullet>", "..."],
  "mistakes": [
    {
      "title": "<short mistake name in surf vocabulary>",
      "detail": "<2-3 sentences: WHAT is wrong, WHY it costs power/score, HOW it differs from a Pro reference>",
      "severity": "<low|medium|high>",
      "timestamp": "<mm:ss in the video where it occurs, or null>"
    }
  ],
  "corrections": ["<actionable fix referencing body mechanics>", "..."],
  "tips": ["<world-tour-style tip>", "..."],
  "drills": ["<concrete drill: dry-land, balance-board or in-water>", "..."],
  "scores": [
    {"key": "<one of: surf_flow, take_off, bottom_turn, top_turn, compression, recovery, rail_control, speed_generation, power, timing, balance, style, body_position, wave_reading>",
     "value": <integer 0-100>,
     "note": "<very short verdict, max 6 words, e.g. 'Strong drive off the bottom'>"}
  ],
  "main_mistake": {
    "title": "<short name of the SINGLE biggest mistake>",
    "why": "<WHY it is a mistake, 1-2 sentences>",
    "cause": "<WHAT caused it biomechanically, 1-2 sentences>",
    "performance_lost": "<estimate of performance/score lost, e.g. 'Roughly 15 points of flow lost'>",
    "fix": "<HOW to fix it, 1-2 concrete sentences>",
    "timestamp": "<mm:ss or null>"
  },
  "key_moments": [
    {"timestamp": "<mm:ss>", "label": "<3-5 word moment name, e.g. 'Powerful Bottom Turn'>", "type": "<good|bad|neutral>"}
  ]
}

Provide AT LEAST 3 mistakes (or fewer if surfing is exceptional), EXACTLY 5 corrections
(the top-5 most impactful, ordered by impact), 3 tips, 2 drills.
"scores" MUST contain ALL 14 categories listed above — score each honestly even if
barely visible (use your best estimate). Only include a maneuver-specific category as
0 with note "Not attempted" if truly absent.
"key_moments" MUST contain 4-8 entries covering the whole clip chronologically with
accurate mm:ss timestamps within the actual clip duration."""

SYSTEM_PROMPT_COACH_EXTRA = """

Because this surfer is on the COACH plan, deliver an EVEN DEEPER pro-tour breakdown:
- 5+ mistakes with frame-precise mm:ss timestamps
- 5+ corrections including specific muscle/joint cues (e.g. "shift centre of mass forward 5–8cm over the front foot before bottom-turn release")
- 5+ tips referencing pro-tour technique vocabulary and naming a Pro reference (Toledo / Medina / Italo / John John / Slater / Ramzi Boukhiam) for each
- 3+ drills covering dry-land mobility, balance-board, AND in-water progressions
- Comment on board choice / volume / fin setup if a flaw suggests it
- Apply the WSL judging criteria (commitment, difficulty, innovation, combination, variety, speed/power/flow) score-by-score in the summary."""


def _strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    if "{" in text and "}" in text:
        text = text[text.index("{") : text.rindex("}") + 1]
    return text


LANGUAGE_NAMES = {
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "ru": "Russian",
    "es": "Spanish",
    "pt": "Portuguese",
}


def _lang_instruction(lang: str) -> str:
    name = LANGUAGE_NAMES.get(lang, "English")
    if name == "English":
        return ""
    return (
        f"\n\nCRITICAL LANGUAGE RULE: Write ALL human-readable string values "
        f"(title, summary, strengths, mistake details, corrections, tips, drills, "
        f"score notes, main_mistake texts, key_moment labels) in {name}. "
        f"Keep JSON keys, 'severity', score 'key' values, key_moment 'type' and "
        f"'overall_rating' in English."
    )


async def _refine_with_claude(raw_analysis: dict, deep: bool = False, lang: str = "en") -> dict:
    """Polish Gemini's surf-analysis JSON using Claude Sonnet 4.6.

    Best-effort: if Claude fails for any reason, we return the original Gemini
    output unchanged so user still gets a result.
    """
    refine_prompt = (
        "You are SurfCoach23 — a world-class surf-technique reviewer. "
        "Below is a draft JSON analysis of a surfing clip produced by a vision AI. "
        "Your job: REWRITE it to be more accurate, more actionable, and more "
        "encouraging — while KEEPING THE EXACT SAME JSON SCHEMA. "
        "Rules:\n"
        " - Output ONLY valid JSON, no prose, no markdown fences.\n"
        " - Keep the SAME keys: title, score, overall_rating, summary, strengths, "
        "mistakes, corrections, tips, drills, scores, main_mistake, key_moments.\n"
        " - `mistakes` items must keep keys: title, detail, severity, timestamp.\n"
        " - `scores` items must keep keys: key, value, note (all 14 categories).\n"
        " - `main_mistake` must keep keys: title, why, cause, performance_lost, fix, timestamp.\n"
        " - `key_moments` items must keep keys: timestamp, label, type. Do NOT change timestamps.\n"
        " - `corrections` must be EXACTLY the top 5, ordered by impact.\n"
        " - score: int 0-100. overall_rating: one of "
        "[Beginner, Intermediate, Advanced, Pro].\n"
        " - Tighten wording. Cut filler. Use surf-coach voice (e.g. 'plant your "
        "back foot earlier').\n"
        " - Aim for 4-6 strengths, 3-5 mistakes, 4-6 tips, 2-4 drills.\n"
        " - If draft is empty or low quality, infer reasonable feedback from "
        "any clue (title, summary, score) — do NOT just echo the draft.\n"
        + ("\n - DEEP MODE: add more technical detail per item (3-5 sentences each)."
           if deep else "")
        + _lang_instruction(lang)
    )

    draft_json = json.dumps(raw_analysis, ensure_ascii=False, indent=2)
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"refine_{uuid.uuid4().hex[:8]}",
            system_message=refine_prompt,
        ).with_model("anthropic", "claude-sonnet-4-6")
        msg = UserMessage(
            text=f"DRAFT_JSON:\n{draft_json}\n\nReturn the polished JSON now."
        )
        response = await chat.send_message(msg)
        raw = response if isinstance(response, str) else str(response)
        cleaned = _strip_json(raw)
        polished = json.loads(cleaned)
        # Sanity-check schema; if missing core keys, fall back.
        required = {"title", "score", "overall_rating", "summary"}
        if not isinstance(polished, dict) or not required.issubset(polished.keys()):
            logger.warning("Claude refine returned unexpected schema — keeping draft")
            return raw_analysis
        # Merge: prefer polished fields, fall back to draft where missing
        merged = dict(raw_analysis)
        merged.update({k: v for k, v in polished.items() if v not in (None, "", [])})
        return merged
    except Exception as e:
        logger.warning(f"Claude refinement failed ({type(e).__name__}: {str(e)[:160]}) — using Gemini draft")
        return raw_analysis


async def analyse_video_with_gemini(
    file_path: Path,
    mime_type: str,
    deep: bool = False,
    lang: str = "en",
    extra_files: Optional[List[tuple]] = None,  # [(Path, mime), ...]
) -> dict:
    """Try Gemini 2.5 Pro first; fall back to Gemini 2.0 Flash on 400 BadRequest.

    After getting a draft from Gemini, refine it through Claude Sonnet 4.6
    for a more polished, coach-quality response.
    """
    n_clips = 1 + len(extra_files or [])
    multi_extra = ""
    if n_clips > 1:
        multi_extra = (
            f"\n\nMULTI-CLIP MODE: You receive {n_clips} clips of the SAME surfer "
            "from one session. Produce ONE combined analysis of the surfer, not "
            "one per clip. Judge consistency across all waves (this strongly "
            "informs the 'consistency' of your verdicts and the summary). "
            "All 'timestamp' values (mistakes, main_mistake, key_moments) MUST "
            "refer to the FIRST clip only. When a strength/mistake is clearest "
            "in another clip, mention it in the text (e.g. 'in your second "
            "wave...') without a timestamp."
        )
    sys_msg = (
        SYSTEM_PROMPT_BASE
        + (SYSTEM_PROMPT_COACH_EXTRA if deep else "")
        + multi_extra
        + _lang_instruction(lang)
    )
    file_contents = [
        FileContentWithMimeType(file_path=str(file_path), mime_type=mime_type)
    ]
    for p, m in extra_files or []:
        file_contents.append(
            FileContentWithMimeType(file_path=str(p), mime_type=m)
        )

    draft: dict | None = None
    last_error: Exception | None = None
    for model_name in ("gemini-2.5-pro", "gemini-2.5-flash"):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis_{uuid.uuid4().hex[:8]}",
                system_message=sys_msg,
            ).with_model("gemini", model_name)
            msg = UserMessage(
                text=(
                    "Analyse this surfing clip in depth and respond with the strict JSON schema."
                    if n_clips == 1
                    else f"Analyse these {n_clips} surfing clips of the same surfer as ONE combined session and respond with the strict JSON schema."
                ),
                file_contents=file_contents,
            )
            # Retry transient gateway errors (429/500/503/timeout) up to 3x with
            # exponential backoff. This is the #1 cause of "worked on the 2nd try".
            raw = None
            transient_err: Exception | None = None
            for attempt in range(3):
                try:
                    response = await chat.send_message(msg)
                    raw = response if isinstance(response, str) else str(response)
                    transient_err = None
                    break
                except Exception as se:
                    et = str(se)
                    is_transient = any(
                        code in et
                        for code in ("429", "500", "502", "503", "504",
                                     "overloaded", "Overloaded", "timeout",
                                     "Timeout", "RESOURCE_EXHAUSTED",
                                     "UNAVAILABLE", "rate limit", "Rate limit")
                    )
                    transient_err = se
                    if not is_transient or attempt == 2:
                        raise
                    wait_s = 2 ** attempt + 1  # 2s, 3s, 5s
                    logger.warning(
                        "Gemini %s transient error (attempt %d/3): %s — retrying in %ss",
                        model_name, attempt + 1, et[:160], wait_s,
                    )
                    await asyncio.sleep(wait_s)
            cleaned = _strip_json(raw)
            try:
                draft = json.loads(cleaned)
                logger.info(f"Gemini analysis OK with model={model_name}")
                break
            except Exception as e:
                logger.error(
                    f"Failed JSON parse from {model_name}: {e}\nRAW={raw[:500]}"
                )
                draft = {
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
                break
        except Exception as e:
            last_error = e
            err_text = str(e)
            logger.warning(
                "Gemini model %s failed: %s — trying next model",
                model_name,
                err_text[:200],
            )
            if (
                "BadRequest" not in err_text
                and "INVALID_ARGUMENT" not in err_text
                and "400" not in err_text
            ):
                break

    if draft is None:
        # Both models failed.
        raise last_error or Exception("Gemini analysis failed")

    # Hybrid step: Claude refines Gemini's draft for coach-quality output.
    polished = await _refine_with_claude(draft, deep=deep, lang=lang)
    return polished


# ---------------- Analysis routes ----------------
class PreferencesUpdate(BaseModel):
    language: str


@api_router.put("/users/preferences", response_model=User)
async def update_preferences(
    payload: PreferencesUpdate, user: User = Depends(get_current_user)
):
    lang = payload.language.lower().strip()
    if lang not in LANGUAGE_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    await db.users.update_one(
        {"user_id": user.user_id}, {"$set": {"preferred_language": lang}}
    )
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    return _user_to_model(doc)


@api_router.get("/analyses/quota")
async def get_quota(user: User = Depends(get_current_user)):
    # Free tier: lifetime cap (1 analysis ever) — not daily.
    # Exclude failed analyses so the user isn't penalised when our AI rejects a clip.
    if user.tier == "free":
        used_total = await db.analyses.count_documents(
            {"user_id": user.user_id, "status": {"$ne": "failed"}}
        )
        return {
            "tier": user.tier,
            "remaining": max(0, FREE_LIFETIME_LIMIT - used_total),
            "limit": FREE_LIFETIME_LIMIT,
            "used_today": used_total,
            "is_lifetime": True,
        }

    limit = TIER_DAILY_LIMITS.get(user.tier, FREE_LIFETIME_LIMIT)
    if limit == -1:
        return {
            "tier": user.tier,
            "remaining": -1,
            "limit": -1,
            "used_today": 0,
            "is_lifetime": False,
        }
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    used = await db.analyses.count_documents(
        {
            "user_id": user.user_id,
            "created_at": {"$gte": today_start},
            "status": {"$ne": "failed"},
        }
    )
    return {
        "tier": user.tier,
        "remaining": max(0, limit - used),
        "limit": limit,
        "used_today": used,
        "is_lifetime": False,
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


async def _check_analysis_quota(user: User) -> None:
    """Enforce analysis limits by tier.

    Free tier: lifetime cap. Paid tiers: per-day cap.
    Excludes failed analyses so AI errors don't burn the user's quota.
    """
    if user.tier == "free":
        used_total = await db.analyses.count_documents(
            {"user_id": user.user_id, "status": {"$ne": "failed"}}
        )
        if used_total >= FREE_LIFETIME_LIMIT:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Free plan allows only {FREE_LIFETIME_LIMIT} analysis ever. "
                    "Upgrade to a paid plan to keep analysing."
                ),
            )
    else:
        limit = TIER_DAILY_LIMITS.get(user.tier, FREE_LIFETIME_LIMIT)
        if limit != -1:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            used = await db.analyses.count_documents(
                {
                    "user_id": user.user_id,
                    "created_at": {"$gte": today_start},
                    "status": {"$ne": "failed"},
                }
            )
            if used >= limit:
                tier_label = (user.tier or "free").capitalize()
                raise HTTPException(
                    status_code=402,
                    detail=f"{tier_label} plan limit of {limit} {'analyses' if limit != 1 else 'analysis'} per day reached. Upgrade for more.",
                )


@api_router.post("/analyses", response_model=AnalysisOut)
async def create_analysis(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    await _check_analysis_quota(user)

    analysis_id = f"ana_{uuid.uuid4().hex[:14]}"
    ext = (file.filename or "video.mp4").split(".")[-1].lower()
    if ext not in {"mp4", "mov", "m4v", "webm", "avi"}:
        ext = "mp4"
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    save_path = user_dir / f"{analysis_id}.{ext}"

    with save_path.open("wb") as f:
        written = 0
        while True:
            block = file.file.read(1024 * 1024)
            if not block:
                break
            written += len(block)
            if written > MAX_VIDEO_BYTES:
                f.close()
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail="Video too large (max 300MB)"
                )
            f.write(block)

    mime = file.content_type or "video/mp4"
    return await _finalize_and_start_analysis(user, analysis_id, save_path, ext, mime)


# ---- Chunked upload (bypasses proxy body-size/timeout limits for big clips) ----
# Chunks are stored in MongoDB (NOT local disk) because the deployed app runs
# multiple replicas behind a load balancer — each request can land on a
# different pod, so local disk is not shared.
_UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{16,64}$")
MAX_CHUNK_BYTES = 8 * 1024 * 1024  # 8MB per chunk
MAX_VIDEO_BYTES = 300 * 1024 * 1024  # 300MB assembled clip ceiling


@api_router.post("/uploads/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file: Optional[UploadFile] = File(None),
    chunk_b64: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
):
    if not _UPLOAD_ID_RE.match(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload_id")
    if total_chunks < 1 or total_chunks > 100 or not (0 <= chunk_index < total_chunks):
        raise HTTPException(status_code=400, detail="Invalid chunk index")
    if file is not None:
        data = await file.read()
    elif chunk_b64:
        try:
            data = base64.b64decode(chunk_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 chunk")
    else:
        raise HTTPException(status_code=400, detail="No chunk data")
    if len(data) > MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="Chunk too large (max 8MB)")

    await db.upload_chunks.replace_one(
        {
            "user_id": user.user_id,
            "upload_id": upload_id,
            "chunk_index": chunk_index,
        },
        {
            "user_id": user.user_id,
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "data": data,
            "created_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )
    received = await db.upload_chunks.count_documents(
        {"user_id": user.user_id, "upload_id": upload_id}
    )
    return {"received": received, "total": total_chunks}


class FinalizeUploadIn(BaseModel):
    upload_id: str
    filename: str = "video.mp4"
    mime_type: str = "video/mp4"
    total_chunks: int


@api_router.post("/analyses/finalize", response_model=AnalysisOut)
async def finalize_chunked_upload(
    payload: FinalizeUploadIn,
    user: User = Depends(get_current_user),
):
    if not _UPLOAD_ID_RE.match(payload.upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload_id")
    query = {"user_id": user.user_id, "upload_id": payload.upload_id}
    received = await db.upload_chunks.count_documents(query)
    if received == 0:
        raise HTTPException(status_code=400, detail="Upload not found")
    if received != payload.total_chunks:
        raise HTTPException(
            status_code=400,
            detail=f"Upload incomplete: {received}/{payload.total_chunks} chunks received",
        )

    await _check_analysis_quota(user)

    analysis_id = f"ana_{uuid.uuid4().hex[:14]}"
    ext = (payload.filename or "video.mp4").split(".")[-1].lower()
    if ext not in {"mp4", "mov", "m4v", "webm", "avi"}:
        ext = "mp4"
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    save_path = user_dir / f"{analysis_id}.{ext}"

    cursor = db.upload_chunks.find(query).sort("chunk_index", 1)
    written = 0
    with save_path.open("wb") as out:
        async for part in cursor:
            written += len(part["data"])
            if written > MAX_VIDEO_BYTES:
                out.close()
                save_path.unlink(missing_ok=True)
                await db.upload_chunks.delete_many(query)
                raise HTTPException(
                    status_code=413, detail="Video too large (max 300MB)"
                )
            out.write(part["data"])
    await db.upload_chunks.delete_many(query)

    mime = payload.mime_type or "video/mp4"
    return await _finalize_and_start_analysis(user, analysis_id, save_path, ext, mime)


class MultiFinalizeIn(BaseModel):
    uploads: List[FinalizeUploadIn]


@api_router.post("/analyses/finalize-multi", response_model=AnalysisOut)
async def finalize_multi_upload(
    payload: MultiFinalizeIn,
    user: User = Depends(get_current_user),
):
    """Combine 2-3 chunk-uploaded clips into ONE paid multi-video analysis.

    Consumes 1 multi_credit (bought via LemonSqueezy one-time purchase).
    Does NOT touch the daily quota — it's a separate paid add-on.
    """
    uploads = payload.uploads
    if not 2 <= len(uploads) <= 3:
        raise HTTPException(status_code=400, detail="Provide 2 or 3 clips")
    for up in uploads:
        if not _UPLOAD_ID_RE.match(up.upload_id):
            raise HTTPException(status_code=400, detail="Invalid upload_id")
        q = {"user_id": user.user_id, "upload_id": up.upload_id}
        received = await db.upload_chunks.count_documents(q)
        if received == 0:
            raise HTTPException(status_code=400, detail="Upload not found")
        if received != up.total_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Upload incomplete: {received}/{up.total_chunks} chunks",
            )

    # Atomically consume one credit (race-safe).
    res = await db.users.update_one(
        {"user_id": user.user_id, "multi_credits": {"$gte": 1}},
        {"$inc": {"multi_credits": -1}},
    )
    if res.modified_count == 0:
        raise HTTPException(
            status_code=402,
            detail="No multi-video credits. Purchase one to analyse multiple clips together.",
        )

    analysis_id = f"ana_{uuid.uuid4().hex[:14]}"
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    files: list = []  # (Path, ext, mime)
    try:
        for i, up in enumerate(uploads):
            ext = (up.filename or "video.mp4").split(".")[-1].lower()
            if ext not in {"mp4", "mov", "m4v", "webm", "avi"}:
                ext = "mp4"
            save_path = user_dir / f"{analysis_id}_{i}.{ext}"
            q = {"user_id": user.user_id, "upload_id": up.upload_id}
            cursor = db.upload_chunks.find(q).sort("chunk_index", 1)
            written = 0
            with save_path.open("wb") as out:
                async for part in cursor:
                    written += len(part["data"])
                    if written > MAX_VIDEO_BYTES:
                        raise HTTPException(
                            status_code=413, detail="Video too large (max 300MB)"
                        )
                    out.write(part["data"])
            await db.upload_chunks.delete_many(q)
            files.append((save_path, ext, up.mime_type or "video/mp4"))
    except Exception:
        # Refund the credit if assembly failed.
        await db.users.update_one(
            {"user_id": user.user_id}, {"$inc": {"multi_credits": 1}}
        )
        for p, _, _ in files:
            p.unlink(missing_ok=True)
        raise

    doc = {
        "analysis_id": analysis_id,
        "user_id": user.user_id,
        "video_path": str(files[0][0]),
        "video_paths": [str(p) for p, _, _ in files],
        "video_count": len(files),
        "is_multi": True,
        "mime_type": files[0][2],
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

    # PERSISTENCE-FIRST: store every raw clip to GridFS synchronously before any
    # conversion / AI work, so clips can never be lost on a restart/OOM.
    for i, (p, _, _) in enumerate(files):
        await _store_video_in_gridfs(f"{analysis_id}_{i}", p)

    asyncio.create_task(
        _run_multi_analysis_in_background(
            analysis_id=analysis_id,
            files=files,
            deep=(user.tier == "coach"),
            lang=(user.preferred_language or "en"),
        )
    )

    final = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return AnalysisOut(
        **{k: final[k] for k in AnalysisOut.model_fields if k in final}
    )


async def _finalize_and_start_analysis(
    user: User, analysis_id: str, save_path: Path, ext: str, mime: str
) -> AnalysisOut:
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

    # Post-insert quota guard: closes the race where several simultaneous
    # uploads all pass the pre-check. Counting AFTER insert is authoritative —
    # if the cap is now exceeded, roll this one back (fail-closed).
    if user.tier == "free":
        cap = FREE_LIFETIME_LIMIT
        total_now = await db.analyses.count_documents(
            {"user_id": user.user_id, "status": {"$ne": "failed"}}
        )
    else:
        cap = TIER_DAILY_LIMITS.get(user.tier, FREE_LIFETIME_LIMIT)
        if cap == -1:
            total_now = 0
        else:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            total_now = await db.analyses.count_documents(
                {
                    "user_id": user.user_id,
                    "created_at": {"$gte": today_start},
                    "status": {"$ne": "failed"},
                }
            )
    if cap != -1 and total_now > cap:
        await db.analyses.delete_one({"analysis_id": analysis_id})
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=402,
            detail="Plan limit reached. Upgrade for more analyses.",
        )

    # PERSISTENCE-FIRST: store the raw uploaded video to GridFS synchronously,
    # BEFORE any conversion / AI / pose work. GridFS lives in MongoDB (shared,
    # permanent) so the clip can NEVER be lost even if this pod restarts, runs
    # out of memory during analysis, or the request lands on another replica
    # later. Background conversion re-stores the mp4 version under the same name.
    await _store_video_in_gridfs(analysis_id, save_path)

    # Kick off conversion + AI analysis in the background so this HTTP request
    # returns instantly (Cloudflare proxy times out at ~100s, and ffmpeg can be
    # slow on small deployment pods).
    asyncio.create_task(
        _run_analysis_in_background(
            analysis_id=analysis_id,
            save_path=save_path,
            mime=mime,
            deep=(user.tier == "coach"),
            ext=ext,
            lang=(user.preferred_language or "en"),
        )
    )

    # Return the in-progress record to the client.
    final = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return AnalysisOut(
        **{k: final[k] for k in AnalysisOut.model_fields if k in final}
    )


def _resolve_ffmpeg() -> Optional[str]:
    """Return a usable ffmpeg executable path.

    Prefer the system ffmpeg; if it isn't installed (some slim containers omit
    it), fall back to the binary bundled with the `imageio-ffmpeg` package so
    iPhone .MOV/HEVC conversion never silently breaks.
    """
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


async def _convert_to_mp4_if_needed(
    analysis_id: str, save_path: Path, ext: str, mime: str
) -> tuple[Path, str]:
    """Convert non-MP4 clips (especially iPhone .MOV/HEVC) to MP4 for Gemini.

    Runs in the background task — never inside an HTTP request — because
    ffmpeg can take minutes on small deployment pods.
    """
    if ext == "mp4":
        return save_path, mime
    ffmpeg_bin = _resolve_ffmpeg()
    if not ffmpeg_bin:
        logger.warning("ffmpeg unavailable (system + bundled) — using original file")
        return save_path, mime
    try:
        mp4_path = save_path.parent / f"{analysis_id}.mp4"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            "-y",
            "-i",
            str(save_path),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "26",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-loglevel",
            "error",
            str(mp4_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=600)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            logger.warning("ffmpeg timed out — using original file")
            return save_path, mime
        if mp4_path.exists() and mp4_path.stat().st_size > 0:
            try:
                save_path.unlink()
            except Exception:
                pass
            logger.info("Converted %s -> mp4 for analysis_id=%s", ext, analysis_id)
            return mp4_path, "video/mp4"
        logger.warning(
            "ffmpeg conversion failed for analysis_id=%s, err=%s",
            analysis_id,
            (err.decode("utf-8", "ignore") if err else "")[:200],
        )
    except FileNotFoundError:
        logger.warning("ffmpeg not installed — skipping conversion")
    except Exception as e:
        logger.exception("ffmpeg conversion error: %s", e)
    return save_path, mime


async def _store_video_in_gridfs(analysis_id: str, path: Path) -> bool:
    """Persist the video to GridFS so ANY replica can stream it later.

    Local pod disk is not shared between deployment replicas. Retries once on
    failure. Returns True if the video is confirmed stored.
    """
    for attempt in range(2):
        try:
            if not path.exists() or path.stat().st_size == 0:
                logger.warning("GridFS skip: file missing/empty %s", path)
                return False
            # Remove any prior copy under this name (idempotent re-store).
            async for f in db["videos.files"].find({"filename": analysis_id}, {"_id": 1}):
                try:
                    await gridfs_videos.delete(f["_id"])
                except Exception:
                    pass
            with path.open("rb") as fh:
                await gridfs_videos.upload_from_stream(analysis_id, fh)
            # Verify it landed.
            exists = await db["videos.files"].find_one(
                {"filename": analysis_id}, {"_id": 1}
            )
            if exists:
                return True
        except Exception:
            logger.exception(
                "GridFS store failed for %s (attempt %d/2)", analysis_id, attempt + 1
            )
        await asyncio.sleep(1)
    return False


async def _run_analysis_in_background(
    analysis_id: str,
    save_path: Path,
    mime: str,
    deep: bool,
    ext: str = "mp4",
    lang: str = "en",
) -> None:
    """Convert (if needed) then run Gemini + Claude pipeline and update the doc.

    Runs detached from the HTTP request so the proxy timeout doesn't matter.
    """
    try:
        save_path, mime = await _convert_to_mp4_if_needed(
            analysis_id, save_path, ext, mime
        )
        await db.analyses.update_one(
            {"analysis_id": analysis_id},
            {"$set": {"video_path": str(save_path), "mime_type": mime}},
        )
        await _store_video_in_gridfs(analysis_id, save_path)
    except Exception:
        logger.exception("Background conversion step failed — using original file")

    try:
        # Hard timeout so an analysis can never hang forever
        result = await asyncio.wait_for(
            analyse_video_with_gemini(save_path, mime, deep=deep, lang=lang),
            timeout=900,
        )
    except Exception as e:
        logger.exception("AI analysis failed (background)")
        await db.analyses.update_one(
            {"analysis_id": analysis_id},
            {
                "$set": {
                    "status": "failed",
                    "summary": (
                        "We couldn't analyse this clip. Try a shorter video "
                        "(under 60 seconds, MP4, under 50MB)."
                    ),
                    "error": str(e)[:300],
                }
            },
        )
        return

    await _apply_ai_result(analysis_id, result)

    # --- Skeleton tracking (Phase 2) ---
    # Runs AFTER the AI result is saved so the user sees feedback ASAP; pose
    # overlay appears when ready. CPU-bound → thread, with a hard timeout.
    await _run_pose_extraction(analysis_id, save_path)


async def _apply_ai_result(analysis_id: str, result: dict) -> None:
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
        "scores": _sanitize_scores(result.get("scores")),
        "main_mistake": result.get("main_mistake")
        if isinstance(result.get("main_mistake"), dict)
        else None,
        "key_moments": _sanitize_key_moments(result.get("key_moments")),
    }
    await db.analyses.update_one({"analysis_id": analysis_id}, {"$set": update})


async def _run_multi_analysis_in_background(
    analysis_id: str,
    files: list,  # [(Path, ext, mime), ...] in clip order
    deep: bool,
    lang: str = "en",
) -> None:
    """Convert + GridFS-store every clip, then run ONE combined AI analysis."""
    converted: list = []  # [(Path, mime), ...]
    for i, (path, ext, mime) in enumerate(files):
        try:
            new_path, new_mime = await _convert_to_mp4_if_needed(
                f"{analysis_id}_{i}", path, ext, mime
            )
        except Exception:
            logger.exception("Multi conversion failed for clip %d — using original", i)
            new_path, new_mime = path, mime
        converted.append((new_path, new_mime))
        await _store_video_in_gridfs(f"{analysis_id}_{i}", new_path)

    await db.analyses.update_one(
        {"analysis_id": analysis_id},
        {
            "$set": {
                "video_paths": [str(p) for p, _ in converted],
                "video_path": str(converted[0][0]),
                "mime_type": converted[0][1],
            }
        },
    )

    try:
        result = await asyncio.wait_for(
            analyse_video_with_gemini(
                converted[0][0],
                converted[0][1],
                deep=deep,
                lang=lang,
                extra_files=converted[1:],
            ),
            timeout=1200,
        )
    except Exception as e:
        logger.exception("Multi AI analysis failed (background)")
        await db.analyses.update_one(
            {"analysis_id": analysis_id},
            {
                "$set": {
                    "status": "failed",
                    "summary": (
                        "We couldn't analyse these clips. Try shorter videos "
                        "(under 60 seconds each, MP4)."
                    ),
                    "error": str(e)[:300],
                }
            },
        )
        # Refund the paid credit — the user got nothing.
        doc = await db.analyses.find_one(
            {"analysis_id": analysis_id}, {"_id": 0, "user_id": 1}
        )
        if doc:
            await db.users.update_one(
                {"user_id": doc["user_id"]}, {"$inc": {"multi_credits": 1}}
            )
        return

    await _apply_ai_result(analysis_id, result)
    await _run_pose_extraction(analysis_id, converted[0][0])


async def _run_pose_extraction(analysis_id: str, save_path: Path) -> None:
    try:
        await db.analyses.update_one(
            {"analysis_id": analysis_id}, {"$set": {"pose_status": "processing"}}
        )

        # Retry once: MediaPipe can occasionally fail on the first pass
        # (transient decode/memory hiccup) but succeed on a clean retry.
        data = None
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                # Run in a SEPARATE PROCESS (not a thread): MediaPipe/OpenCV are
                # native C extensions that hold the GIL during CPU work, which
                # would otherwise stall the web server's event loop and make
                # concurrent video streaming slow / 502. A process pool keeps
                # the API responsive while pose extraction runs.
                loop = asyncio.get_running_loop()
                data = await asyncio.wait_for(
                    loop.run_in_executor(
                        _get_pose_pool(), _pose_worker, str(save_path)
                    ),
                    timeout=300,
                )
                if data and data.get("frames"):
                    break
                last_err = RuntimeError("no pose frames detected")
            except Exception as e:
                last_err = e
                logger.warning(
                    "pose extraction attempt %d/2 failed for %s: %s",
                    attempt + 1, analysis_id, str(e)[:160],
                )
                # A crashed worker breaks the pool — rebuild it for the retry.
                _reset_pose_pool()
            await asyncio.sleep(1)
        if not data or not data.get("frames"):
            raise last_err or RuntimeError("no pose frames detected")
        await db.pose_data.replace_one(
            {"analysis_id": analysis_id},
            {"analysis_id": analysis_id, "data": data,
             "created_at": datetime.now(timezone.utc)},
            upsert=True,
        )
        await db.analyses.update_one(
            {"analysis_id": analysis_id}, {"$set": {"pose_status": "ready"}}
        )
    except Exception as e:
        logger.warning("pose extraction failed for %s: %s", analysis_id, str(e)[:200])
        await db.analyses.update_one(
            {"analysis_id": analysis_id}, {"$set": {"pose_status": "failed"}}
        )


def _sanitize_scores(raw) -> list:
    """Keep only well-formed {key, value, note} entries."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        try:
            value = max(0, min(100, int(item.get("value"))))
        except (TypeError, ValueError):
            continue
        if not key:
            continue
        out.append({"key": key, "value": value, "note": str(item.get("note") or "")[:120]})
    return out


def _sanitize_key_moments(raw) -> list:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("timestamp") or "").strip()
        label = str(item.get("label") or "").strip()
        if not ts or not label:
            continue
        mtype = str(item.get("type") or "neutral").lower()
        if mtype not in ("good", "bad", "neutral"):
            mtype = "neutral"
        out.append({"timestamp": ts, "label": label[:80], "type": mtype})
    return out[:10]


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


STALE_PROCESSING_MINUTES = 20


async def _fail_if_stale(doc: dict) -> dict:
    """Lazy watchdog: if a pod died mid-analysis, the doc stays 'processing'
    forever. Detect it on read (works across replicas, no restart needed)."""
    if doc.get("status") != "processing":
        return doc
    created = doc.get("created_at")
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except ValueError:
            return doc
    if created is None:
        return doc
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created < datetime.now(timezone.utc) - timedelta(minutes=STALE_PROCESSING_MINUTES):
        await db.analyses.update_one(
            {"analysis_id": doc["analysis_id"], "status": "processing"},
            {
                "$set": {
                    "status": "failed",
                    "error": "Analysis was interrupted. Please upload your clip again — this attempt did not use your quota.",
                }
            },
        )
        doc["status"] = "failed"
    return doc


# ---------------- Pro Reference clips (royalty-free, skeleton-tracked) ----------------
# Real surf footage sourced from Pexels (Free-to-use / commercial license).
# Clips + precomputed MediaPipe pose JSON live in static_assets/pro/.
PRO_ASSETS_DIR = ROOT_DIR / "static_assets" / "pro"
PRO_CLIP_IDS = {"8775726", "4927323", "4929633", "14435086"}


@api_router.get("/pro/{clip_id}/video")
async def get_pro_video(clip_id: str):
    if clip_id not in PRO_CLIP_IDS:
        raise HTTPException(status_code=404, detail="Not found")
    path = PRO_ASSETS_DIR / f"small_{clip_id}.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Clip missing")
    return FileResponse(path, media_type="video/mp4")


@api_router.get("/pro/{clip_id}/pose")
async def get_pro_pose(clip_id: str):
    if clip_id not in PRO_CLIP_IDS:
        raise HTTPException(status_code=404, detail="Not found")
    path = PRO_ASSETS_DIR / f"pose_{clip_id}.json"
    if not path.is_file():
        return {"status": "none", "data": None}
    try:
        with path.open("r") as f:
            return {"status": "ready", "data": json.load(f)}
    except Exception:
        return {"status": "failed", "data": None}


@api_router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(analysis_id: str, user: User = Depends(get_current_user)):
    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    # Owner can always read; coach can read if shared with them
    if doc.get("user_id") != user.user_id and doc.get("shared_with_coach_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await _fail_if_stale(doc)
    return AnalysisOut(**{k: doc[k] for k in AnalysisOut.model_fields if k in doc})


@api_router.get("/analyses/{analysis_id}/pose")
async def get_analysis_pose(
    analysis_id: str, user: User = Depends(get_current_user)
):
    doc = await db.analyses.find_one(
        {"analysis_id": analysis_id},
        {"_id": 0, "user_id": 1, "shared_with_coach_id": 1, "pose_status": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        doc.get("user_id") != user.user_id
        and doc.get("shared_with_coach_id") != user.user_id
    ):
        raise HTTPException(status_code=404, detail="Not found")
    status = doc.get("pose_status") or "none"
    if status != "ready":
        return {"status": status, "data": None}
    pose_doc = await db.pose_data.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not pose_doc:
        return {"status": "failed", "data": None}
    return {"status": "ready", "data": pose_doc["data"]}


@api_router.get("/analyses/{analysis_id}/video")
async def get_analysis_video(
    analysis_id: str, token: Optional[str] = None, index: int = 0
):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid token")
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    doc = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        doc.get("user_id") != session_doc["user_id"]
        and doc.get("shared_with_coach_id") != session_doc["user_id"]
    ):
        raise HTTPException(status_code=404, detail="Not found")
    # Multi-video analyses: pick the requested clip (index 0..2).
    video_paths = doc.get("video_paths") or []
    gridfs_name = analysis_id
    path = doc.get("video_path")
    if video_paths:
        idx = max(0, min(index, len(video_paths) - 1))
        path = video_paths[idx]
        gridfs_name = f"{analysis_id}_{idx}"
    if path and Path(path).exists():
        return FileResponse(path, media_type=doc.get("mime_type") or "video/mp4")

    # Multi-replica fallback: this pod doesn't have the file locally — stream
    # it from GridFS (shared storage in MongoDB).
    try:
        grid_out = await gridfs_videos.open_download_stream_by_name(gridfs_name)
    except Exception:
        raise HTTPException(status_code=404, detail="Video file missing")

    async def _iter_gridfs():
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        _iter_gridfs(), media_type=doc.get("mime_type") or "video/mp4"
    )


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
async def list_public_coaches(
    q: Optional[str] = None,
    location: Optional[str] = None,
    specialty: Optional[str] = None,
):
    query: dict = {"tier": "coach", "coach_public": True}
    if location:
        query["coach_location"] = {"$regex": location, "$options": "i"}
    if specialty:
        query["coach_specialty"] = {"$regex": specialty, "$options": "i"}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"coach_bio": {"$regex": q, "$options": "i"}},
            {"coach_specialty": {"$regex": q, "$options": "i"}},
            {"coach_location": {"$regex": q, "$options": "i"}},
        ]
    cursor = db.users.find(
        query,
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
    plans_out = [
        {
            "plan_id": "free",
            "name": "Free",
            "amount": 0.0,
            "currency": "usd",
            "features": [
                f"{FREE_LIFETIME_LIMIT} AI video analysis (lifetime)",
                "Standard depth analysis",
                "Personal session history",
            ],
            "daily_limit": FREE_LIFETIME_LIMIT,
            "is_lifetime": True,
        },
        {
            "plan_id": "learn",
            "name": "LEARN",
            "amount": PLANS["learn"]["amount"],
            "currency": PLANS["learn"]["currency"],
            "features": [
                f"{PLANS['learn']['daily_limit']} AI analysis per day",
                "Standard depth analysis",
                "Personal session history",
            ],
            "daily_limit": PLANS["learn"]["daily_limit"],
            "interval": "month",
        },
        {
            "plan_id": "advanced",
            "name": "Advanced",
            "amount": PLANS["advanced"]["amount"],
            "currency": PLANS["advanced"]["currency"],
            "features": [
                f"{PLANS['advanced']['daily_limit']} AI analyses per day",
                "Deeper technical breakdown",
                "Priority queue",
                "Browse public coach directory",
            ],
            "daily_limit": PLANS["advanced"]["daily_limit"],
            "interval": "month",
        },
        {
            "plan_id": "pro",
            "name": "PRO",
            "amount": PLANS["pro"]["amount"],
            "currency": PLANS["pro"]["currency"],
            "features": [
                f"{PLANS['pro']['daily_limit']} AI analyses per day",
                "Pro-tour deeper breakdown",
                "Top-priority queue",
                "Browse public coach directory",
                "Share clips with any coach",
            ],
            "daily_limit": PLANS["pro"]["daily_limit"],
            "interval": "month",
        },
    ]
    return {
        "plans": plans_out,
        "free_lifetime_limit": FREE_LIFETIME_LIMIT,
        "free_daily_limit": FREE_LIFETIME_LIMIT,  # legacy key for old clients
        "provider": "lemonsqueezy",
    }


@api_router.post("/payments/checkout", response_model=CheckoutSessionOut)
async def create_checkout(
    req: CheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """DEPRECATED — use /api/payments/lemonsqueezy/checkout instead.

    Kept for backwards compatibility with very old app builds. New clients are
    routed through the LemonSqueezy router which supports Apple Pay, Google
    Pay, mada, and credit cards via a Saudi-licensed processor.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "This payment endpoint is no longer supported. "
            "Please update the app to the latest version."
        ),
    )


# ─── Legacy Stripe handler removed (replaced by LemonSqueezy) ───────────────


async def _apply_subscription_if_paid(
    session_id: str, event_paid: bool = False
) -> dict:
    """Idempotently activate subscription when payment is paid.

    event_paid: when True (e.g. webhook for checkout.session.completed with
    payment_status='paid'), trust this as ground truth even if Stripe.retrieve
    is briefly out of sync.
    """
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not txn:
        return {"applied": False, "reason": "txn_not_found"}

    if txn.get("payment_status") == "paid" and txn.get("applied"):
        return {"applied": True, "already": True, "plan_id": txn.get("plan_id")}

    is_paid = event_paid
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        update = {
            "status": s.status,
            "payment_status": s.payment_status,
            "amount_total": s.amount_total,
            "currency": s.currency,
            "last_checked_at": datetime.now(timezone.utc),
        }
        if s.payment_status == "paid":
            is_paid = True
    except Exception as e:
        logger.warning(f"Stripe retrieve failed for {session_id}: {e}")
        update = {"last_checked_at": datetime.now(timezone.utc)}
        if not is_paid:
            is_paid = txn.get("payment_status") == "paid"
    if event_paid:
        update["payment_status"] = "paid"
        update["status"] = update.get("status") or "complete"

    if is_paid and not txn.get("applied"):
        plan_id = txn.get("plan_id")
        if plan_id in PLANS and txn.get("user_id"):
            interval = PLANS[plan_id]["interval_days"]
            now = datetime.now(timezone.utc)
            user_doc = await db.users.find_one(
                {"user_id": txn["user_id"]}, {"_id": 0}
            )
            base_expiry = now
            if user_doc and _is_paid_active(user_doc):
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
                        "tier": plan_id,
                        "subscription_status": "active",
                        "subscription_expires_at": new_expiry,
                        "cancel_at_period_end": False,
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
    applied = bool(txn.get("applied"))
    return PaymentStatusOut(
        session_id=session_id,
        status=txn.get("status") or "open",
        payment_status=txn.get("payment_status") or "initiated",
        plan_id=txn.get("plan_id"),
        tier=txn.get("plan_id") if applied else None,
    )


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.warning(f"Webhook parsing failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")

    try:
        event_type = event["type"]
        obj = event["data"]["object"]
    except Exception:
        # Newer stripe SDK Event objects expose attrs not items
        event_type = getattr(event, "type", None)
        data = getattr(event, "data", None)
        obj = getattr(data, "object", None) if data is not None else None
    if not event_type or obj is None:
        logger.warning("Webhook event missing type/object")
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    logger.info(f"Stripe webhook received: {event_type}")

    # NB: `obj` is a stripe.StripeObject (dict-like) but its custom __getattr__
    # makes `.get(...)` unreliable; use bracket-style access.
    def _obj_id(o) -> Optional[str]:
        if o is None:
            return None
        try:
            v = o["id"]
            if v:
                return v
        except (KeyError, TypeError):
            pass
        return getattr(o, "id", None)

    if event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    ):
        session_id = _obj_id(obj)
        if session_id:
            # Trust the event's payment_status as ground truth
            obj_paid = False
            try:
                obj_paid = obj["payment_status"] == "paid"
            except (KeyError, TypeError):
                obj_paid = getattr(obj, "payment_status", None) == "paid"
            await _apply_subscription_if_paid(session_id, event_paid=obj_paid)
    elif event_type == "checkout.session.async_payment_failed":
        session_id = _obj_id(obj)
        if session_id:
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "failed", "status": "expired"}},
            )

    return {"ok": True, "type": event_type}


@api_router.delete("/auth/account")
async def delete_account(user: User = Depends(get_current_user)):
    """Permanently delete the user's account and all associated data.

    Required by Apple App Store review for apps with account creation.
    """
    uid = user.user_id
    async for a in db.analyses.find(
        {"user_id": uid}, {"analysis_id": 1, "video_path": 1}
    ):
        vp = a.get("video_path")
        if vp:
            Path(vp).unlink(missing_ok=True)
        async for f in db["videos.files"].find(
            {"filename": a["analysis_id"]}, {"_id": 1}
        ):
            try:
                await gridfs_videos.delete(f["_id"])
            except Exception:
                pass
    await db.analyses.delete_many({"user_id": uid})
    await db.analysis_comments.delete_many(
        {"$or": [{"author_id": uid}, {"user_id": uid}]}
    )
    await db.upload_chunks.delete_many({"user_id": uid})
    await db.user_sessions.delete_many({"user_id": uid})
    await db.users.delete_one({"user_id": uid})
    shutil.rmtree(UPLOAD_DIR / uid, ignore_errors=True)
    logger.info("Account deleted: %s", uid)
    return {"ok": True}


@api_router.post("/payments/cancel-renewal", response_model=CancelRenewalResponse)
async def cancel_renewal(user: User = Depends(get_current_user)):
    if user.tier not in PAID_TIERS:
        raise HTTPException(status_code=400, detail="No active subscription")
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"cancel_at_period_end": True, "subscription_status": "canceled"}},
    )
    return CancelRenewalResponse(
        cancel_at_period_end=True,
        subscription_expires_at=user.subscription_expires_at,
    )


@api_router.post("/payments/resume-renewal", response_model=CancelRenewalResponse)
async def resume_renewal(user: User = Depends(get_current_user)):
    if user.tier not in PAID_TIERS:
        raise HTTPException(status_code=400, detail="No active subscription")
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"cancel_at_period_end": False, "subscription_status": "active"}},
    )
    return CancelRenewalResponse(
        cancel_at_period_end=False,
        subscription_expires_at=user.subscription_expires_at,
    )


# ---------------- Misc ----------------
@api_router.get("/")
async def root():
    return {"service": "SurfAI", "ok": True}


@api_router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# Wire LemonSqueezy endpoints onto api_router BEFORE include_router.
try:
    from routers import lemonsqueezy as _lemonsqueezy

    _lemonsqueezy.attach(
        app_router=api_router,
        db=db,
        get_current_user=get_current_user,
        paid_tiers_setter=lambda extra: PAID_TIERS.update(extra),
    )
except Exception as _e:  # pragma: no cover
    logging.getLogger("surfai").exception("Failed to attach LemonSqueezy router: %s", _e)


app.include_router(api_router)

# ---- Serve the exported Expo web build (landing, terms, privacy, refund) ----
# On mobile deployments only the backend is exposed publicly, so the backend
# serves the static web export at the root path. Generated via:
#   npx expo export --platform web --output-dir /app/backend/static_web
STATIC_WEB_DIR = ROOT_DIR / "static_web"

if STATIC_WEB_DIR.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_web_app(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        base = STATIC_WEB_DIR.resolve()
        target = (base / full_path).resolve() if full_path else base / "index.html"
        try:
            target.relative_to(base)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path and target.is_file():
            return FileResponse(target)
        html = (base / f"{full_path}.html") if full_path else (base / "index.html")
        if html.is_file():
            return FileResponse(html)
        # SPA fallback: let expo-router handle the route client-side
        return FileResponse(base / "index.html")

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


@app.on_event("startup")
async def _ensure_indexes():
    try:
        # Apple review demo account must never hit a quota wall (no way to
        # pay inside the iOS app). Idempotent: only bumps the free tier.
        await db.users.update_one(
            {"email": "qa.tester@surfcoach23.com", "tier": "free"},
            {"$set": {"tier": "pro", "subscription_status": "active"}},
        )
    except Exception:
        logging.getLogger("surfai").warning(
            "reviewer account upgrade failed", exc_info=True
        )
    try:
        # Auth indexes: fast session lookup + automatic expiry cleanup.
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("user_id")
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
        await db.users.create_index("user_id", unique=True)
    except Exception:
        logging.getLogger("surfai").warning(
            "auth index creation failed", exc_info=True
        )
    try:
        # Orphaned chunks auto-expire after 24h
        await db.upload_chunks.create_index(
            "created_at", expireAfterSeconds=86400
        )
        await db.upload_chunks.create_index(
            [("user_id", 1), ("upload_id", 1), ("chunk_index", 1)], unique=True
        )
    except Exception:
        logging.getLogger("surfai").warning(
            "upload_chunks index creation failed", exc_info=True
        )
    try:
        # Crash recovery: if a pod died mid-analysis (OOM/restart), the doc
        # stays 'processing' forever. Mark stale ones failed so they don't
        # hang the UI or burn the user's quota (failed doesn't count).
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        res = await db.analyses.update_many(
            {"status": "processing", "created_at": {"$lt": cutoff}},
            {
                "$set": {
                    "status": "failed",
                    "error": "Analysis was interrupted by a server restart. Please upload your clip again — this attempt did not use your quota.",
                }
            },
        )
        if res.modified_count:
            logging.getLogger("surfai").info(
                "Marked %d stale processing analyses as failed", res.modified_count
            )
    except Exception:
        logging.getLogger("surfai").warning(
            "stale analysis cleanup failed", exc_info=True
        )


@app.on_event("shutdown")
async def shutdown_db_client():
    _reset_pose_pool()
    client.close()
