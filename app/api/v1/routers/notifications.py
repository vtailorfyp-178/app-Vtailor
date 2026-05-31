"""
Notifications Router
────────────────────
Authenticated endpoints for per-user notification management.

All routes require a valid app JWT (Authorization: Bearer <token>).

Routes:
    GET    /notifications              — list all notifications (newest first)
    GET    /notifications/unread-count — number of unread notifications
    POST   /notifications              — create a notification (called by frontend
                                         for client-side events, e.g. chat messages)
    PATCH  /notifications/{id}/read   — mark one notification as read
    PATCH  /notifications/read-all    — mark all notifications as read
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Any

from app.api.v1.routers.auth import get_current_user
from app.services import notification_service as svc

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    data: dict
    is_read: bool
    created_at: str


class NotificationCreateRequest(BaseModel):
    type: str
    title: str
    message: str
    data: dict[str, Any] = {}


class UnreadCountResponse(BaseModel):
    count: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _out(doc: dict) -> NotificationOut:
    return NotificationOut(
        id=doc["id"],
        user_id=doc["user_id"],
        type=doc["type"],
        title=doc["title"],
        message=doc["message"],
        data=doc.get("data") or {},
        is_read=doc.get("is_read", False),
        created_at=doc["created_at"].isoformat() if hasattr(doc.get("created_at"), "isoformat") else str(doc.get("created_at", "")),
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Return all notifications for the authenticated user, newest first."""
    user_id = str(current_user.get("_id"))
    docs = await svc.get_user_notifications(user_id=user_id, limit=limit)
    return [_out(d) for d in docs]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(current_user: dict = Depends(get_current_user)):
    """Return the number of unread notifications for the authenticated user."""
    user_id = str(current_user.get("_id"))
    count = await svc.count_unread(user_id=user_id)
    return UnreadCountResponse(count=count)


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a notification for the authenticated user.
    Used by the frontend to persist client-side events (e.g. new chat messages)
    so they appear in the in-app notification list.
    """
    user_id = str(current_user.get("_id"))
    doc = await svc.create_notification(
        user_id=user_id,
        type=body.type,
        title=body.title,
        message=body.message,
        data=body.data,
    )
    return _out(doc)


@router.patch("/read-all", response_model=dict)
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications for the authenticated user as read."""
    user_id = str(current_user.get("_id"))
    updated = await svc.mark_all_read(user_id=user_id)
    return {"updated": updated}


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_one_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Mark a single notification as read."""
    user_id = str(current_user.get("_id"))
    ok = await svc.mark_notification_read(user_id=user_id, notification_id=notification_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"updated": True}
