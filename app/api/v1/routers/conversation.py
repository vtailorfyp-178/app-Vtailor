"""
Conversation Router
───────────────────
REST + WebSocket endpoints for the tailor-customer chat system.

Mount in main.py:
    from app.api.v1.routers.conversation import create_conversation_router
    app.include_router(
        create_conversation_router(db=database, s3_client=s3, bucket=BUCKET_NAME),
        prefix="/api/v1/conversations",
        tags=["Conversations"],
    )
"""

import asyncio
import json
import logging
import uuid as _uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.conversation.models import (
    CallActionRequest,
    CallOut,
    ConversationOut,
    CreateConversationRequest,
    InitiateCallRequest,
    MarkReadRequest,
    MessageOut,
    MessageStatus,
    PresignedUrlRequest,
    PresignedUrlResponse,
    SendMessageRequest,
    TypingEvent,
    UserRole,
    WSEventType,
)
from app.conversation.service import ConversationService
from app.conversation.ws_manager import manager

log = logging.getLogger(__name__)

PRESIGN_EXPIRY = 300  # 5 minutes
bearer = HTTPBearer(auto_error=False)


def create_conversation_router(
    db: Any,
    s3_client: Any,  # boto3 S3 client
    bucket: str,  # S3 bucket name
) -> APIRouter:

    router = APIRouter()
    svc = ConversationService(db)

    # ── Dependency ─────────────────────────────────────────────────────────────

    async def get_svc() -> ConversationService:
        return svc

    # ── Conversations ──────────────────────────────────────────────────────────

    @router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
    async def create_or_get_conversation(
        body: CreateConversationRequest,
        s: ConversationService = Depends(get_svc),
    ) -> ConversationOut:
        try:
            return await s.get_or_create_conversation(body.tailor_id, body.customer_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/{user_id}", response_model=list[ConversationOut])
    async def list_my_conversations(
        user_id: str,
        role: UserRole = Query(..., description="tailor or customer"),
        limit: int = Query(50, ge=1, le=200),
        s: ConversationService = Depends(get_svc),
    ) -> list[ConversationOut]:
        return await s.list_conversations(user_id, role, limit)

    # ── Messages ───────────────────────────────────────────────────────────────

    @router.post("/messages/send", response_model=MessageOut)
    async def send_message(
        body: SendMessageRequest,
        s: ConversationService = Depends(get_svc),
    ) -> MessageOut:
        try:
            msg = await s.send_message(body)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Real-time delivery to recipient
        conv = await db["conversations"].find_one(
            {"conversation_id": body.conversation_id}, {"tailor_id": 1, "customer_id": 1}
        )
        if conv:
            participants = [conv["tailor_id"], conv["customer_id"]]
            payload = {
                "event": WSEventType.NEW_MESSAGE.value,
                "data": msg.model_dump(),
            }
            await manager.broadcast_to_conversation(
                participants, payload, exclude_sender=body.sender_id
            )

            # Mark delivered if recipient is online
            other_id = next((p for p in participants if p != body.sender_id), None)
            if other_id and manager.is_online(other_id):
                await s.update_message_status(msg.message_id, MessageStatus.DELIVERED)
                # Notify sender of delivery
                await manager.send_to_user(body.sender_id, {
                    "event": WSEventType.MESSAGE_STATUS.value,
                    "data": {"message_id": msg.message_id, "status": MessageStatus.DELIVERED.value},
                })

        return msg

    @router.get("/messages/{conversation_id}", response_model=list[MessageOut])
    async def get_messages(
        conversation_id: str,
        user_id: str = Query(...),
        before_id: str | None = Query(None),
        limit: int = Query(40, ge=1, le=100),
        s: ConversationService = Depends(get_svc),
    ) -> list[MessageOut]:
        try:
            return await s.get_messages(conversation_id, user_id, before_id, limit)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    @router.post("/messages/read", response_model=dict)
    async def mark_messages_read(
        body: MarkReadRequest,
        s: ConversationService = Depends(get_svc),
    ) -> dict:
        try:
            count = await s.mark_read(body)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        # Notify the other participant(s) about read receipts
        conv = await db["conversations"].find_one(
            {"conversation_id": body.conversation_id}, {"tailor_id": 1, "customer_id": 1}
        )
        if conv:
            participants = [conv["tailor_id"], conv["customer_id"]]
            payload = {
                "event": WSEventType.MESSAGE_STATUS.value,
                "data": {
                    "conversation_id": body.conversation_id,
                    "read_by": body.user_id,
                    "status": MessageStatus.READ.value,
                },
            }
            await manager.broadcast_to_conversation(
                participants, payload, exclude_sender=body.user_id
            )

        return {"marked_read": count}

    @router.delete("/messages/{message_id}", response_model=dict)
    async def delete_message(
        message_id: str,
        user_id: str = Query(...),
        s: ConversationService = Depends(get_svc),
    ) -> dict:
        deleted = await s.delete_message(message_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Message not found or not yours.")
        return {"deleted": True}

    # ── Media (S3 Presigned URL) ───────────────────────────────────────────────

    @router.post("/media/presign", response_model=PresignedUrlResponse)
    async def get_presigned_url(
        body: PresignedUrlRequest,
        s: ConversationService = Depends(get_svc),
    ) -> PresignedUrlResponse:
        try:
            s.validate_media(body.content_type, body.file_size)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        ext = body.filename.rsplit(".", 1)[-1] if "." in body.filename else "bin"
        key = f"conversations/{body.conversation_id}/{body.sender_id}/{_uuid.uuid4()}.{ext}"

        try:
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ContentType": body.content_type,
                },
                ExpiresIn=PRESIGN_EXPIRY,
            )
        except ClientError as e:
            log.error("S3 presign error: %s", e)
            raise HTTPException(status_code=500, detail="Could not generate upload URL.")

        return PresignedUrlResponse(
            upload_url=url,
            media_key=key,
            expires_in=PRESIGN_EXPIRY,
        )

    @router.get("/media/url/{media_key:path}", response_model=dict)
    async def get_download_url(media_key: str) -> dict:
        """Get a temporary download URL for a private S3 media object."""
        try:
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": media_key},
                ExpiresIn=3600,
            )
            return {"url": url}
        except ClientError as e:
            raise HTTPException(status_code=500, detail="Could not generate download URL.")

    # ── Calls ──────────────────────────────────────────────────────────────────

    @router.post("/calls/initiate", response_model=CallOut, status_code=status.HTTP_201_CREATED)
    async def initiate_call(
        body: InitiateCallRequest,
        s: ConversationService = Depends(get_svc),
    ) -> CallOut:
        try:
            call = await s.initiate_call(body)
        except (ValueError, PermissionError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Notify callee in real-time
        await manager.send_to_user(body.callee_id, {
            "event": WSEventType.CALL_INCOMING.value,
            "data": call.model_dump(),
        })

        return call

    @router.post("/calls/action", response_model=CallOut)
    async def call_action(
        body: CallActionRequest,
        s: ConversationService = Depends(get_svc),
    ) -> CallOut:
        try:
            call = await s.update_call_status(body)
        except (ValueError, PermissionError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Notify both participants of call status change
        payload = {"event": WSEventType.CALL_STATUS.value, "data": call.model_dump()}
        await manager.send_to_user(call.caller_id, payload)
        await manager.send_to_user(call.callee_id, payload)

        return call

    @router.get("/calls/{conversation_id}", response_model=list[CallOut])
    async def get_call_history(
        conversation_id: str,
        user_id: str = Query(...),
        limit: int = Query(20, ge=1, le=100),
        s: ConversationService = Depends(get_svc),
    ) -> list[CallOut]:
        try:
            return await s.get_call_history(conversation_id, user_id, limit)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

    # ── Typing indicator (REST fallback) ──────────────────────────────────────

    @router.post("/typing", status_code=204)
    async def typing_indicator(body: TypingEvent) -> None:
        conv = await db["conversations"].find_one(
            {"conversation_id": body.conversation_id},
            {"tailor_id": 1, "customer_id": 1},
        )
        if conv:
            participants = [conv["tailor_id"], conv["customer_id"]]
            await manager.broadcast_to_conversation(
                participants,
                {"event": WSEventType.TYPING.value, "data": body.model_dump()},
                exclude_sender=body.user_id,
            )

    # ── WebSocket ──────────────────────────────────────────────────────────────

    @router.websocket("/ws/{user_id}")
    async def websocket_endpoint(ws: WebSocket, user_id: str) -> None:
        """
        WebSocket per user.

        Client sends JSON frames:
          {"event": "typing",         "data": {"conversation_id": "...", "is_typing": true}}
          {"event": "mark_read",      "data": {"conversation_id": "...", "up_to_message_id": "..."}}
          {"event": "ping",           "data": {}}

        Server pushes:
          new_message, message_status, typing, call_incoming, call_status, online_status, ping
        """
        await manager.connect(user_id, ws)
        log.info("WS open: user=%s", user_id)

        # Announce presence to all connected users
        await _broadcast_presence(user_id, online=True)

        try:
            while True:
                try:
                    raw = await asyncio.wait_for(ws.receive_text(), timeout=60)
                except asyncio.TimeoutError:
                    await manager.ping(ws)
                    continue

                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    await manager.send_error(ws, "INVALID_JSON", "Frame must be valid JSON.")
                    continue

                event = frame.get("event")
                data = frame.get("data", {})

                if event == "typing":
                    conv = await db["conversations"].find_one(
                        {"conversation_id": data.get("conversation_id")},
                        {"tailor_id": 1, "customer_id": 1},
                    )
                    if conv:
                        participants = [conv["tailor_id"], conv["customer_id"]]
                        await manager.broadcast_to_conversation(
                            participants,
                            {"event": WSEventType.TYPING.value, "data": {**data, "user_id": user_id}},
                            exclude_sender=user_id,
                        )

                elif event == "mark_read":
                    req = MarkReadRequest(
                        conversation_id=data.get("conversation_id", ""),
                        user_id=user_id,
                        up_to_message_id=data.get("up_to_message_id"),
                    )
                    try:
                        await svc.mark_read(req)
                    except Exception as e:
                        await manager.send_error(ws, "MARK_READ_FAILED", str(e))

                elif event == "ping":
                    await ws.send_text(json.dumps({"event": "pong", "data": {}}))

        except WebSocketDisconnect:
            log.info("WS closed: user=%s", user_id)
        except Exception as e:
            log.error("WS error user=%s: %s", user_id, e)
        finally:
            await manager.disconnect(user_id, ws)
            await _broadcast_presence(user_id, online=False)

    async def _broadcast_presence(user_id: str, online: bool) -> None:
        """Broadcast online/offline status to all connected users."""
        payload = {
            "event": WSEventType.ONLINE_STATUS.value,
            "data": {"user_id": user_id, "online": online},
        }
        for uid in manager.online_users():
            if uid != user_id:
                await manager.send_to_user(uid, payload)

    return router
