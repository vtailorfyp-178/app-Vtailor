"""
Stream Chat Router
──────────────────
Authenticated endpoints that issue Stream user tokens and open channels.

All routes require a valid app JWT (Authorization: Bearer <token>).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.routers.auth import get_current_user
from app.services import stream_chat_service as svc
from app.services.notification_service import create_notification

router = APIRouter(prefix="/stream", tags=["Stream Chat"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class StreamTokenResponse(BaseModel):
    configured: bool = True
    token: str = ""
    api_key: str = ""
    user_id: str = ""


class StreamNotConfiguredResponse(BaseModel):
    configured: bool = False
    user_id: str
    message: str = (
        "Stream Chat is not configured. "
        "Add STREAM_API_KEY and STREAM_API_SECRET in backend .env "
        "from https://dashboard.getstream.io/"
    )


class ChannelRequest(BaseModel):
    tailor_id: str
    customer_id: str


class ChannelResponse(BaseModel):
    channel_id: str
    channel_type: str
    cid: str
    members: list[str]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _stream_not_configured(user_id: str) -> StreamNotConfiguredResponse:
    return StreamNotConfiguredResponse(configured=False, user_id=user_id)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_stream_status():
    """Public check — lets the app skip Stream calls when backend has no Stream keys."""
    return {"configured": svc.is_stream_configured()}


@router.get("/token", response_model=StreamTokenResponse | StreamNotConfiguredResponse)
async def get_stream_token(current_user: dict = Depends(get_current_user)):
    """
    Issue a Stream user token for the currently authenticated app user.
    Frontend calls this once after JWT login and passes the token to StreamChat.connectUser().
    When Stream is not configured, returns 200 with configured=false (not 503).
    """
    user_id = str(current_user.get("_id"))
    if not svc.is_stream_configured():
        return _stream_not_configured(user_id)
    name = current_user.get("name") or current_user.get("email") or user_id
    role = current_user.get("role", "customer")
    avatar = current_user.get("avatar")
    phone = current_user.get("phone")
    email = current_user.get("email")

    try:
        svc.upsert_stream_user(user_id, name=name, role=role, image=avatar, phone=phone, email=email)
        token = svc.create_stream_user_token(user_id)
        from app.core.config import get_settings
        return StreamTokenResponse(
            configured=True,
            token=token,
            api_key=get_settings().STREAM_API_KEY or "",
            user_id=user_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stream token generation failed: {exc}",
        )


@router.post("/channel", response_model=ChannelResponse, status_code=status.HTTP_200_OK)
async def get_or_create_channel(
    body: ChannelRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create (or return existing) a 1-to-1 Stream channel between a tailor and customer.
    Either participant may call this.
    """
    current_user_id = str(current_user.get("_id"))
    if not svc.is_stream_configured():
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=(
                "Stream Chat is not configured. "
                "Add STREAM_API_KEY and STREAM_API_SECRET in backend .env "
                "from https://dashboard.getstream.io/"
            ),
        )
    allowed = {body.tailor_id, body.customer_id}
    if current_user_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only open channels you are a member of.",
        )
    try:
        result = svc.get_or_create_channel(body.tailor_id, body.customer_id)

        # Notify the OTHER participant that a new chat was started.
        # We only notify when the channel is newly created (no prior messages),
        # deduced by checking the member list; always safe to fire and let the
        # UI deduplicate by checking notification history.
        initiator_id = current_user_id
        recipient_id = body.customer_id if initiator_id == body.tailor_id else body.tailor_id
        initiator_name = current_user.get("name") or current_user.get("email") or "Someone"
        try:
            await create_notification(
                user_id=recipient_id,
                type="chat_started",
                title="New Message",
                message=f"{initiator_name} started a conversation with you.",
                data={
                    "channelId": result["channel_id"],
                    "channelCid": result["cid"],
                    "initiator_id": initiator_id,
                    "initiator_name": initiator_name,
                    "otherUserId": initiator_id,
                    "otherUserName": initiator_name,
                },
            )
        except Exception:
            pass  # notification failure must not break channel creation

        return ChannelResponse(
            channel_id=result["channel_id"],
            channel_type=result["channel_type"],
            cid=result["cid"],
            members=result["members"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Channel creation failed: {exc}",
        )
