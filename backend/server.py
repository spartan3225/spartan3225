from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Header, Request
from fastapi.responses import FileResponse, JSONResponse
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


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
EMERGENT_AUTH_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)

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


class SessionExchangeRequest(BaseModel):
    session_id: str


class AuthResponse(BaseModel):
    session_token: str
    user: User


class Mistake(BaseModel):
    title: str
    detail: str
    severity: str  # "low" | "medium" | "high"
    timestamp: Optional[str] = None  # mm:ss in video


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


class AnalysisListItem(BaseModel):
    analysis_id: str
    title: str
    score: int
    overall_rating: str
    summary: str
    status: str
    created_at: datetime


# ---------------- Auth helpers ----------------
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
    return User(**user_doc)


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

    # Find or create user
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(dict(user_doc))
    else:
        # update name/picture
        await db.users.update_one(
            {"user_id": user_doc["user_id"]},
            {"$set": {"name": name, "picture": picture}},
        )
        user_doc["name"] = name
        user_doc["picture"] = picture

    # Save session (7 days)
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

    return AuthResponse(session_token=session_token, user=User(**user_doc))


@api_router.get("/auth/me", response_model=User)
async def auth_me(user: User = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}


# ---------------- Analysis core ----------------
SYSTEM_PROMPT = """You are SurfAI Coach, an elite surfing technique analyst with the experience of a world-tour coach.
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
  "strengths": ["<short bullet>", "<short bullet>", "..."],
  "mistakes": [
    {
      "title": "<short mistake name>",
      "detail": "<1-2 sentences explaining WHAT is wrong and WHY it hurts performance>",
      "severity": "<low|medium|high>",
      "timestamp": "<mm:ss in the video where it occurs, or null>"
    }
  ],
  "corrections": ["<actionable fix 1>", "<actionable fix 2>", "..."],
  "tips": ["<tip 1>", "<tip 2>", "..."],
  "drills": ["<concrete dry-land or in-water drill>", "..."]
}

Provide AT LEAST 3 mistakes (or fewer if surfing is exceptional), 3 corrections, 3 tips, 2 drills.
Use precise surfing vocabulary."""


def _strip_json(text: str) -> str:
    """Remove possible markdown fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    # Slice from first { to last }
    if "{" in text and "}" in text:
        text = text[text.index("{") : text.rindex("}") + 1]
    return text


async def analyse_video_with_gemini(file_path: Path, mime_type: str) -> dict:
    chat = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis_{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_PROMPT,
        )
        .with_model("gemini", "gemini-2.5-pro")
    )
    video_file = FileContentWithMimeType(
        file_path=str(file_path),
        mime_type=mime_type,
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
        # Fallback minimal structured response
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
@api_router.post("/analyses", response_model=AnalysisOut)
async def create_analysis(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    analysis_id = f"ana_{uuid.uuid4().hex[:14]}"
    ext = (file.filename or "video.mp4").split(".")[-1].lower()
    if ext not in {"mp4", "mov", "m4v", "webm", "avi"}:
        ext = "mp4"
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    save_path = user_dir / f"{analysis_id}.{ext}"

    # Save uploaded file to disk
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    mime = file.content_type or "video/mp4"

    # Initial doc
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
    }
    await db.analyses.insert_one(dict(doc))

    # Run AI analysis
    try:
        result = await analyse_video_with_gemini(save_path, mime)
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
        "strengths": result.get("strengths") or [],
        "mistakes": result.get("mistakes") or [],
        "corrections": result.get("corrections") or [],
        "tips": result.get("tips") or [],
        "drills": result.get("drills") or [],
    }
    await db.analyses.update_one({"analysis_id": analysis_id}, {"$set": update})

    final = await db.analyses.find_one({"analysis_id": analysis_id}, {"_id": 0})
    return AnalysisOut(**{k: final[k] for k in AnalysisOut.model_fields if k in final})


@api_router.get("/analyses", response_model=List[AnalysisListItem])
async def list_analyses(user: User = Depends(get_current_user)):
    cursor = db.analyses.find(
        {"user_id": user.user_id},
        {"_id": 0, "analysis_id": 1, "title": 1, "score": 1, "overall_rating": 1, "summary": 1, "status": 1, "created_at": 1},
    ).sort("created_at", -1)
    items = await cursor.to_list(200)
    return [AnalysisListItem(**i) for i in items]


@api_router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(analysis_id: str, user: User = Depends(get_current_user)):
    doc = await db.analyses.find_one(
        {"analysis_id": analysis_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return AnalysisOut(**{k: doc[k] for k in AnalysisOut.model_fields if k in doc})


@api_router.get("/analyses/{analysis_id}/video")
async def get_analysis_video(
    analysis_id: str, token: Optional[str] = None
):
    """Stream the original video. Public-by-token (used by <Video> tag in app)."""
    # Token is passed as query param because <Video> can't set Authorization headers
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid token")

    doc = await db.analyses.find_one(
        {"analysis_id": analysis_id, "user_id": session_doc["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    path = doc.get("video_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Video file missing")
    return FileResponse(path, media_type=doc.get("mime_type") or "video/mp4")


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
