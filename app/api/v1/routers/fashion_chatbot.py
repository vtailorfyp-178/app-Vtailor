import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.mongodb import get_database

CHAT_MESSAGES_COLLECTION = "chat_messages"
CHAT_SESSIONS_COLLECTION = "chat_sessions"

FASHION_SYSTEM_PROMPT = """You are Vogue — a knowledgeable and stylish AI fashion assistant.
Your expertise covers:
- Outfit recommendations for any occasion (casual, formal, business, party, outdoor, etc.)
- Fabric guidance: properties, care instructions, seasonal suitability, sustainability
- Color theory: palettes, skin-tone matching, color coordination, trending colors
- Style advice: body-type flattering cuts, layering tips, capsule wardrobe building
- Trend updates: current and upcoming fashion trends by season
- Accessory pairing: shoes, bags, jewelry, belts, hats
- Budget-conscious styling: how to mix high and low pieces

Guidelines:
- Be warm, encouraging, and inclusive — fashion is for everyone.
- Keep responses concise and actionable (3-5 bullet points or a short paragraph).
- When recommending colors, mention specific names (e.g., "dusty rose", "cobalt blue").
- When recommending fabrics, note the season and care level.
- Always ask a clarifying question if the user's request is vague (e.g., "What's the occasion?").
- Never shame body types or budgets.
- If asked something unrelated to fashion, politely redirect: "I'm best at fashion questions — want style advice instead?"
"""


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class SessionItem(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str


class SessionGroupsResponse(BaseModel):
    groups: dict[str, list[SessionItem]]


class MessageItem(BaseModel):
    sender: str
    text: str
    time: str
    created_at: str


class HistoryResponse(BaseModel):
    messages: list[MessageItem]


def _clean_reply(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _time_str(dt: datetime) -> str:
    return dt.strftime("%I:%M %p")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
router = APIRouter(prefix="/chatbot", tags=["Fashion Chatbot"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    db = get_database()
    session_id = req.session_id or str(uuid.uuid4())

    history_cursor = (
        db[CHAT_MESSAGES_COLLECTION]
        .find(
            {"user_id": req.user_id, "session_id": session_id},
            {"_id": 0, "sender": 1, "text": 1},
        )
        .sort("created_at", -1)
        .limit(10)
    )
    history_docs = await history_cursor.to_list(length=10)
    history_docs.reverse()

    messages = [{"role": "system", "content": FASHION_SYSTEM_PROMPT}]
    for msg in history_docs:
        role = "assistant" if msg.get("sender") == "ai" else "user"
        messages.append({"role": role, "content": msg.get("text", "")})
    messages.append({"role": "user", "content": text})

    now = datetime.now(timezone.utc)
    is_first = len(history_docs) == 0
    title = text[:60] if is_first else None

    await db[CHAT_MESSAGES_COLLECTION].insert_one(
        {
            "user_id": req.user_id,
            "session_id": session_id,
            "sender": "user",
            "text": text,
            "time": _time_str(now),
            "created_at": now,
        }
    )

    if openai_client is None:
        reply = "Fashion assistant is not configured yet. Please set OPENAI_API_KEY in backend .env."
    else:
        try:
            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_tokens=600,
                temperature=0.75,
            )
            raw = response.choices[0].message.content or "Sorry, I could not generate a response."
            reply = _clean_reply(raw)
        except Exception as exc:
            reply = f"Fashion assistant error: {exc}"

    ai_now = datetime.now(timezone.utc)

    await db[CHAT_MESSAGES_COLLECTION].insert_one(
        {
            "user_id": req.user_id,
            "session_id": session_id,
            "sender": "ai",
            "text": reply,
            "time": _time_str(ai_now),
            "created_at": ai_now,
        }
    )

    if is_first and title:
        await db[CHAT_SESSIONS_COLLECTION].update_one(
            {"user_id": req.user_id, "session_id": session_id},
            {
                "$set": {
                    "user_id": req.user_id,
                    "session_id": session_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": ai_now,
                }
            },
            upsert=True,
        )
    else:
        await db[CHAT_SESSIONS_COLLECTION].update_one(
            {"user_id": req.user_id, "session_id": session_id},
            {"$set": {"updated_at": ai_now}},
        )

    return ChatResponse(reply=reply, session_id=session_id)


@router.get("/sessions/{user_id}", response_model=SessionGroupsResponse)
async def get_sessions(user_id: str) -> SessionGroupsResponse:
    db = get_database()
    cursor = (
        db[CHAT_SESSIONS_COLLECTION]
        .find(
            {"user_id": user_id},
            {"_id": 0, "session_id": 1, "title": 1, "created_at": 1, "updated_at": 1},
        )
        .sort("updated_at", -1)
        .limit(100)
    )

    docs = await cursor.to_list(length=100)
    grouped: dict[str, list[SessionItem]] = {}
    today = datetime.now(timezone.utc).date()

    for doc in docs:
        created = doc.get("created_at") or datetime.now(timezone.utc)
        d = created.date()
        if d == today:
            label = "Today"
        elif (today - d).days == 1:
            label = "Yesterday"
        elif (today - d).days < 7:
            label = "This Week"
        elif (today - d).days < 30:
            label = "This Month"
        else:
            label = created.strftime("%B %Y")

        if label not in grouped:
            grouped[label] = []

        grouped[label].append(
            SessionItem(
                session_id=doc["session_id"],
                title=doc.get("title", "Untitled Chat"),
                created_at=_iso(created),
                updated_at=_iso(doc.get("updated_at") or created),
            )
        )

    return SessionGroupsResponse(groups=grouped)


@router.get("/history/{user_id}/{session_id}", response_model=HistoryResponse)
async def get_session_history(user_id: str, session_id: str, limit: int = 100) -> HistoryResponse:
    db = get_database()
    cursor = (
        db[CHAT_MESSAGES_COLLECTION]
        .find(
            {"user_id": user_id, "session_id": session_id},
            {"_id": 0, "sender": 1, "text": 1, "time": 1, "created_at": 1},
        )
        .sort("created_at", 1)
        .limit(limit)
    )

    docs = await cursor.to_list(length=limit)
    messages: list[MessageItem] = []
    for doc in docs:
        created_at = doc.get("created_at") or datetime.now(timezone.utc)
        messages.append(
            MessageItem(
                sender=doc.get("sender", "ai"),
                text=doc.get("text", ""),
                time=doc.get("time", ""),
                created_at=_iso(created_at),
            )
        )

    return HistoryResponse(messages=messages)


@router.delete("/session/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str) -> dict[str, bool]:
    db = get_database()
    await db[CHAT_MESSAGES_COLLECTION].delete_many({"user_id": user_id, "session_id": session_id})
    await db[CHAT_SESSIONS_COLLECTION].delete_one({"user_id": user_id, "session_id": session_id})
    return {"deleted": True}


@router.delete("/history/{user_id}")
async def clear_chat_history(user_id: str) -> dict[str, int]:
    db = get_database()
    result = await db[CHAT_MESSAGES_COLLECTION].delete_many({"user_id": user_id})
    await db[CHAT_SESSIONS_COLLECTION].delete_many({"user_id": user_id})
    return {"deleted": result.deleted_count}
