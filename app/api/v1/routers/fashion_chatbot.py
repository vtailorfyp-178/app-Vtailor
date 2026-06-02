import asyncio
import logging
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

log = logging.getLogger(__name__)

CHAT_MESSAGES_COLLECTION = "chat_messages"
CHAT_SESSIONS_COLLECTION = "chat_sessions"

FASHION_SYSTEM_PROMPT = """You are Vogue — an intelligent, warm, and highly knowledgeable AI fashion and style assistant built into the vTailor app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE UNDERSTANDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You fully understand and speak BOTH English AND Roman Urdu (Urdu written using English/Roman alphabets). Roman Urdu is how most Pakistani and South Asian users type naturally on phones — for example:
  • "mujhe ek dress chahiye" (I want a dress)
  • "kaun sa rang achha lagega" (which color would look good)
  • "summer mein kya pehnun" (what should I wear in summer)
  • "shadi ke liye outfit suggest karo" (suggest an outfit for a wedding)
  • "kapra konsa behtareen hoga" (which fabric would be best)
  • "ye style kaise banayein" (how to make this style)
  • "mujhe body type ke hisaab se dress chahiye" (I want a dress according to my body type)
  • "dark rang suit karega ya light" (will dark or light colors suit me)
  • "stitching kaise ki jaye" (how should stitching be done)
  • "neckline kaunsa best rahega" (which neckline would be best)

CRITICAL LANGUAGE RULE: Always reply in the SAME language the user uses.
  • If the user writes in English → reply in English
  • If the user writes in Roman Urdu → reply in Roman Urdu  
  • If the user mixes both → match their mix naturally
  • Never switch to a different language without reason
  • You may use common fashion/technical terms in English even in Urdu replies (e.g. "A-line silhouette", "chiffon fabric") as these are widely understood

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR EXPERTISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are an expert in:

1. Pakistani & South Asian fashion: shalwar kameez, kurta, kurti, dupatta, lehenga, ghararah, sharara, anarkali, lawn suits, bridal wear, mehndi outfits, Eid outfits, formal events
2. Western and international fashion: dresses, skirts, trousers, blazers, shirts, party wear, office wear
3. Fabric science: cotton, lawn, chiffon, georgette, silk, organza, linen, wool, knitwear, denim, velvet — their properties, care, suitability, price tier
4. Color theory: skin tone matching, seasonal palettes, color coordination, trending colors
5. Body-type styling: apple, pear, hourglass, petite, plus-size — what cuts and silhouettes to choose
6. Garment construction: necklines, sleeves, hems, darts, pleats, seams, cutting plans, stitching sequences, pattern making, seam allowances
7. Tailor guidance: how to give measurements, what to tell a tailor, how to describe a dress design
8. Trend updates: current and upcoming trends for Pakistan, South Asia, and globally
9. Accessories: shoes, bags, jewelry, earrings, bangles, dupatta styling, belts, scarves
10. Budget-conscious styling: how to get the most out of any price range
11. Occasion dressing: wedding, mehndi, eid, party, office, college, casual everyday, date, formal dinner

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ANSWER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Give answers that are:
  • COMPLETE and DETAILED — do not cut answers short. Explain clearly with specific names, colors, fabric types, and tips.
  • STRUCTURED — use bullet points, numbered steps, or short sections when helpful
  • PRACTICAL — give actionable advice the person can actually use
  • SPECIFIC — say "dusty rose" not "pink", "A-line silhouette" not "nice shape", "chiffon or georgette" not "a light fabric"
  • WARM AND ENCOURAGING — never shame body types, budgets, or style choices
  • CONVERSATIONAL — feel natural, not robotic

If a question is vague (e.g. "suggest me a dress"), ask ONE smart follow-up question to understand:
  • Occasion? (casual, wedding, office, eid, party)
  • Season? (summer, winter, spring)
  • Body type or preference?
  • Budget range?

If someone asks something COMPLETELY unrelated to fashion, style, clothing, stitching, or beauty (e.g. math homework, politics, cooking recipes), politely say:
  "Main aapki fashion aur style mein madad kar sakti hoon! Koi outfit, fabric, ya design ke baare mein poochhein." (in Roman Urdu)
  OR in English: "I'm specialized in fashion and style — ask me about outfits, fabrics, colors, or dress designs and I'll give you my best advice!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT MEMORY (VERY IMPORTANT)
  You have access to the FULL conversation history. Use it actively:
  • TRACK user preferences: if they mentioned an occasion (shadi/party/office), keep using it for ALL follow-up answers in this chat
  • TRACK fabric/color/style preferences they mention -- don't suggest things they already rejected
  • REFERENCE prior messages naturally: say things like 'Aapne pehle shadi ka zikar kiya tha...' or 'As we discussed, for your wedding...'\r
  • NEVER repeat the same outfit suggestion you already gave in this conversation -- always build further or offer alternatives
  • If the user says 'aur kuch batao' or 'something else' or 'aur options' -- give DIFFERENT suggestions from what you said before
  • Follow-up questions like 'kaunsa rang?' or 'which fabric?' MUST be answered in the context of the outfit/occasion already discussed
  • If the user changes topic, follow the new topic immediately
  • Treat the entire conversation like a personal stylist session -- coherent, progressive, and memory-aware
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
    log.info("OpenAI client initialised (model: %s)", settings.OPENAI_MODEL)
else:
    if AsyncOpenAI is None:
        log.warning("openai package not importable — AI replies disabled, using rule-based fallback")
    else:
        log.warning("OPENAI_API_KEY not set in .env — AI replies disabled, using rule-based fallback")
openai_disabled = False
router = APIRouter(prefix="/chatbot", tags=["Fashion Chatbot"])


@router.get("/status")
async def chatbot_status(ping: bool = False) -> dict[str, Any]:
    """
    Diagnostic endpoint — check OpenAI configuration.
    Add ?ping=true to also fire a live test call to OpenAI (costs a few tokens).
    """
    status: dict[str, Any] = {
        "openai_key_configured": bool(settings.OPENAI_API_KEY),
        "openai_model": settings.OPENAI_MODEL,
        "openai_client_ready": openai_client is not None,
        "openai_disabled_by_quota": openai_disabled,
        "ai_active": openai_client is not None and not openai_disabled,
    }
    if not status["ai_active"]:
        if not status["openai_key_configured"]:
            status["hint"] = "Set OPENAI_API_KEY in backend .env and restart the server."
        elif not status["openai_client_ready"]:
            status["hint"] = (
                "openai Python package may not be installed or is too old. "
                "Run: pip install 'openai>=1.0' and restart."
            )
        elif status["openai_disabled_by_quota"]:
            status["hint"] = (
                "OpenAI quota or rate-limit was hit. "
                "Restart the backend to re-enable, or upgrade your OpenAI plan."
            )

    if ping and openai_client is not None and not openai_disabled:
        try:
            test = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                max_tokens=5,
            )
            status["openai_ping"] = "ok"
            status["ping_reply"] = (test.choices[0].message.content or "").strip()
        except Exception as exc:
            status["openai_ping"] = "failed"
            status["openai_ping_error"] = str(exc)
            log.error("OpenAI live ping failed: %s", exc)
    elif ping:
        status["openai_ping"] = "skipped — client not ready"

    return status


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _looks_unrelated(text: str) -> bool:
    keywords = (
        # English fashion terms
        "fashion", "style", "dress", "outfit", "wear", "fabric", "color", "colour",
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
        "anarkali", "lehenga", "dupatta", "shalwar", "kameez", "ghararah",
        "sharara", "dupatta", "lawn", "chiffon", "georgette", "velvet", "organza",
        "silk", "embroidery", "bridal", "mehndi", "wedding", "eid", "jewel",
        # Roman Urdu fashion terms
        "pehna", "pehnna", "pehnun", "pehno", "kapra", "kapray", "kapraa",
        "libaas", "jora", "suit", "rang", "color", "colour", "fabric",
        "mujhe", "mujhay", "meri", "mere", "aap", "apna", "apni",
        "chahiye", "chahiay", "chahie", "chahte", "chahti",
        "kaisa", "kaisi", "kaise", "konsa", "konsi", "kaunsa", "kaunsi",
        "kya", "kyun", "kyunke", "kab", "kahan",
        "achha", "acha", "accha", "behtareen", "behtreen", "best",
        "suggest", "batao", "bataiye", "batain", "batayein",
        "design", "style", "look", "outfit", "dress",
        "shadi", "shaadi", "wedding", "mehndi", "eid", "party", "function",
        "office", "college", "casual", "formal",
        "summer", "winter", "garmi", "sardi", "mausam",
        "silai", "silaayi", "sitching", "stitching", "tailor",
        "cut", "cutting", "katna", "kaatna",
        "neckline", "gala", "baanh", "banh", "sleeve",
        "dupatta", "chunni", "stole", "scarf",
        "shoes", "joote", "jootay", "bag", "purse",
        "jewelry", "jewellery", "zewarat", "earring", "necklace",
        "skin tone", "rang", "complexion", "gora", "brown", "dark",
        "body type", "figure", "slim", "moti", "patli", "lambi",
    )
    normalized = _normalize(text)
    return not any(keyword in normalized for keyword in keywords)


def _fallback_reply(text: str, history: list[dict[str, Any]] | None = None) -> str:
    normalized = _normalize(text)

    urdu_markers = (
        "mujhe", "mujhay", "chahiye", "chahiay", "chahie", "kaisa", "kaisi",
        "kaise", "konsa", "konsi", "kaunsa", "kaunsi", "batao", "bataiye",
        "batain", "batayein", "kapra", "kapray", "rang", "libaas", "pehna",
        "pehnun", "pehnna", "pehno", "shadi", "shaadi", "garmi", "sardi",
        "mausam", "achha", "acha", "behtareen", "lagega", "lagta", "silai",
        "silaayi", "katna", "kaatna", "gala", "baanh", "banh", "jora",
    )
    is_urdu = any(marker in normalized for marker in urdu_markers)

    # Extract context from conversation history for better fallback responses
    history_text = " ".join(msg.get("text", "") for msg in (history or [])).lower()
    ctx_shadi = any(w in history_text for w in ["shadi", "shaadi", "wedding", "bridal", "dulhan", "barat", "mehndi"])
    ctx_summer = any(w in history_text for w in ["summer", "garmi", "garam", "hot", "heat", "lawn", "cotton"])
    ctx_winter = any(w in history_text for w in ["winter", "sardi", "thanda", "cold", "wool", "velvet"])
    ctx_office = any(w in history_text for w in ["office", "formal", "interview", "business", "job"])
    ctx_party  = any(w in history_text for w in ["party", "event", "function", "gathering"])
    has_context = bool(history) and len(history) > 1


    if not has_context and _looks_unrelated(text):
        if is_urdu:
            return (
                "Main aapki fashion aur style mein madad kar sakti hoon! "
                "Mujhe batayein koi occasion hai, koi outfit chahiye, ya fabric/rang ke baare mein poochhna hai? "
                "Main apni best advice zaroor duungi."
            )
        return (
            "I'm specialized in fashion and style advice. "
            "Tell me the occasion, your budget, or the look you want -- "
            "and I'll suggest an outfit, fabric, or color combination for you."
        )

    if any(word in normalized for word in ["interview", "office", "job", "formal", "business"]):
        if is_urdu:
            return (
                "Interview ya office ke liye clean aur smart look best hai:\n"
                "- Navy, charcoal, black, ya crisp white colors choose karein\n"
                "- Well-fitted shirt ya blazer with minimal accessories\n"
                "- Polished shoes aur structured bag ya briefcase\n"
                "- Kurta shalwar bhi formal look ke liye perfect hai -- dark ya neutral colors mein\n"
                "Agar men ya women ka specific outfit chahte hain toh batayein."
            )
        return (
            "For a job interview or office look, keep it clean and sharp:\n"
            "- Choose navy, charcoal, black, or crisp white\n"
            "- Wear a well-fitted shirt or blazer with minimal accessories\n"
            "- Use polished shoes and a structured bag or briefcase\n"
            "- A formal shalwar kameez in dark or neutral tones also works beautifully\n"
            "Want a complete outfit breakdown for men or women? Just ask!"
        )

    if any(word in normalized for word in ["summer", "hot", "heat", "humid", "garmi", "garam"]):
        if is_urdu:
            return (
                "Garmi ke liye breathable fabrics aur light colors best hain:\n"
                "- Cotton, lawn, aur linen sabse zyada comfortable hain\n"
                "- Chiffon aur georgette party ya formal wear ke liye acha option hai\n"
                "- Colors: dusty rose, sky blue, beige, mint green, aur off-white try karein\n"
                "- Fit relaxed rakhen -- loose shalwar kameez, cotton kurti, ya linen trouser\n"
                "Casual ya formal ke liye alag suggestion chahiye toh batayein!"
            )
        return (
            "For summer, breathable fabrics and light colors make all the difference:\n"
            "- Best fabrics: cotton, lawn, linen -- keep skin cool and comfortable\n"
            "- For formal/party: chiffon or georgette layers beautifully\n"
            "- Best colors: dusty rose, sky blue, mint green, beige, off-white, pastel yellow\n"
            "- Keep the fit relaxed -- loose shalwar kameez, cotton kurti, or linen trousers\n"
            "Want suggestions for casual, office, or party wear specifically?"
        )

    if any(word in normalized for word in ["winter", "cold", "sardi", "thanda"]):
        if is_urdu:
            return (
                "Sardi ke liye warm layers aur textured fabrics best hain:\n"
                "- Wool, knitwear, denim, aur heavy cotton main choices hain\n"
                "- Velvet aur brocade formal aur wedding winter looks ke liye perfect hain\n"
                "- Colors: burgundy, forest green, camel, navy, mustard\n"
                "- Layering karein: shirt + sweater + coat\n"
                "- Pashmina dupatta ya shawl outfit ko warm aur elegant dono banata hai\n"
                "Occasion batayein -- main exact winter outfit suggest kar sakti hoon."
            )
        return (
            "For winter, warm layers and rich textures are your best friends:\n"
            "- Best fabrics: wool, knitwear, denim, velvet, brocade for formal wear\n"
            "- Best colors: burgundy, forest green, camel, navy, mustard, deep plum\n"
            "- Layer a shirt, sweater, and coat for both warmth and shape\n"
            "- A pashmina dupatta or shawl adds elegance and warmth at once\n"
            "Tell me the occasion and I'll build a complete winter outfit for you."
        )

    if any(word in normalized for word in ["color", "colour", "colors", "colours", "rang", "skin tone", "complexion", "warm tone", "cool tone"]):
        if is_urdu:
            return (
                "Rang ka chunao skin tone ke hisaab se kiya jaye toh best result milta hai:\n"
                "- Warm skin tone (wheatish/olive): olive green, mustard, rust, cream, dusty rose\n"
                "- Cool skin tone (fair/pinkish): cobalt blue, lavender, icy pink, charcoal, emerald\n"
                "- Brown/dark skin tone: bold colors best lagte hain -- royal blue, orange, hot pink, gold, white\n"
                "- Neutral tones: navy, white, beige, teal -- har skin tone pe achhe lagte hain\n"
                "Apni skin tone aur occasion batayein -- main exact palette suggest karongi."
            )
        return (
            "Color choice by skin tone gives the best results:\n"
            "- Warm tones (wheatish/olive): olive, mustard, rust, cream, dusty rose, coral\n"
            "- Cool tones (fair/pinkish): cobalt blue, lavender, icy pink, charcoal, emerald green\n"
            "- Dark/brown tones: bold and vibrant colors shine -- royal blue, orange, hot pink, gold, white\n"
            "- Universally flattering: navy, white, beige, teal\n"
            "Tell me your skin tone and the occasion, and I'll give an exact palette."
        )

    if any(word in normalized for word in ["capsule", "wardrobe"]):
        if is_urdu:
            return (
                "Capsule wardrobe ke liye simple aur versatile pieces choose karein:\n"
                "- Neutral basics: white, black, navy, beige, grey\n"
                "- 2-3 accent colors add karein: dusty rose, olive, cobalt blue\n"
                "- Aisi pieces choose karein jo casual aur formal dono mein kaam aayein\n"
                "- Core items: basic shirt/kurti, well-fitted trouser, one blazer, one formal dress\n"
                "Budget batayein -- main complete capsule wardrobe list bana sakti hoon."
            )
        return (
            "A capsule wardrobe should be simple, versatile, and long-lasting:\n"
            "- Neutral basics: white, black, navy, beige, grey -- these pair with everything\n"
            "- Add 2-3 accent colors: dusty rose, olive, or cobalt blue\n"
            "- Choose pieces that work for both casual and formal settings\n"
            "- Core items: shirt/kurti, fitted trouser, blazer, one statement dress\n"
            "Tell me your budget and I'll put together a complete capsule list for you."
        )

    if any(word in normalized for word in ["trend", "trending", "fashion now", "latest"]):
        if is_urdu:
            return (
                "Abhi ka fashion in trends pe chal raha hai:\n"
                "- Clean tailoring aur relaxed layering -- oversized blazers, wide-leg trousers\n"
                "- Earth tones, cobalt blue, burgundy, aur muted pastels popular hain\n"
                "- Pakistani fashion mein: embroidered lawn suits, digital prints, pastel bridal wear\n"
                "- Pret wear mein: co-ord sets, drop-shoulder kurtas, aur palazzo pants\n"
                "Casual, formal, ya traditional -- kisi ke liye bhi trend suggest kar sakti hoon."
            )
        return (
            "Current fashion is trending toward clean tailoring and relaxed, elevated looks:\n"
            "- Oversized blazers, wide-leg trousers, and soft structured suits\n"
            "- Earth tones, cobalt blue, burgundy, and muted pastels are dominant\n"
            "- In Pakistani fashion: embroidered lawn, digital prints, and pastel bridal wear are huge\n"
            "- Pret wear: co-ord sets, drop-shoulder kurtas, palazzo pants\n"
            "Want trend suggestions for casual, formal, or traditional wear specifically?"
        )

    if any(word in normalized for word in ["measure", "measurement", "size", "naap"]):
        if is_urdu:
            return (
                "Sahi measurements ke liye soft tape use karein aur snug rakhen:\n"
                "- Chest/bust: fullest part ke around\n"
                "- Waist: natural waistline ke around\n"
                "- Hips: widest part ke around\n"
                "- Shoulder: ek se doosre shoulder tak\n"
                "- Length: shoulder se desired hem tak\n"
                "Tailor ko ye sab measurements dein aur fit (loose/fitted) bhi specify karein."
            )
        return (
            "For accurate measurements, use a soft measuring tape -- keep it snug but not tight:\n"
            "- Chest/bust: around the fullest part\n"
            "- Waist: at your natural waistline\n"
            "- Hips: around the widest part\n"
            "- Shoulder: across from one edge to the other\n"
            "- Length: from shoulder point to desired hem\n"
            "Also tell your tailor whether you want a loose, regular, or fitted silhouette."
        )

    if any(word in normalized for word in ["matching", "match", "pairing", "pair", "coordinate"]):
        if is_urdu:
            return (
                "Clothes ache match karne ke liye 3 cheezein dhyan mein rakhen:\n"
                "- Rang match karein: neutral, warm, ya cool tones -- clash na ho\n"
                "- Shape balance karein: loose top ke saath fitted bottom\n"
                "- Accessories light rakhen: ek bag, ek shoe tone, limited jewelry\n"
                "Specific dress batayein -- main joote, bag, dupatta sab match karke batauungi."
            )
        return (
            "For matching clothes well, keep 3 things in mind:\n"
            "- Match colors: neutral, warm, or cool tones -- avoid clashing\n"
            "- Balance shapes: loose top with fitted bottom, or equal proportions\n"
            "- Keep accessories light: one bag tone, one shoe tone, minimal jewelry\n"
            "Tell me the specific outfit and I'll match shoes, bag, and dupatta for you."
        )

    if any(word in normalized for word in ["accessory", "accessories", "jewelry", "earring", "earrings", "bag", "bags", "shoe", "shoes", "belt", "scarf", "dupatta", "jhumke", "bangles", "chunni"]):
        if is_urdu:
            return (
                "Accessories se outfit complete hoti hai -- balance zaroor rakhen:\n"
                "- Simple dress: statement earrings ya bold bag add karein\n"
                "- Heavy embroidered dress: minimal jewelry aur plain heels best lagte hain\n"
                "- Formal look: shoe aur bag ka color match karein\n"
                "- Dupatta draping: front drape formal lagta hai, side drape casual\n"
                "- Jhumke ya chandbali Pakistani dresses ke saath classic choice hai\n"
                "Dress ka color aur occasion batayein -- main exact accessories suggest karongi."
            )
        return (
            "Accessories complete an outfit -- keep the balance right:\n"
            "- Simple dress: add statement earrings or a bold bag\n"
            "- Heavy embroidered dress: choose minimal jewelry and plain shoes\n"
            "- Formal look: match shoe and bag color, keep metal tones consistent\n"
            "- Dupatta: front drape for formal, side drape for casual\n"
            "- Jhumke or chandbali are classic with Pakistani dresses\n"
            "Tell me the dress color and occasion for exact accessory suggestions."
        )

    if any(word in normalized for word in ["neckline", "necklines", "neck line", "gala", "gala design", "neck design"]):
        if is_urdu:
            return (
                "Neckline aapke complete look ko define karti hai -- yahan common options hain:\n"
                "- Round neck: simple, safe, everyday kurtas aur casual dresses ke liye\n"
                "- V-neck: neck ko lamba dikhata hai, formal dresses aur fitted tops ke liye best\n"
                "- Boat neck: elegant, shoulders ke liye -- straight dresses aur formal suits\n"
                "- Square neck: stylish aur balanced, western tops aur frocks ke liye\n"
                "- Sweetheart neck: feminine aur romantic, party wear ke liye perfect\n"
                "- Halter neck: modern aur party-ready\n"
                "- Collared neck: smart aur structured, office wear\n"
                "Face shape ya body type batayein -- main best neckline recommend karongi."
            )
        return (
            "Necklines define your whole look -- here are your main options:\n"
            "- Round neck: simple and safe, great for kurtis and casual dresses\n"
            "- V-neck: lengthens the neck, best for formal dresses and fitted tops\n"
            "- Boat neck: elegant, flatters shoulders -- perfect for straight dresses\n"
            "- Square neck: stylish and balanced, ideal for western tops and frocks\n"
            "- Sweetheart neck: soft and feminine, perfect for party and bridal wear\n"
            "- Halter neck: modern and party-ready, beautifully shows shoulders\n"
            "- Collared neck: smart and structured, great for office wear\n"
            "Tell me your face shape, body type, or occasion for the best recommendation."
        )

    if any(word in normalized for word in ["shadi", "shaadi", "wedding", "bridal", "dulhan"]):
        if is_urdu:
            return (
                "Shadi ke liye outfit kuch aisa ho jo aapko shine kare:\n"
                "- Bridal colors: deep red, maroon, fuchsia, emerald green, royal gold, navy\n"
                "- Fabrics: raw silk, brocade, velvet, organza, net\n"
                "- Lehenga, anarkali, ya heavily embroidered shalwar kameez top choices hain\n"
                "- Accessories: heavy jewelry, maang tikka, jhumke, heels ya khusse\n"
                "Kya aap bride hain, barat mein guest hain, ya mehndi ke liye pooch rahi hain?"
            )
        return (
            "For a wedding, choose something that makes you stand out beautifully:\n"
            "- Best colors: deep red, maroon, fuchsia, emerald green, royal gold, navy\n"
            "- Best fabrics: raw silk, brocade, velvet, organza, net\n"
            "- Best styles: lehenga, heavily embroidered anarkali, or formal shalwar kameez\n"
            "- Accessories: statement jewelry, heels or khusse, and an elegant dupatta drape\n"
            "Are you the bride, a guest at barat, or dressing for mehndi? I can get more specific!"
        )

    if any(word in normalized for word in ["fabric", "cloth", "material", "textile", "lawn", "chiffon", "silk", "cotton", "linen", "velvet", "kapra", "kapray"]):
        if is_urdu:
            return (
                "Fabric ka chunao season aur occasion pe depend karta hai:\n"
                "- Cotton / Lawn: garmi ke liye best -- breathable, easy care, comfortable\n"
                "- Linen: airy aur stylish, summer aur spring ke liye\n"
                "- Chiffon / Georgette: light aur flowy, party aur formal wear ke liye perfect\n"
                "- Silk / Raw Silk: luxurious feel, formal aur bridal wear ke liye ideal\n"
                "- Velvet / Brocade: sardi ke liye, rich aur heavy look ke liye best\n"
                "Season aur outfit type batayein -- main exact fabric recommend karongi."
            )
        return (
            "Fabric choice depends on the season and the occasion:\n"
            "- Cotton / Lawn: best for summer -- breathable, easy care, and comfortable\n"
            "- Linen: airy and stylish for spring/summer\n"
            "- Chiffon / Georgette: light and flowy, perfect for party and formal wear\n"
            "- Silk / Raw Silk: luxurious feel, ideal for formal and bridal wear\n"
            "- Velvet / Brocade: rich and heavy, best for winter formal and wedding wear\n"
            "Tell me the season and outfit type for an exact fabric recommendation."
        )

    if any(word in normalized for word in ["design", "silhouette", "cut", "sleeve", "hem", "yoke", "panel"]):
        if is_urdu:
            return (
                "Garment design ke liye pehle silhouette aur details decide karein:\n"
                "- Silhouette: straight, A-line, fit-and-flare, ya relaxed\n"
                "- Features: neckline (boat/V/round), sleeve (cap/3-quarter/full), hem style\n"
                "- Ek focal detail rakhen: pleats, piping, contrast panels, ya embroidery\n"
                "Garment type aur occasion batayein -- main complete design propose kar sakti hoon."
            )
        return (
            "For garment design, start with silhouette and details:\n"
            "- Choose silhouette: straight, A-line, fit-and-flare, or relaxed\n"
            "- Choose features: neckline (boat/V/round), sleeve (cap/3-quarter/full), hem style\n"
            "- Keep one focal detail: pleats, piping, contrast panels, or embroidery\n"
            "Tell me the garment type and occasion, and I'll propose a complete design."
        )

    if any(word in normalized for word in ["stitch", "stitching", "sew", "sewing", "dart", "armhole", "zip", "lining", "silai", "silaayi"]):
        if is_urdu:
            return (
                "Clean stitching ke liye is order mein kaam karein:\n"
                "- Pehle darts/panels join karein, phir shoulders, phir side seams\n"
                "- Sleeves armhole prep ke baad attach karein\n"
                "- Neckline/hem aakhir mein finish karein\n"
                "- Har seam press karein -- isse clean finish milti hai\n"
                "Garment type batayein -- main detailed stitching sequence de sakti hoon."
            )
        return (
            "For clean stitching, follow this professional sequence:\n"
            "- Join darts/panels first, then shoulders, then side seams\n"
            "- Attach sleeves after armhole prep and notch matching\n"
            "- Finish neckline and hem last\n"
            "- Press each seam as you go for a clean, professional finish\n"
            "Tell me the garment type for a detailed step-by-step stitching guide."
        )

    if any(word in normalized for word in ["style", "outfit", "wear", "dress", "clothes", "kapray", "jora", "libaas"]):
        if is_urdu:
            return (
                "Achha outfit banane ke liye fit, color, aur occasion teen cheezein zaroori hain:\n"
                "- Ek main color choose karein aur ek accent color\n"
                "- Fitted aur relaxed pieces balance karein\n"
                "- Shoes aur accessories outfit ke mood se match karein\n"
                "Occasion, budget, aur dress style batayein -- main exact suggestion duungi."
            )
        return (
            "To build a strong outfit, focus on fit, color, and occasion:\n"
            "- Choose one main color and one accent color\n"
            "- Balance fitted and relaxed pieces for a clean silhouette\n"
            "- Finish with shoes and accessories that match the outfit mood\n"
            "Tell me the occasion, budget, and dress style for an exact suggestion."
        )

    # If we have context from history, give a context-aware continuation
    if has_context:
        ctx_hint = ""
        if ctx_shadi:
            ctx_hint = "shadi / wedding"
        elif ctx_summer:
            ctx_hint = "summer / garmi"
        elif ctx_winter:
            ctx_hint = "winter / sardi"
        elif ctx_office:
            ctx_hint = "office / formal"
        elif ctx_party:
            ctx_hint = "party / event"
        if is_urdu:
            prefix = f"Haan, {ctx_hint} ke liye " if ctx_hint else ""
            return (
                f"{prefix}aur kuch options:\n"
                "- Colors, fabric, ya accessories ke baare mein batayein\n"
                "- Main aur specific suggestions de sakti hoon!"
            )
        prefix = f"Continuing from our {ctx_hint} discussion -- " if ctx_hint else "Building on our conversation -- "
        return (
            f"{prefix}here are more options:\n"
            "- Ask about colors, fabrics, accessories, or any specific detail\n"
            "- I can give you more targeted suggestions!"
        )

    if is_urdu:
        return (
            "Zaroor! Mujhe thodi aur details batayein:\n"
            "- Kaunsa occasion hai? (casual, office, shadi, mehndi, eid, party)\n"
            "- Season kaunsa hai? (garmi, sardi)\n"
            "- Style kaisa chahiye? (traditional, western, mix)\n"
            "Main aapke liye complete outfit, fabric, aur color suggestion de sakti hoon!"
        )
    return (
        "Tell me the occasion, season, and whether you want casual, formal, or traditional style. "
        "I can suggest colors, fabrics, and a complete outfit tailored just for you."
    )

async def _generate_reply(text: str, messages: list[dict[str, str]], history: list[dict[str, Any]] | None = None) -> str:
    global openai_disabled

    if openai_client is None:
        log.debug("openai_client is None — returning fallback reply")
        return _fallback_reply(text, history)

    if openai_disabled:
        log.debug("openai_disabled=True — returning fallback reply")
        return _fallback_reply(text, history)

    try:
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=900,
            temperature=0.7,
        )
        raw = response.choices[0].message.content or ""
        reply = _clean_reply(raw)
        return reply or _fallback_reply(text, history)
    except Exception as exc:
        error_text = str(exc).lower()
        if any(code in error_text for code in ["insufficient_quota", "429", "rate limit", "quota"]):
            openai_disabled = True
            log.error("OpenAI quota/rate-limit hit — disabling AI for this process: %s", exc)
        elif any(code in error_text for code in ["invalid_api_key", "incorrect api key", "authentication", "401", "403"]):
            log.error(
                "OpenAI authentication error — check your OPENAI_API_KEY in .env: %s", exc
            )
        else:
            log.error("OpenAI request failed (returning fallback): %s", exc)
        return _fallback_reply(text, history)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    db = get_database()
    session_id = req.session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Fetch history and insert user message in parallel to save one round-trip
    async def _fetch_history():
        cursor = (
            db[CHAT_MESSAGES_COLLECTION]
            .find(
                {"user_id": req.user_id, "session_id": session_id},
                {"_id": 0, "sender": 1, "text": 1},
            )
            .sort("created_at", -1)
            .limit(12)
        )
        docs = await cursor.to_list(length=12)
        docs.reverse()
        return docs

    async def _insert_user_msg():
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

    history_docs, _ = await asyncio.gather(_fetch_history(), _insert_user_msg())

    is_first = len(history_docs) == 0
    title = text[:60] if is_first else None

    messages = [{"role": "system", "content": FASHION_SYSTEM_PROMPT}]
    for msg in history_docs:
        role = "assistant" if msg.get("sender") == "ai" else "user"
        messages.append({"role": role, "content": msg.get("text", "")})
    messages.append({"role": "user", "content": text})

    reply = await _generate_reply(text, messages, history_docs)

    ai_now = datetime.now(timezone.utc)

    # Save AI message and update session in parallel
    async def _insert_ai_msg():
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

    async def _upsert_session():
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

    await asyncio.gather(_insert_ai_msg(), _upsert_session())

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
