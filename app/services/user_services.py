from app.db.mongodb import get_database
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from bson import ObjectId


async def get_user_by_email(email: str, role: str | None = None):
    """Get user by email address, optionally scoped to a role."""
    db = get_database()
    query = {"email": email}
    if role:
        query["role"] = role
    user = await db.users.find_one(query)
    return user


async def get_user_by_phone(phone: str):
    """Get user by phone number (E.164)."""
    db = get_database()
    user = await db.users.find_one({"phone": phone})
    return user


async def get_user_by_id(user_id: str):
    """Get user by user ID."""
    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        return user
    except:
        return None


async def create_user(email: str | None = None, role: str = "customer", phone: str | None = None):
    """
    Create a new user in the database.
    Either email or phone must be provided.
    """
    db = get_database()
    user_data = {
        "email": email,
        "phone": phone,
        "role": role,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    # Remove None fields to avoid storing them
    user_data = {k: v for k, v in user_data.items() if v is not None}
    result = await db.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    return user_data


async def update_user(user_id: str, update_data: dict):
    """Update user information."""
    db = get_database()
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            return None
        return await get_user_by_id(user_id)
    except:
        return None


def user_to_profile(user: dict | None):
    if not user:
        return None
    return {
        "user_id": str(user.get("_id")),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "name": user.get("name"),
        "address": user.get("address"),
        "experience": user.get("experience"),
        "specialization": user.get("specialization"),
        "description": user.get("description"),
        "avatar": user.get("avatar"),
        "role": user.get("role", "customer"),
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at"),
    }


async def delete_user(user_id: str):
    """Delete a user."""
    db = get_database()
    try:
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    except:
        return False


async def list_all_users(skip: int = 0, limit: int = 10):
    """Get all users with pagination."""
    db = get_database()
    users = await db.users.find().skip(skip).limit(limit).to_list(length=limit)
    total = await db.users.count_documents({})
    return {"users": users, "total": total}


async def search_users(
    query: str = "",
    role: str | None = None,
    exclude_user_id: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """
    Search users by name or email (case-insensitive substring).
    Optionally filter by role and exclude the requesting user.
    Returns a lightweight list for profile discovery / new-chat flow.
    """
    db = get_database()
    mongo_filter: dict = {"is_active": True}

    if role:
        mongo_filter["role"] = role

    if query.strip():
        q = query.strip()
        mongo_filter["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]

    users = await db.users.find(mongo_filter).limit(limit * 2).to_list(length=limit * 2)

    results = []
    for u in users:
        uid = str(u.get("_id"))
        if exclude_user_id and uid == exclude_user_id:
            continue
        results.append({
            "user_id": uid,
            "name": u.get("name") or "",
            "email": u.get("email") or "",
            "phone": u.get("phone") or "",
            "role": u.get("role", "customer"),
            "avatar": u.get("avatar"),
            "specialization": u.get("specialization") or [],
            "experience": u.get("experience") or "",
            "is_available": bool(u.get("is_available", False)),
        })
        if len(results) >= limit:
            break

    return results


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two geo points in kilometers."""
    r = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _extract_coordinates(user: dict) -> tuple[float | None, float | None]:
    location = user.get("location") or {}
    lat = _safe_float(location.get("latitude"), None)
    lng = _safe_float(location.get("longitude"), None)
    if lat is not None and lng is not None:
        return lat, lng

    lat = _safe_float(user.get("latitude"), None)
    lng = _safe_float(user.get("longitude"), None)
    return lat, lng


async def update_tailor_location(user_id: str, latitude: float, longitude: float, is_available: bool | None = None):
    db = get_database()
    update_doc = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
        "last_location_at": datetime.utcnow(),
    }
    if is_available is not None:
        update_doc["is_available"] = bool(is_available)

    return await update_user(user_id, update_doc)


async def update_tailor_availability(user_id: str, is_available: bool):
    return await update_user(
        user_id,
        {
            "is_available": bool(is_available),
            "availability_updated_at": datetime.utcnow(),
        },
    )


async def get_nearby_tailors(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    specialty: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    min_rating: float | None = None,
    availability: bool | None = None,
    query_text: str | None = None,
    sort_by: str = "distance",
    limit: int = 100,
):
    db = get_database()
    tailors = await db.users.find({"role": "tailor", "is_active": True}).to_list(length=max(limit * 3, 200))

    specialty_filter = (specialty or "").strip().lower()
    text_filter = (query_text or "").strip().lower()
    items: list[dict] = []

    for user in tailors:
        lat, lng = _extract_coordinates(user)
        if lat is None or lng is None:
            continue

        distance_km = _haversine_km(latitude, longitude, lat, lng)
        if distance_km > radius_km:
            continue

        specializations = user.get("specialization") or []
        spec_lower = [str(s).strip().lower() for s in specializations if s]

        if specialty_filter and specialty_filter != "all":
            if not any(specialty_filter in s for s in spec_lower):
                continue

        name = (user.get("name") or "").strip()
        if text_filter:
            in_name = text_filter in name.lower()
            in_specializations = any(text_filter in s for s in spec_lower)
            if not in_name and not in_specializations:
                continue

        rating = _safe_float(user.get("rating"), 4.4) or 4.4
        if min_rating is not None and rating < min_rating:
            continue

        review_count = _safe_int(user.get("review_count"), 0)
        price_from = _safe_int(user.get("price_from"), 1200)
        price_to = _safe_int(user.get("price_to"), max(price_from, 2800))

        if price_min is not None and price_to < price_min:
            continue
        if price_max is not None and price_from > price_max:
            continue

        is_available = bool(user.get("is_available", False))
        if availability is not None and is_available != availability:
            continue

        items.append(
            {
                "user_id": str(user.get("_id")),
                "name": name or "Tailor",
                "avatar": user.get("avatar"),
                "specialization": specializations,
                "experience": user.get("experience"),
                "rating": round(rating, 1),
                "review_count": review_count,
                "price_from": price_from,
                "price_to": price_to,
                "is_available": is_available,
                "location": {"latitude": lat, "longitude": lng},
                "distance_km": round(distance_km, 2),
                "last_location_at": user.get("last_location_at"),
            }
        )

    if sort_by == "rating":
        items.sort(key=lambda x: (x["rating"], x["review_count"]), reverse=True)
    elif sort_by == "reviews":
        items.sort(key=lambda x: x["review_count"], reverse=True)
    else:
        items.sort(key=lambda x: x["distance_km"])

    return items[:limit]
