"""Minimal admin API — stats, orders overview, user moderation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.v1.routers.users import require_role
from app.db.mongodb import get_database
from app.api.v1.routers.orders import _serialize, _out, OrderOut
from app.schemas.auth import UserProfile
from app.services.user_services import user_to_profile

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def admin_stats(_admin: dict = Depends(require_role("admin"))):
    db = get_database()
    orders = db.orders
    users = db.users
    return {
        "users_total": await users.count_documents({}),
        "customers": await users.count_documents({"role": "customer"}),
        "tailors": await users.count_documents({"role": "tailor"}),
        "admins": await users.count_documents({"role": "admin"}),
        "users_inactive": await users.count_documents({"is_active": False}),
        "orders_total": await orders.count_documents({}),
        "orders_pending": await orders.count_documents({"status": "pending"}),
        "orders_confirmed": await orders.count_documents({"status": "confirmed"}),
        "orders_declined": await orders.count_documents({"status": "declined"}),
    }


@router.get("/users")
async def admin_list_users(
    skip: int = 0,
    limit: int = Query(50, le=100),
    role: str | None = None,
    _admin: dict = Depends(require_role("admin")),
):
    db = get_database()
    query = {}
    if role:
        query["role"] = role.strip().lower()
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    total = await db.users.count_documents(query)
    return {
        "users": [UserProfile(**user_to_profile(u)) for u in docs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/orders", response_model=list[OrderOut])
async def admin_list_orders(
    skip: int = 0,
    limit: int = Query(50, le=100),
    status: str | None = None,
    _admin: dict = Depends(require_role("admin")),
):
    db = get_database()
    query = {}
    if status:
        query["status"] = status.strip().lower()
    cursor = db.orders.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    out: list[OrderOut] = []
    for d in docs:
        doc = dict(d)
        out.append(_out(_serialize(doc)))
    return out
