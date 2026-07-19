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
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import httpx

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import stripe


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

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
    expo_push_token: Optional[str] = None


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


class PushTokenUpdate(BaseModel):
    token: Optional[str] = None


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
  "drills": ["<concrete drill: dry-land, balance-board or in-water>", "..."]
}

Provide AT LEAST 3 mistakes (or fewer if surfing is exceptional), 3 corrections, 3 tips, 2 drills."""

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


async def _refine_with_claude(raw_analysis: dict, deep: bool = False) -> dict:
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
        "mistakes, corrections, tips, drills.\n"
        " - `mistakes` items must keep keys: title, detail, severity, timestamp.\n"
        " - score: int 0-100. overall_rating: one of "
        "[Beginner, Intermediate, Advanced, Pro].\n"
        " - Tighten wording. Cut filler. Use surf-coach voice (e.g. 'plant your "
        "back foot earlier').\n"
        " - Aim for 4-6 strengths, 3-5 mistakes, 4-6 tips, 2-4 drills.\n"
        " - If draft is empty or low quality, infer reasonable feedback from "
        "any clue (title, summary, score) — do NOT just echo the draft.\n"
        + ("\n - DEEP MODE: add more technical detail per item (3-5 sentences each)."
           if deep else "")
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
    file_path: Path, mime_type: str, deep: bool = False
) -> dict:
    """Try Gemini 2.5 Pro first; fall back to Gemini 2.0 Flash on 400 BadRequest.

    After getting a draft from Gemini, refine it through Claude Sonnet 4.6
    for a more polished, coach-quality response.
    """
    sys_msg = SYSTEM_PROMPT_BASE + (SYSTEM_PROMPT_COACH_EXTRA if deep else "")
    video_file = FileContentWithMimeType(
        file_path=str(file_path), mime_type=mime_type
    )

    draft: dict | None = None
    last_error: Exception | None = None
    for model_name in ("gemini-2.5-pro", "gemini-2.0-flash"):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis_{uuid.uuid4().hex[:8]}",
                system_message=sys_msg,
            ).with_model("gemini", model_name)
            msg = UserMessage(
                text="Analyse this surfing clip in depth and respond with the strict JSON schema.",
                file_contents=[video_file],
            )
            response = await chat.send_message(msg)
            raw = response if isinstance(response, str) else str(response)
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
    polished = await _refine_with_claude(draft, deep=deep)
    return polished


# ---------------- Analysis routes ----------------
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


@api_router.post("/analyses", response_model=AnalysisOut)
async def create_analysis(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    # Enforce limit by tier.
    # Free tier: lifetime cap. Paid tiers: per-day cap.
    # Exclude failed analyses so AI errors don't burn the user's quota.
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

    # Auto-convert non-MP4 formats (especially iPhone .MOV with HEVC) to MP4
    # so Gemini can reliably ingest them. Cheap and fast for short clips.
    if ext != "mp4":
        try:
            mp4_path = user_dir / f"{analysis_id}.mp4"
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(save_path),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "26",
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
                _, err = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                logger.warning("ffmpeg timed out — using original file")
                mp4_path = None
            if mp4_path and mp4_path.exists() and mp4_path.stat().st_size > 0:
                try:
                    save_path.unlink()
                except Exception:
                    pass
                save_path = mp4_path
                mime = "video/mp4"
                logger.info(
                    "Converted %s -> mp4 for analysis_id=%s", ext, analysis_id
                )
            else:
                logger.warning(
                    "ffmpeg conversion failed for analysis_id=%s, err=%s",
                    analysis_id,
                    (err.decode("utf-8", "ignore") if err else "")[:200],
                )
        except FileNotFoundError:
            logger.warning("ffmpeg not installed — skipping conversion")
        except Exception as e:
            logger.exception("ffmpeg conversion error: %s", e)

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

    # Kick off AI analysis in the background so this HTTP request returns
    # quickly (Cloudflare proxy times out at ~100s).
    asyncio.create_task(
        _run_analysis_in_background(
            analysis_id=analysis_id,
            save_path=save_path,
            mime=mime,
            deep=(user.tier == "coach"),
        )
    )

    # Return the in-progress record to the client.
    final = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return AnalysisOut(
        **{k: final[k] for k in AnalysisOut.model_fields if k in final}
    )


async def _run_analysis_in_background(
    analysis_id: str, save_path: Path, mime: str, deep: bool
) -> None:
    """Run Gemini + Claude pipeline and update the analysis doc.

    Runs detached from the HTTP request so the proxy timeout doesn't matter.
    """
    try:
        result = await analyse_video_with_gemini(save_path, mime, deep=deep)
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

    # Send push notification to the OTHER party (clip owner if commenter is coach, vice versa)
    other_user_id = (
        doc["user_id"] if user.user_id != doc["user_id"] else doc.get("shared_with_coach_id")
    )
    if other_user_id:
        other = await db.users.find_one({"user_id": other_user_id}, {"_id": 0})
        token = (other or {}).get("expo_push_token")
        if token:
            who = "Coach " + user.name if user.tier == "coach" else user.name
            preview = body.text.strip()[:80]
            await _send_push_notification(
                token,
                f"New comment from {who}",
                preview,
                {"analysis_id": analysis_id, "type": "comment"},
            )

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


async def _send_push_notification(to_token: str, title: str, body: str, data: dict | None = None):
    """Best-effort push via Expo push service."""
    if not to_token:
        return
    payload = {
        "to": to_token,
        "title": title,
        "body": body,
        "sound": "default",
        "priority": "high",
        "data": data or {},
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client_http:
            await client_http.post(
                "https://exp.host/--/api/v2/push/send",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
    except Exception as e:
        logger.warning(f"Push send failed: {e}")


@api_router.put("/users/push-token", response_model=User)
async def update_push_token(
    body: PushTokenUpdate, user: User = Depends(get_current_user)
):
    token_value = (body.token or "").strip() or None
    await db.users.update_one(
        {"user_id": user.user_id}, {"$set": {"expo_push_token": token_value}}
    )
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    return _user_to_model(doc)


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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
