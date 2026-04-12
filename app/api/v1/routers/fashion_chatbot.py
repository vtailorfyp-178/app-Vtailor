import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover - optional dependency at runtime
    AsyncOpenAI = None

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
- Garment design and construction: neckline/sleeve/hem ideas, pattern guidance, cutting plans, seam allowances, and stitching tips
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
openai_client: Any = None
if settings.OPENAI_API_KEY and AsyncOpenAI is not None:
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
openai_disabled = False
router = APIRouter(prefix="/chatbot", tags=["Fashion Chatbot"])


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _looks_unrelated(text: str) -> bool:
    keywords = (
        "fashion", "style", "dress", "outfit", "wear", "fabric", "color",
        "measure", "measurement", "tailor", "shirt", "pant", "trouser",
        "kurta", "kurti", "suit", "jacket", "blouse", "skirt", "shoe",
        "accessor", "trend", "summer", "winter", "formal", "casual", "party",
        "stitch", "seam", "cut", "cutting", "pattern", "draft", "dart",
        "neckline", "sleeve", "hem", "yoke", "armhole", "collar", "pleat",
        "grainline", "bias", "interfacing", "fusible", "notch", "placket",
        "zip", "zipper", "overlock", "serger", "bobbin", "presser", "needle",
        "thread", "tension", "spi", "seam allowance", "topstitch", "lining",
        "facing", "gusset", "princess seam", "muslin", "toile", "pattern making",
        "fabric consumption", "marker", "cut plan", "stitch length", "feed dog",
    )
    normalized = _normalize(text)
    return not any(keyword in normalized for keyword in keywords)


def _fallback_reply(text: str, history: list[dict[str, Any]] | None = None) -> str:
    normalized = _normalize(text)

    if _looks_unrelated(text):
        return (
            "I'm best at fashion questions. Want style advice instead? "
            "Tell me the occasion, your budget, or the look you want, and I’ll suggest an outfit."
        )

    if any(word in normalized for word in ["interview", "office", "job", "formal", "business"]):
        return (
            "For a job interview or office look, keep it clean and sharp:\n"
            "• Choose navy, charcoal, black, or crisp white\n"
            "• Wear a well-fitted shirt or blazer with minimal accessories\n"
            "• Use polished shoes and a structured bag or briefcase\n"
            "If you want, I can build a full outfit for men or women."
        )

    if any(word in normalized for word in ["summer", "hot", "heat", "humid"]):
        return (
            "For summer, go for breathable fabrics and light colors:\n"
            "• Cotton, linen, and cotton blends work best\n"
            "• Try dusty rose, sky blue, beige, or mint green\n"
            "• Keep the fit relaxed and avoid heavy layering\n"
            "If you want, I can suggest summer outfits for casual or formal wear."
        )

    if any(word in normalized for word in ["winter", "cold"]):
        return (
            "For winter, choose warmer layers and textured fabrics:\n"
            "• Wool, knitwear, denim, and heavier cotton are strong choices\n"
            "• Pick deep shades like burgundy, forest green, camel, or navy\n"
            "• Layer a shirt, sweater, and coat for comfort and shape\n"
            "I can also suggest a winter outfit by occasion."
        )

    if any(word in normalized for word in ["color", "colours", "colors", "skin tone", "warm tone", "cool tone"]):
        return (
            "For color matching, a few safe choices are:\n"
            "• Warm skin tones: olive, mustard, rust, cream, dusty rose\n"
            "• Cool skin tones: cobalt blue, lavender, charcoal, icy pink\n"
            "• Neutral tones: navy, white, beige, teal\n"
            "If you tell me your skin tone and the occasion, I can narrow it down."
        )

    if any(word in normalized for word in ["capsule", "wardrobe"]):
        return (
            "A capsule wardrobe should stay simple and versatile:\n"
            "• Pick neutral basics like white, black, navy, beige, and grey\n"
            "• Add 2-3 accent colors such as dusty rose, olive, or cobalt blue\n"
            "• Choose pieces that mix and match easily across casual and formal looks\n"
            "I can build a capsule wardrobe for your budget if you want."
        )

    if any(word in normalized for word in ["trend", "trending", "fashion now", "latest"]):
        return (
            "Current fashion trends are leaning toward clean tailoring and relaxed layering:\n"
            "• Oversized blazers, wide-leg trousers, and soft structured suits\n"
            "• Earth tones, cobalt blue, burgundy, and muted pastels\n"
            "• Simple accessories with one bold statement piece\n"
            "I can also suggest trends for casual, formal, or traditional wear."
        )

    if any(word in normalized for word in ["measure", "measurement", "size"]):
        return (
            "For measurements, use a soft measuring tape and keep it snug but not tight:\n"
            "• Chest/bust: around the fullest part\n"
            "• Waist: around your natural waistline\n"
            "• Hips: around the widest part\n"
            "If you want, I can guide you step by step for a specific outfit."
        )

    if any(word in normalized for word in ["matching", "match", "pairing", "pair", "coordinate"]):
        return (
            "For matching clothes well, keep 3 things in mind:\n"
            "• Match colors first: neutral, warm, or cool tones\n"
            "• Match shapes: loose top with fitted bottom, or balanced proportions\n"
            "• Match accessories lightly: one bag, one shoe tone, and limited jewelry\n"
            "If you want, I can match a specific dress with shoes, bag, and dupatta."
        )

    if any(word in normalized for word in ["accessory", "accessories", "jewelry", "earring", "earrings", "bag", "bags", "shoe", "shoes", "belt", "scarf", "dupatta"]):
        return (
            "For accessories with a dress, keep the outfit balance simple:\n"
            "• Simple dress: add statement earrings or a bold bag\n"
            "• Heavy dress: choose minimal jewelry and plain shoes\n"
            "• Formal look: match the shoe and bag color, and keep metal tones consistent\n"
            "Tell me the dress color and event, and I’ll suggest exact accessories."
        )

    if any(word in normalized for word in ["dress names", "dresses names", "types of dresses", "dress type", "dress types", "dress designs", "designs of dresses", "list of dresses", "dress list", "dress ideas"]):
        return (
            "Common dress names and styles you can ask for are:\n"
            "• A-line dress: fitted at the top and flares gently from the waist\n"
            "• Fit-and-flare: fitted bodice with a fuller skirt\n"
            "• Straight dress: clean, simple, and body-skimming\n"
            "• Maxi dress: long, flowy, and elegant for casual or formal wear\n"
            "• Shirt dress: shirt-inspired, smart, and versatile\n"
            "• Anarkali: classic flared traditional style\n"
            "If you want, I can suggest dress names for casual, party, wedding, or office wear."
        )

    if any(word in normalized for word in ["first date", "date", "party", "wedding", "event"]):
        return (
            "For an event or date, aim for polished but comfortable:\n"
            "• Pick one standout piece and keep the rest simple\n"
            "• Great colors: emerald green, wine, navy, blush, or charcoal\n"
            "• Add matching shoes, a clean bag, and one or two accessories\n"
            "Tell me the occasion and I’ll tailor the outfit exactly."
        )

    if any(word in normalized for word in ["neckline", "necklines", "necklin", "neck line", "neck line design", "specific neckline"]):
        return (
            "Here are common neckline names and where they work best:\n"
            "• Round neck: simple and safe for everyday wear, kurtis, and casual dresses\n"
            "• V-neck: lengthens the neck and suits formal dresses, blouses, and fitted tops\n"
            "• Boat neck: elegant and good for shoulders; works well on straight dresses and blouses\n"
            "• Square neck: stylish and balanced for western tops, frocks, and blouses\n"
            "• Sweetheart neck: soft and feminine, great for party wear and special occasions\n"
            "• Halter neck: best for party wear and modern dresses; shows shoulders nicely\n"
            "• Collared neck: smart and structured, ideal for shirt dresses and office wear\n"
            "If you want, I can recommend the best neckline for your face shape, body type, or dress type."
        )

    if any(word in normalized for word in ["design", "silhouette", "neckline", "sleeve", "hem", "yoke", "panel", "cut"]):
        return (
            "For garment design, start with silhouette and details first:\n"
            "• Pick silhouette: straight, A-line, fit-and-flare, or relaxed\n"
            "• Choose features: neckline (boat/V/round), sleeve (cap/3-4th/full), and hem style\n"
            "• Keep one focal element like pleats, piping, or contrast panels\n"
            "Tell me the garment type and occasion, and I’ll propose a complete design."
        )

    if any(word in normalized for word in [
        "spi", "stitch length", "thread tension", "needle", "bobbin", "presser foot",
        "overlock", "serger", "topstitch", "feed dog",
    ]):
        return (
            "For lawn/cotton side seams, start with these settings:\n"
            "• SPI: around 10-12 (or stitch length ~2.2 to 2.6 mm)\n"
            "• Needle: 11/75 or 14/90 depending on fabric thickness\n"
            "• Side seam allowance: usually 1 cm to 1.5 cm\n"
            "Test on scrap first, then adjust tension if stitches pucker or loop."
        )

    if any(word in normalized for word in ["cutting", "pattern", "draft", "marker"]):
        return (
            "For cutting and pattern work, use this sequence:\n"
            "• Draft or trace base pattern using body measurements\n"
            "• Add seam allowances (usually 1 cm seams, 2-4 cm hems)\n"
            "• Place pattern on grainline and cut in mirrored pairs where needed\n"
            "I can give exact cutting steps for kurti, shirt, frock, trouser, or blouse."
        )

    if any(word in normalized for word in ["stitch", "stitching", "sew", "sewing", "dart", "armhole", "zip", "lining"]):
        return (
            "For clean stitching, follow this order:\n"
            "• Join darts/panels first, then shoulders, then side seams\n"
            "• Attach sleeves after armhole prep and notch matching\n"
            "• Finish neckline/hem last and press each seam while sewing\n"
            "Share the garment type and I’ll give a detailed stitching sequence."
        )

    if any(word in normalized for word in [
        "interfacing", "fusible", "grainline", "bias", "seam allowance",
        "fabric consumption", "placket", "facing", "gusset", "princess seam",
        "toile", "muslin",
    ]):
        return (
            "That is a valid garment-construction question. Quick practical guide:\n"
            "• Use suitable needle/thread for fabric weight (light, medium, heavy)\n"
            "• Keep seam allowance consistent and mark notches before stitching\n"
            "• Test stitch length/tension on scrap fabric before final seams\n"
            "Tell me your exact fabric and garment, and I’ll give precise settings and steps."
        )

    if any(word in normalized for word in ["fabric", "cloth", "material", "textile"]):
        return (
            "For fabric guidance:\n"
            "• Cotton is breathable and easy to care for, best for daily wear and summer\n"
            "• Linen is airy and stylish, but wrinkles easily\n"
            "• Wool and knits are better for winter and need gentler care\n"
            "Tell me the season or outfit type and I’ll suggest the best fabric."
        )

    if any(word in normalized for word in ["style", "outfit", "wear", "dress", "clothes"]):
        return (
            "To build a strong outfit, focus on fit, color, and occasion:\n"
            "• Choose one main color and one accent color\n"
            "• Balance fitted and relaxed pieces so the silhouette feels clean\n"
            "• Finish with shoes and accessories that match the outfit mood\n"
            "Tell me the occasion, budget, and dress style, and I’ll make a specific suggestion."
        )

    return (
        "Tell me the occasion, season, and whether you want casual, formal, or traditional style. "
        "I can suggest colors, fabrics, and a complete outfit."
    )


async def _generate_reply(text: str, messages: list[dict[str, str]]) -> str:
    global openai_disabled

    if openai_client is None or openai_disabled:
        return _fallback_reply(text)

    try:
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.75,
        )
        raw = response.choices[0].message.content or ""
        reply = _clean_reply(raw)
        return reply or _fallback_reply(text)
    except Exception as exc:
        error_text = str(exc).lower()
        if any(code in error_text for code in ["insufficient_quota", "429", "rate limit", "quota"]):
            openai_disabled = True
        return _fallback_reply(text)


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

    reply = await _generate_reply(text, messages)

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
