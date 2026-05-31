"""
Orders Router
─────────────
Handles order-request lifecycle between customer and tailor.

Order document schema:
  _id             : ObjectId
  customer_id     : str
  tailor_id       : str
  customer_name   : str   (denormalized for tailor's inbox)
  tailor_name     : str   (denormalized for customer's view)
  description     : str   (what to stitch)
  budget          : float (customer's proposed budget)
  status          : 'pending' | 'accepted' | 'declined' | 'negotiating'
  proposed_price  : float | None   (tailor fills on accept)
  delivery_days   : int   | None   (tailor fills on accept)
  note            : str   | None   (tailor's note on accept/decline)
  created_at      : datetime
  updated_at      : datetime
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.routers.auth import get_current_user
from app.db.mongodb import get_database
from app.services.notification_service import create_notification

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _ensure_indexes() -> None:
    db = get_database()
    await db.orders.create_index([("customer_id", 1), ("created_at", -1)])
    await db.orders.create_index([("tailor_id",   1), ("created_at", -1)])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    tailor_id:   str
    tailor_name: str
    description: str = Field(..., min_length=3)
    budget:      float = Field(..., gt=0)


class AcceptOrderRequest(BaseModel):
    proposed_price: float = Field(..., gt=0)
    delivery_days:  int   = Field(..., gt=0)
    note:           str | None = None


class DeclineOrderRequest(BaseModel):
    note: str | None = None


class OrderOut(BaseModel):
    id:             str
    customer_id:    str
    tailor_id:      str
    customer_name:  str
    tailor_name:    str
    description:    str
    budget:         float
    status:         str
    proposed_price: float | None
    delivery_days:  int | None
    note:           str | None
    created_at:     str
    updated_at:     str


def _out(doc: dict) -> OrderOut:
    def iso(dt):
        return dt.isoformat() if hasattr(dt, "isoformat") else str(dt or "")

    return OrderOut(
        id=doc["id"],
        customer_id=doc["customer_id"],
        tailor_id=doc["tailor_id"],
        customer_name=doc.get("customer_name", ""),
        tailor_name=doc.get("tailor_name", ""),
        description=doc["description"],
        budget=doc["budget"],
        status=doc["status"],
        proposed_price=doc.get("proposed_price"),
        delivery_days=doc.get("delivery_days"),
        note=doc.get("note"),
        created_at=iso(doc.get("created_at")),
        updated_at=iso(doc.get("updated_at")),
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Customer places a new order request to a tailor."""
    customer_id   = str(current_user.get("_id"))
    customer_name = current_user.get("name") or current_user.get("email") or "Customer"

    db = get_database()
    doc = {
        "customer_id":    customer_id,
        "tailor_id":      body.tailor_id,
        "customer_name":  customer_name,
        "tailor_name":    body.tailor_name,
        "description":    body.description,
        "budget":         body.budget,
        "status":         "pending",
        "proposed_price": None,
        "delivery_days":  None,
        "note":           None,
        "created_at":     _now(),
        "updated_at":     _now(),
    }
    result = await db.orders.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Notify the tailor
    try:
        await create_notification(
            user_id=body.tailor_id,
            type="order_requested",
            title="New Order Request",
            message=f"{customer_name} sent a request for '{body.description}'",
            data={
                "orderId":       str(result.inserted_id),
                "customerId":    customer_id,
                "customerName":  customer_name,
                "description":   body.description,
                "budget":        body.budget,
            },
        )
    except Exception:
        pass

    return _out(_serialize(doc))


@router.get("", response_model=list[OrderOut])
async def list_orders(current_user: dict = Depends(get_current_user)):
    """
    Returns orders for the current user.
    - customer  → orders they placed
    - tailor    → orders sent to them
    """
    user_id = str(current_user.get("_id"))
    role    = current_user.get("role", "customer")
    db      = get_database()

    field = "tailor_id" if role == "tailor" else "customer_id"
    cursor = db.orders.find({field: user_id}, sort=[("created_at", -1)], limit=100)
    docs   = await cursor.to_list(length=100)
    return [_out(_serialize(d)) for d in docs]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fetch a single order (must belong to current user as customer or tailor)."""
    user_id = str(current_user.get("_id"))
    db      = get_database()
    try:
        doc = await db.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(doc["customer_id"]) != user_id and str(doc["tailor_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _out(_serialize(doc))


@router.patch("/{order_id}/accept", response_model=OrderOut)
async def accept_order(
    order_id: str,
    body: AcceptOrderRequest,
    current_user: dict = Depends(get_current_user),
):
    """Tailor accepts an order and proposes price + delivery days."""
    user_id = str(current_user.get("_id"))
    db      = get_database()
    try:
        doc = await db.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(doc["tailor_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Only the tailor can accept this order")
    if doc["status"] != "pending":
        raise HTTPException(status_code=400, detail="Order is not pending")

    update = {
        "status":         "accepted",
        "proposed_price": body.proposed_price,
        "delivery_days":  body.delivery_days,
        "note":           body.note,
        "updated_at":     _now(),
    }
    await db.orders.update_one({"_id": ObjectId(order_id)}, {"$set": update})

    tailor_name = current_user.get("name") or current_user.get("email") or "Tailor"
    try:
        await create_notification(
            user_id=str(doc["customer_id"]),
            type="order_accepted",
            title="Order Accepted!",
            message=(
                f"{tailor_name} accepted your '{doc['description']}' request. "
                f"Proposed price: Rs. {body.proposed_price:,.0f}, "
                f"Delivery: {body.delivery_days} day(s)."
            ),
            data={
                "orderId":       order_id,
                "tailorId":      user_id,
                "tailorName":    tailor_name,
                "proposedPrice": body.proposed_price,
                "deliveryDays":  body.delivery_days,
            },
        )
    except Exception:
        pass

    doc.update(update)
    doc["_id"] = ObjectId(order_id)
    return _out(_serialize(doc))


@router.patch("/{order_id}/decline", response_model=OrderOut)
async def decline_order(
    order_id: str,
    body: DeclineOrderRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Tailor declines an order."""
    user_id = str(current_user.get("_id"))
    db      = get_database()
    try:
        doc = await db.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(doc["tailor_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Only the tailor can decline this order")
    if doc["status"] != "pending":
        raise HTTPException(status_code=400, detail="Order is not pending")

    note   = (body.note if body else None) or ""
    update = {"status": "declined", "note": note, "updated_at": _now()}
    await db.orders.update_one({"_id": ObjectId(order_id)}, {"$set": update})

    tailor_name = current_user.get("name") or current_user.get("email") or "Tailor"
    try:
        await create_notification(
            user_id=str(doc["customer_id"]),
            type="order_declined",
            title="Order Declined",
            message=f"{tailor_name} could not accept your '{doc['description']}' request."
            + (f" Reason: {note}" if note else ""),
            data={"orderId": order_id, "tailorId": user_id, "tailorName": tailor_name},
        )
    except Exception:
        pass

    doc.update(update)
    doc["_id"] = ObjectId(order_id)
    return _out(_serialize(doc))
