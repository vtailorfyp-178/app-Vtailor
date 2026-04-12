"""
ConversationService
───────────────────
All MongoDB operations for the tailor-customer conversation system.
Injected into routers via FastAPI dependency.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .models import (
    CallActionRequest,
    CallOut,
    CallStatus,
    ConversationOut,
    ConversationStatus,
    InitiateCallRequest,
    MarkReadRequest,
    MessageOut,
    MessageStatus,
    MessageType,
    SendMessageRequest,
    UserRole,
    _iso,
    doc_to_call_out,
    doc_to_message_out,
    new_call_doc,
    new_message_doc,
)

log = logging.getLogger(__name__)

# Collection names
COL_CONVERSATIONS = "conversations"
COL_MESSAGES = "messages"
COL_CALLS = "calls"
COL_USERS = "users"

# Media limits
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


class ConversationService:
    def __init__(self, db: Any) -> None:
        self.db = db

    # ── Indexes (call once at startup) ────────────────────────────────────────

    async def ensure_indexes(self) -> None:
        await self.db[COL_CONVERSATIONS].create_index(
            [("tailor_id", ASCENDING), ("customer_id", ASCENDING)], unique=True
        )
        await self.db[COL_CONVERSATIONS].create_index([("tailor_id", ASCENDING)])
        await self.db[COL_CONVERSATIONS].create_index([("customer_id", ASCENDING)])

        await self.db[COL_MESSAGES].create_index(
            [("conversation_id", ASCENDING), ("created_at", ASCENDING)]
        )
        await self.db[COL_MESSAGES].create_index([("sender_id", ASCENDING)])
        await self.db[COL_MESSAGES].create_index([("message_id", ASCENDING)], unique=True)

        await self.db[COL_CALLS].create_index([("call_id", ASCENDING)], unique=True)
        await self.db[COL_CALLS].create_index([("conversation_id", ASCENDING)])

        log.info("Conversation indexes ensured.")

    # ── User helpers ──────────────────────────────────────────────────────────

    async def _get_user(self, user_id: str) -> dict | None:
        # Support both legacy user_id field and Mongo _id string identifiers.
        user = await self.db[COL_USERS].find_one({"user_id": user_id}, {"_id": 0})
        if user:
            return user

        try:
            return await self.db[COL_USERS].find_one({"_id": ObjectId(user_id)}, {"_id": 0})
        except Exception:
            return None

    async def _assert_participant(self, conversation_id: str, user_id: str) -> dict:
        conv = await self.db[COL_CONVERSATIONS].find_one(
            {"conversation_id": conversation_id}, {"_id": 0}
        )
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found.")
        if user_id not in (conv["tailor_id"], conv["customer_id"]):
            raise PermissionError("User is not a participant of this conversation.")
        return conv

    # ── Conversations ─────────────────────────────────────────────────────────

    async def get_or_create_conversation(
        self, tailor_id: str, customer_id: str
    ) -> ConversationOut:
        existing = await self.db[COL_CONVERSATIONS].find_one(
            {"tailor_id": tailor_id, "customer_id": customer_id}, {"_id": 0}
        )
        if existing:
            return await self._enrich_conversation(existing)

        tailor = await self._get_user(tailor_id) or {}
        customer = await self._get_user(customer_id) or {}
        now = datetime.now(timezone.utc)

        doc = {
            "conversation_id": str(uuid.uuid4()),
            "tailor_id": tailor_id,
            "customer_id": customer_id,
            "tailor_name": tailor.get("name", "Tailor"),
            "customer_name": customer.get("name", "Customer"),
            "tailor_avatar": tailor.get("avatar_url"),
            "customer_avatar": customer.get("avatar_url"),
            "last_message": None,
            "last_message_type": None,
            "last_message_at": None,
            "unread_tailor": 0,
            "unread_customer": 0,
            "status": ConversationStatus.ACTIVE.value,
            "created_at": now,
            "updated_at": now,
        }
        await self.db[COL_CONVERSATIONS].insert_one(doc)
        return await self._enrich_conversation(doc)

    async def list_conversations(
        self, user_id: str, role: UserRole, limit: int = 50
    ) -> list[ConversationOut]:
        field = "tailor_id" if role == UserRole.TAILOR else "customer_id"
        cursor = (
            self.db[COL_CONVERSATIONS]
            .find({field: user_id, "status": {"$ne": ConversationStatus.BLOCKED.value}}, {"_id": 0})
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        result = []
        for doc in docs:
            try:
                result.append(await self._enrich_conversation(doc, requesting_user=user_id))
            except Exception as e:
                log.warning("Skipping malformed conversation doc: %s", e)
        return result

    async def _enrich_conversation(
        self, doc: dict, requesting_user: str | None = None
    ) -> ConversationOut:
        unread = 0
        if requesting_user:
            if requesting_user == doc.get("tailor_id"):
                unread = doc.get("unread_tailor", 0)
            elif requesting_user == doc.get("customer_id"):
                unread = doc.get("unread_customer", 0)

        lm_type = doc.get("last_message_type")
        return ConversationOut(
            conversation_id=doc["conversation_id"],
            tailor_id=doc["tailor_id"],
            customer_id=doc["customer_id"],
            tailor_name=doc.get("tailor_name", "Tailor"),
            customer_name=doc.get("customer_name", "Customer"),
            tailor_avatar=doc.get("tailor_avatar"),
            customer_avatar=doc.get("customer_avatar"),
            last_message=doc.get("last_message"),
            last_message_type=MessageType(lm_type) if lm_type else None,
            last_message_at=_iso(doc.get("last_message_at")),
            unread_count=unread,
            status=ConversationStatus(doc.get("status", ConversationStatus.ACTIVE.value)),
            created_at=_iso(doc.get("created_at")) or "",
        )

    # ── Messages ──────────────────────────────────────────────────────────────

    async def send_message(self, req: SendMessageRequest) -> MessageOut:
        conv = await self._assert_participant(req.conversation_id, req.sender_id)

        sender_role = (
            UserRole.TAILOR if req.sender_id == conv["tailor_id"] else UserRole.CUSTOMER
        )
        doc = new_message_doc(req, sender_role)

        # Attach reply preview
        if req.reply_to_id:
            quoted = await self.db[COL_MESSAGES].find_one(
                {"message_id": req.reply_to_id}, {"content": 1, "message_type": 1}
            )
            if quoted:
                doc["reply_to_preview"] = (quoted.get("content") or "")[:80]

        await self.db[COL_MESSAGES].insert_one(doc)

        # Update conversation summary
        now = datetime.now(timezone.utc)
        unread_field = (
            "unread_customer"
            if sender_role == UserRole.TAILOR
            else "unread_tailor"
        )

        # Preview text based on type
        preview = self._message_preview(req)

        await self.db[COL_CONVERSATIONS].update_one(
            {"conversation_id": req.conversation_id},
            {
                "$set": {
                    "last_message": preview,
                    "last_message_type": req.message_type.value,
                    "last_message_at": now,
                    "updated_at": now,
                },
                "$inc": {unread_field: 1},
            },
        )

        return doc_to_message_out(doc)

    def _message_preview(self, req: SendMessageRequest) -> str:
        if req.message_type == MessageType.TEXT:
            return (req.content or "")[:80]
        if req.message_type == MessageType.IMAGE:
            return "📷 Photo"
        if req.message_type == MessageType.VIDEO:
            return "🎥 Video"
        if req.message_type == MessageType.AUDIO:
            return "🎤 Voice message"
        if req.message_type == MessageType.CALL_LOG:
            return "📞 Call"
        return req.content[:80] if req.content else ""

    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        before_id: str | None = None,
        limit: int = 40,
    ) -> list[MessageOut]:
        await self._assert_participant(conversation_id, user_id)

        query: dict = {"conversation_id": conversation_id, "is_deleted": False}

        if before_id:
            ref = await self.db[COL_MESSAGES].find_one({"message_id": before_id})
            if ref:
                query["created_at"] = {"$lt": ref["created_at"]}

        cursor = (
            self.db[COL_MESSAGES]
            .find(query, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        docs.reverse()
        return [doc_to_message_out(d) for d in docs]

    async def mark_read(self, req: MarkReadRequest) -> int:
        conv = await self._assert_participant(req.conversation_id, req.user_id)

        # Determine which messages to mark
        query: dict = {
            "conversation_id": req.conversation_id,
            "sender_id": {"$ne": req.user_id},
            "status": {"$in": [MessageStatus.SENT.value, MessageStatus.DELIVERED.value]},
        }
        if req.up_to_message_id:
            ref = await self.db[COL_MESSAGES].find_one({"message_id": req.up_to_message_id})
            if ref:
                query["created_at"] = {"$lte": ref["created_at"]}

        result = await self.db[COL_MESSAGES].update_many(
            query,
            {"$set": {"status": MessageStatus.READ.value, "updated_at": datetime.now(timezone.utc)}},
        )

        # Reset unread counter
        unread_field = (
            "unread_tailor" if req.user_id == conv["tailor_id"] else "unread_customer"
        )
        await self.db[COL_CONVERSATIONS].update_one(
            {"conversation_id": req.conversation_id},
            {"$set": {unread_field: 0}},
        )

        return result.modified_count

    async def update_message_status(
        self, message_id: str, status: MessageStatus
    ) -> bool:
        result = await self.db[COL_MESSAGES].update_one(
            {"message_id": message_id},
            {"$set": {"status": status.value, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Soft-delete — only sender can delete their own message."""
        result = await self.db[COL_MESSAGES].update_one(
            {"message_id": message_id, "sender_id": user_id},
            {"$set": {"is_deleted": True, "content": "", "media_url": None, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    # ── Calls ─────────────────────────────────────────────────────────────────

    async def initiate_call(self, req: InitiateCallRequest) -> CallOut:
        await self._assert_participant(req.conversation_id, req.caller_id)
        doc = new_call_doc(req)
        await self.db[COL_CALLS].insert_one(doc)
        return doc_to_call_out(doc)

    async def update_call_status(self, req: CallActionRequest) -> CallOut:
        call = await self.db[COL_CALLS].find_one({"call_id": req.call_id}, {"_id": 0})
        if not call:
            raise ValueError(f"Call {req.call_id} not found.")

        if req.user_id not in (call["caller_id"], call["callee_id"]):
            raise PermissionError("User is not a participant of this call.")

        now = datetime.now(timezone.utc)
        updates: dict = {"status": req.action.value, "updated_at": now}

        if req.action == CallStatus.ANSWERED:
            updates["started_at"] = now
        elif req.action in (CallStatus.ENDED, CallStatus.DECLINED, CallStatus.MISSED, CallStatus.FAILED):
            updates["ended_at"] = now
            started_at = call.get("started_at")
            if started_at and req.action == CallStatus.ENDED:
                duration = int((now - started_at).total_seconds())
                updates["duration_seconds"] = max(duration, 0)

        await self.db[COL_CALLS].update_one(
            {"call_id": req.call_id}, {"$set": updates}
        )

        # Insert a call-log system message into the conversation
        if req.action in (CallStatus.ENDED, CallStatus.MISSED, CallStatus.DECLINED):
            dur = updates.get("duration_seconds")
            if req.action == CallStatus.ENDED and dur is not None:
                mins, secs = divmod(dur, 60)
                text = f"📞 {call['call_type'].capitalize()} call ended — {mins}m {secs}s"
            elif req.action == CallStatus.MISSED:
                text = "📞 Missed call"
            else:
                text = "📞 Call declined"

            log_req = SendMessageRequest(
                conversation_id=call["conversation_id"],
                sender_id=call["caller_id"],
                content=text,
                message_type=MessageType.CALL_LOG,
            )
            conv = await self.db[COL_CONVERSATIONS].find_one(
                {"conversation_id": call["conversation_id"]}
            )
            role = UserRole.TAILOR if conv and call["caller_id"] == conv["tailor_id"] else UserRole.CUSTOMER
            log_doc = new_message_doc(log_req, role)
            await self.db[COL_MESSAGES].insert_one(log_doc)

        updated = await self.db[COL_CALLS].find_one({"call_id": req.call_id}, {"_id": 0})
        return doc_to_call_out(updated)

    async def get_call_history(
        self, conversation_id: str, user_id: str, limit: int = 20
    ) -> list[CallOut]:
        await self._assert_participant(conversation_id, user_id)
        cursor = (
            self.db[COL_CALLS]
            .find({"conversation_id": conversation_id}, {"_id": 0})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [doc_to_call_out(d) for d in docs]

    # ── Media ─────────────────────────────────────────────────────────────────

    def validate_media(self, content_type: str, file_size: int) -> None:
        type_limits = {
            "image": MAX_IMAGE_BYTES,
            "video": MAX_VIDEO_BYTES,
            "audio": MAX_AUDIO_BYTES,
        }
        media_category = content_type.split("/")[0]
        limit = type_limits.get(media_category)
        if limit is None:
            raise ValueError(f"Unsupported media type: {content_type}")
        if file_size > limit:
            limit_mb = limit // (1024 * 1024)
            raise ValueError(f"File exceeds {limit_mb}MB limit for {media_category}.")
