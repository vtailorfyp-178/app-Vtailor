"""
Conversation Router
───────────────────
MIGRATION NOTE (May 2026):
  Custom WebSocket chat has been replaced by Stream Chat.
  The following endpoints are DEPRECATED and return HTTP 410 Gone:
    - POST   /conversations             (create/get conversation)
    - GET    /conversations/{user_id}   (list conversations)
    - POST   /conversations/messages/send
    - GET    /conversations/messages/{id}
    - POST   /conversations/messages/read
    - DELETE /conversations/messages/{id}
    - POST   /conversations/media/presign
    - GET    /conversations/media/url/{key}
    - POST   /conversations/typing
    - WS     /conversations/ws/{user_id}

  The following endpoints remain ACTIVE (call flow unchanged):
    - POST   /conversations/calls/initiate
    - POST   /conversations/calls/action
    - GET    /conversations/calls/{conversation_id}

Mount in main.py:
    from app.api.v1.routers.conversation import create_conversation_router
    app.include_router(
        create_conversation_router(db=database, s3_client=s3, bucket=BUCKET_NAME),
        prefix="/api/v1/conversations",
        tags=["Conversations"],
    )
"""

import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.conversation.models import (
    CallActionRequest,
    CallOut,
    ConversationOut,
    CreateConversationRequest,
    InitiateCallRequest,
    MarkReadRequest,
    MessageOut,
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

_DEPRECATED_MSG = (
    "This endpoint is deprecated. Chat has been migrated to Stream Chat. "
    "Use the /stream/* endpoints instead."
)


def create_conversation_router(
    db: Any,
    s3_client: Any,
    bucket: str,
) -> APIRouter:

    router = APIRouter()
    svc = ConversationService(db)

    async def get_svc() -> ConversationService:
        return svc

    # ── Conversations (DEPRECATED) ─────────────────────────────────────────────

    @router.post("", status_code=status.HTTP_410_GONE, deprecated=True,
                 summary="[DEPRECATED] Create/get conversation — use Stream Chat")
    async def create_or_get_conversation(body: CreateConversationRequest) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    @router.get("/{user_id}", status_code=status.HTTP_410_GONE, deprecated=True,
                summary="[DEPRECATED] List conversations — use Stream Chat")
    async def list_my_conversations(user_id: str) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    # ── Messages (DEPRECATED) ─────────────────────────────────────────────────

    @router.post("/messages/send", status_code=status.HTTP_410_GONE, deprecated=True,
                 summary="[DEPRECATED] Send message — use Stream Chat")
    async def send_message(body: SendMessageRequest) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    @router.get("/messages/{conversation_id}", status_code=status.HTTP_410_GONE, deprecated=True,
                summary="[DEPRECATED] Get messages — use Stream Chat")
    async def get_messages(conversation_id: str) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    @router.post("/messages/read", status_code=status.HTTP_410_GONE, deprecated=True,
                 summary="[DEPRECATED] Mark read — use Stream Chat")
    async def mark_messages_read(body: MarkReadRequest) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    @router.delete("/messages/{message_id}", status_code=status.HTTP_410_GONE, deprecated=True,
                   summary="[DEPRECATED] Delete message — use Stream Chat")
    async def delete_message(message_id: str) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    # ── Media (DEPRECATED) ────────────────────────────────────────────────────

    @router.post("/media/presign", status_code=status.HTTP_410_GONE, deprecated=True,
                 summary="[DEPRECATED] Presign upload — use Stream Chat file upload")
    async def get_presigned_url(body: PresignedUrlRequest) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    @router.get("/media/url/{media_key:path}", status_code=status.HTTP_410_GONE, deprecated=True,
                summary="[DEPRECATED] Download URL — use Stream Chat CDN")
    async def get_download_url(media_key: str) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    # ── Typing (DEPRECATED) ───────────────────────────────────────────────────

    @router.post("/typing", status_code=status.HTTP_410_GONE, deprecated=True,
                 summary="[DEPRECATED] Typing indicator — use Stream Chat typing events")
    async def typing_indicator(body: TypingEvent) -> dict:
        raise HTTPException(status_code=410, detail=_DEPRECATED_MSG)

    # ── WebSocket (DEPRECATED) ────────────────────────────────────────────────

    @router.websocket("/ws/{user_id}")
    async def websocket_endpoint(ws: WebSocket, user_id: str) -> None:
        """[DEPRECATED] Custom WebSocket — use Stream Chat. Closes immediately with code 4410."""
        await ws.accept()
        await ws.close(
            code=4410,
            reason="Deprecated: chat has migrated to Stream Chat. Use the /stream/token endpoint.",
        )

    # ── Calls (ACTIVE — unchanged) ────────────────────────────────────────────

    @router.post("/calls/initiate", response_model=CallOut, status_code=status.HTTP_201_CREATED)
    async def initiate_call(
        body: InitiateCallRequest,
        s: ConversationService = Depends(get_svc),
    ) -> CallOut:
        try:
            call = await s.initiate_call(body)
        except (ValueError, PermissionError) as e:
            raise HTTPException(status_code=400, detail=str(e))

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

    return router
