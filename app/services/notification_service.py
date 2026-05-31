"""
Notification service — create, fetch, and mark notifications.

Notifications are stored in the ``notifications`` MongoDB collection.
Each document:
    _id          : ObjectId
    user_id      : str  (recipient)
    type         : str  (chat_message | chat_started | wallet_pending |
                         wallet_confirmed | wallet_failed)
    title        : str
    message      : str
    data         : dict  (extra payload, e.g. channel_id, tx_id)
    is_read      : bool
    created_at   : datetime (UTC)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.db.mongodb import get_database


def _serialize(doc: dict) -> dict:
    """Convert ObjectId fields to strings so the dict is JSON-safe."""
    doc["id"] = str(doc.pop("_id"))
    return doc


async def create_notification(
    user_id: str,
    type: str,
    title: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict:
    """Insert a notification for *user_id* and return the serialised document."""
    db = get_database()
    doc = {
        "user_id": user_id,
        "type": type,
        "title": title,
        "message": message,
        "data": data or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.notifications.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def get_user_notifications(user_id: str, limit: int = 50) -> list[dict]:
    """Return the most recent *limit* notifications for *user_id*, newest first."""
    db = get_database()
    cursor = db.notifications.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
        limit=limit,
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize(d) for d in docs]


async def mark_notification_read(user_id: str, notification_id: str) -> bool:
    """Mark a single notification as read. Returns True if a document was updated."""
    db = get_database()
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return False
    result = await db.notifications.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"is_read": True}},
    )
    return result.modified_count > 0


async def mark_all_read(user_id: str) -> int:
    """Mark all unread notifications for *user_id* as read. Returns count updated."""
    db = get_database()
    result = await db.notifications.update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True}},
    )
    return result.modified_count


async def count_unread(user_id: str) -> int:
    """Return the number of unread notifications for *user_id*."""
    db = get_database()
    return await db.notifications.count_documents({"user_id": user_id, "is_read": False})


async def ensure_notification_indexes() -> None:
    """Create indexes on the notifications collection (called at startup)."""
    db = get_database()
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
