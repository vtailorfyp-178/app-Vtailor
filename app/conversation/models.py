"""
Conversation System Models
───────────────────────────
Pydantic schemas for chat, calls, media, typing, and WebSocket events.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    TAILOR = "tailor"
    CUSTOMER = "customer"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"  # voice note
    CALL_LOG = "call_log"  # system message for call events
    SYSTEM = "system"  # general system messages


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class CallType(str, Enum):
    VOICE = "voice"
    VIDEO = "video"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    DECLINED = "declined"
    MISSED = "missed"
    ENDED = "ended"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


# ── Request / Response Schemas ─────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    sender_id: str = Field(..., min_length=1)
    content: str = Field(default="", max_length=4000)
    message_type: MessageType = MessageType.TEXT
    # For media messages — populated after presigned-URL upload
    media_url: str | None = None
    media_key: str | None = None  # S3 key
    media_mime: str | None = None
    media_size: int | None = None  # bytes
    media_duration: int | None = None  # seconds (audio/video)
    thumbnail_url: str | None = None  # video thumbnail
    reply_to_id: str | None = None  # quoted message id


class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    sender_id: str
    sender_role: UserRole
    content: str
    message_type: MessageType
    status: MessageStatus
    media_url: str | None
    media_mime: str | None
    media_size: int | None
    media_duration: int | None
    thumbnail_url: str | None
    reply_to_id: str | None
    reply_to_preview: str | None  # snippet of quoted message
    is_deleted: bool
    created_at: str
    updated_at: str


class ConversationOut(BaseModel):
    conversation_id: str
    tailor_id: str
    customer_id: str
    tailor_name: str
    customer_name: str
    tailor_avatar: str | None
    customer_avatar: str | None
    last_message: str | None
    last_message_type: MessageType | None
    last_message_at: str | None
    unread_count: int
    status: ConversationStatus
    created_at: str


class CreateConversationRequest(BaseModel):
    tailor_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)


class MarkReadRequest(BaseModel):
    conversation_id: str
    user_id: str
    up_to_message_id: str | None = None  # mark all up to this id; None = all


class TypingEvent(BaseModel):
    conversation_id: str
    user_id: str
    is_typing: bool


class PresignedUrlRequest(BaseModel):
    conversation_id: str
    sender_id: str
    filename: str
    content_type: str  # e.g. "image/jpeg", "video/mp4"
    file_size: int  # bytes — server validates max size


class PresignedUrlResponse(BaseModel):
    upload_url: str  # PUT to this URL
    media_key: str  # pass back in SendMessageRequest
    expires_in: int  # seconds


# ── Call Schemas ───────────────────────────────────────────────────────────────

class InitiateCallRequest(BaseModel):
    conversation_id: str
    caller_id: str
    callee_id: str
    call_type: CallType


class CallActionRequest(BaseModel):
    call_id: str
    user_id: str
    action: CallStatus  # answered / declined / ended


class CallOut(BaseModel):
    call_id: str
    conversation_id: str
    caller_id: str
    callee_id: str
    call_type: CallType
    status: CallStatus
    duration_seconds: int | None
    started_at: str | None
    ended_at: str | None
    created_at: str


# ── WebSocket Payloads (JSON envelopes) ───────────────────────────────────────

class WSEventType(str, Enum):
    NEW_MESSAGE = "new_message"
    MESSAGE_STATUS = "message_status"
    TYPING = "typing"
    CALL_INCOMING = "call_incoming"
    CALL_STATUS = "call_status"
    ONLINE_STATUS = "online_status"
    ERROR = "error"


class WSEnvelope(BaseModel):
    event: WSEventType
    data: Any


# ── MongoDB Document Helpers ───────────────────────────────────────────────────

def new_message_doc(req: SendMessageRequest, sender_role: UserRole) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "message_id": str(uuid.uuid4()),
        "conversation_id": req.conversation_id,
        "sender_id": req.sender_id,
        "sender_role": sender_role.value,
        "content": req.content,
        "message_type": req.message_type.value,
        "status": MessageStatus.SENT.value,
        "media_url": req.media_url,
        "media_key": req.media_key,
        "media_mime": req.media_mime,
        "media_size": req.media_size,
        "media_duration": req.media_duration,
        "thumbnail_url": req.thumbnail_url,
        "reply_to_id": req.reply_to_id,
        "reply_to_preview": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }


def new_call_doc(req: InitiateCallRequest) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "call_id": str(uuid.uuid4()),
        "conversation_id": req.conversation_id,
        "caller_id": req.caller_id,
        "callee_id": req.callee_id,
        "call_type": req.call_type.value,
        "status": CallStatus.INITIATED.value,
        "duration_seconds": None,
        "started_at": None,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def doc_to_message_out(doc: dict) -> MessageOut:
    return MessageOut(
        message_id=doc["message_id"],
        conversation_id=doc["conversation_id"],
        sender_id=doc["sender_id"],
        sender_role=UserRole(doc["sender_role"]),
        content=doc.get("content", ""),
        message_type=MessageType(doc["message_type"]),
        status=MessageStatus(doc["status"]),
        media_url=doc.get("media_url"),
        media_mime=doc.get("media_mime"),
        media_size=doc.get("media_size"),
        media_duration=doc.get("media_duration"),
        thumbnail_url=doc.get("thumbnail_url"),
        reply_to_id=doc.get("reply_to_id"),
        reply_to_preview=doc.get("reply_to_preview"),
        is_deleted=doc.get("is_deleted", False),
        created_at=_iso(doc.get("created_at")) or "",
        updated_at=_iso(doc.get("updated_at")) or "",
    )


def doc_to_call_out(doc: dict) -> CallOut:
    return CallOut(
        call_id=doc["call_id"],
        conversation_id=doc["conversation_id"],
        caller_id=doc["caller_id"],
        callee_id=doc["callee_id"],
        call_type=CallType(doc["call_type"]),
        status=CallStatus(doc["status"]),
        duration_seconds=doc.get("duration_seconds"),
        started_at=_iso(doc.get("started_at")),
        ended_at=_iso(doc.get("ended_at")),
        created_at=_iso(doc["created_at"]) or "",
    )
