import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.routers.users import get_current_active_user
from app.schemas.user import NearbyTailorsResponse, TailorAvailabilityUpdate, TailorLocationUpdate
from app.services.user_services import get_user_by_id, user_to_profile

log = logging.getLogger(__name__)

COL_TAILOR_PROFILES = "tailor_profiles"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _geo_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def _profile_from_user(user: dict, profile_doc: dict | None = None) -> dict:
    profile = user_to_profile(user) or {}
    merged = dict(profile_doc or {})
    merged.setdefault("tailor_id", profile.get("user_id"))
    merged.setdefault("name", profile.get("name") or "Tailor")
    merged.setdefault("shop_name", profile.get("name") or "Tailor Shop")
    merged.setdefault("bio", profile.get("description"))
    merged.setdefault("address", profile.get("address"))
    merged.setdefault("specialties", profile.get("specialization") or [])
    merged.setdefault("price_range", None)
    merged.setdefault("phone", profile.get("phone"))
    merged.setdefault("avatar_url", profile.get("avatar"))
    merged.setdefault("cover_url", None)
    merged.setdefault("working_hours", None)
    merged.setdefault("rating", _as_float(merged.get("rating"), 4.5))
    merged.setdefault("review_count", int(merged.get("review_count") or 0))
    merged.setdefault("is_available", bool(merged.get("is_available", True)))
    merged.setdefault("is_verified", bool(merged.get("is_verified", False)))
    return merged


async def ensure_tailor_map_indexes(db: Any) -> None:
    """Create indexes for the tailor map collection."""
    try:
        await db[COL_TAILOR_PROFILES].create_index([("location", "2dsphere")])
        await db[COL_TAILOR_PROFILES].create_index([("tailor_id", 1)], unique=True)
        await db[COL_TAILOR_PROFILES].create_index([("is_available", 1)])
        await db[COL_TAILOR_PROFILES].create_index([("rating", -1)])
        await db[COL_TAILOR_PROFILES].create_index(
            [("shop_name", "text"), ("specialties", "text"), ("bio", "text"), ("name", "text")],
            name="tailor_text_search",
        )
    except Exception as exc:
        log.warning("Tailor map index setup skipped: %s", exc)


def create_tailor_map_router(db: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/location")
    async def update_location(
        body: TailorLocationUpdate,
        current_user: dict = Depends(get_current_active_user),
    ) -> dict:
        if current_user.get("role") != "tailor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tailor accounts can update location.")

        tailors = db[COL_TAILOR_PROFILES]
        user_id = str(current_user.get("_id"))
        user_doc = await get_user_by_id(user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="Tailor user not found.")

        existing = await tailors.find_one({"tailor_id": user_id})
        profile = _profile_from_user(user_doc, existing)
        now = _now()

        await tailors.update_one(
            {"tailor_id": user_id},
            {
                "$set": {
                    "tailor_id": user_id,
                    "name": profile.get("name"),
                    "shop_name": profile.get("shop_name"),
                    "bio": profile.get("bio"),
                    "address": profile.get("address"),
                    "specialties": profile.get("specialties") or [],
                    "price_range": profile.get("price_range"),
                    "phone": profile.get("phone"),
                    "avatar_url": profile.get("avatar_url"),
                    "cover_url": profile.get("cover_url"),
                    "working_hours": profile.get("working_hours"),
                    "rating": _as_float(profile.get("rating"), 4.5),
                    "review_count": int(profile.get("review_count") or 0),
                    "is_available": body.is_available,
                    "location": {
                        "type": "Point",
                        "coordinates": [body.longitude, body.latitude],
                    },
                    "latitude": body.latitude,
                    "longitude": body.longitude,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                    "is_verified": bool(profile.get("is_verified", False)),
                },
            },
            upsert=True,
        )

        return {"updated": True}

    @router.post("/profile/map")
    async def update_map_profile(
        body: dict,
        current_user: dict = Depends(get_current_active_user),
    ) -> dict:
        if current_user.get("role") != "tailor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tailor accounts can update map profile.")

        user_id = str(current_user.get("_id"))
        existing = await db[COL_TAILOR_PROFILES].find_one({"tailor_id": user_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Tailor profile not found. Update location first to create it.")

        update_fields: dict[str, Any] = {"updated_at": _now()}
        allowed = [
            "shop_name", "bio", "address", "specialties", "price_range",
            "phone", "avatar_url", "cover_url", "working_hours", "rating", "review_count",
        ]
        for field in allowed:
            if field in body and body[field] is not None:
                update_fields[field] = body[field]

        await db[COL_TAILOR_PROFILES].update_one({"tailor_id": user_id}, {"$set": update_fields})
        return {"updated": True}

    @router.post("/availability")
    async def update_availability(
        body: TailorAvailabilityUpdate,
        current_user: dict = Depends(get_current_active_user),
    ) -> dict:
        if current_user.get("role") != "tailor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only tailor accounts can change availability.")

        user_id = str(current_user.get("_id"))
        result = await db[COL_TAILOR_PROFILES].update_one(
            {"tailor_id": user_id},
            {"$set": {"is_available": body.is_available, "updated_at": _now()}},
        )
        if result.matched_count == 0:
            user_doc = await get_user_by_id(user_id)
            if not user_doc:
                raise HTTPException(status_code=404, detail="Tailor profile not found.")
            await db[COL_TAILOR_PROFILES].insert_one(
                {
                    **_profile_from_user(user_doc),
                    "tailor_id": user_id,
                    "is_available": body.is_available,
                    "location": {"type": "Point", "coordinates": [0.0, 0.0]},
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            )

        return {"status": "success", "is_available": body.is_available}

    @router.get("/nearby", response_model=NearbyTailorsResponse)
    async def get_nearby_tailors(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
        radius_km: float = Query(10.0, ge=0.1, le=100),
        available_only: bool = Query(False),
        availability: bool | None = Query(None),
        specialty: str | None = Query(None),
        price_range: str | None = Query(None),
        price_min: int | None = Query(None, ge=0),
        price_max: int | None = Query(None, ge=0),
        min_rating: float = Query(0.0, ge=0, le=5),
        sort_by: str = Query("distance", pattern="^(distance|rating|review_count)$"),
        limit: int = Query(30, ge=1, le=100),
        q: str | None = Query(None),
    ) -> dict:
        cursor = db[COL_TAILOR_PROFILES].find({})
        docs = await cursor.to_list(length=500)

        q_lower = q.strip().lower() if q else None
        cards = []
        for doc in docs:
            coords = (doc.get("location") or {}).get("coordinates") or [doc.get("longitude", 0.0), doc.get("latitude", 0.0)]
            lng = _as_float(coords[0])
            lat = _as_float(coords[1])
            distance_km = _geo_distance_km(latitude, longitude, lat, lng)
            if distance_km > radius_km:
                continue

            is_open = bool(doc.get("is_available", False))
            desired_availability = availability if availability is not None else (True if available_only else None)
            if desired_availability is not None and is_open != desired_availability:
                continue
            if specialty:
                specialties = [str(item).lower() for item in doc.get("specialties", []) if item]
                if specialty.lower() not in specialties and specialty.lower() not in (doc.get("shop_name", "").lower() + " " + doc.get("bio", "").lower()):
                    continue
            if price_range and doc.get("price_range") != price_range:
                continue
            if price_min is not None or price_max is not None:
                profile_range = doc.get("price_range")
                if price_range:
                    pass
                elif price_min is not None and price_max is not None:
                    if price_max <= 1500:
                        expected_range = "budget"
                    elif price_min >= 3500:
                        expected_range = "premium"
                    else:
                        expected_range = "mid"
                    if profile_range and profile_range != expected_range:
                        continue
                elif price_min is not None:
                    if price_min >= 3500 and profile_range and profile_range != "premium":
                        continue
                elif price_max is not None:
                    if price_max <= 1500 and profile_range and profile_range != "budget":
                        continue
            if _as_float(doc.get("rating"), 0.0) < min_rating:
                continue
            if q_lower:
                blob = " ".join(
                    [
                        str(doc.get("shop_name", "")),
                        str(doc.get("name", "")),
                        str(doc.get("bio", "")),
                        " ".join(doc.get("specialties", []) or []),
                    ]
                ).lower()
                if q_lower not in blob:
                    continue

            cards.append(
                {
                    "user_id": doc.get("tailor_id"),
                    "name": doc.get("name") or doc.get("shop_name") or "Tailor",
                    "avatar": doc.get("avatar_url"),
                    "specialization": doc.get("specialties", []) or [],
                    "experience": doc.get("working_hours") and str(doc.get("working_hours")) or None,
                    "rating": _as_float(doc.get("rating"), 0.0),
                    "review_count": int(doc.get("review_count") or 0),
                    "price_from": 1200,
                    "price_to": 2800,
                    "is_available": bool(doc.get("is_available", True)),
                    "location": {"latitude": lat, "longitude": lng},
                    "distance_km": round(distance_km, 2),
                    "last_location_at": _iso(doc.get("updated_at")),
                }
            )

        if sort_by == "rating":
            cards.sort(key=lambda item: item["rating"], reverse=True)
        elif sort_by == "review_count":
            cards.sort(key=lambda item: item["review_count"], reverse=True)
        else:
            cards.sort(key=lambda item: item["distance_km"])

        results = cards[:limit]
        return {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "count": len(results),
            "results": results,
        }

    @router.get("/search")
    async def search_tailors(
        q: str = Query(..., min_length=2),
        limit: int = Query(20, ge=1, le=50),
    ) -> list[dict]:
        cursor = db[COL_TAILOR_PROFILES].find({})
        docs = await cursor.to_list(length=500)
        q_lower = q.lower().strip()
        results = []
        for doc in docs:
            blob = " ".join(
                [
                    str(doc.get("shop_name", "")),
                    str(doc.get("name", "")),
                    str(doc.get("bio", "")),
                    " ".join(doc.get("specialties", []) or []),
                ]
            ).lower()
            if q_lower in blob:
                results.append(
                    {
                        "user_id": doc.get("tailor_id"),
                        "name": doc.get("name") or doc.get("shop_name") or "Tailor",
                        "avatar": doc.get("avatar_url"),
                        "specialization": doc.get("specialties", []) or [],
                        "experience": doc.get("working_hours") and str(doc.get("working_hours")) or None,
                        "rating": _as_float(doc.get("rating"), 0.0),
                        "review_count": int(doc.get("review_count") or 0),
                        "price_from": 1200,
                        "price_to": 2800,
                        "is_available": bool(doc.get("is_available", True)),
                        "location": {"latitude": _as_float(doc.get("latitude"), 0.0), "longitude": _as_float(doc.get("longitude"), 0.0)},
                        "distance_km": None,
                        "last_location_at": _iso(doc.get("updated_at")),
                    }
                )
            if len(results) >= limit:
                break
        return results[:limit]

    @router.get("/{tailor_id}")
    async def get_tailor_profile(tailor_id: str) -> dict:
        doc = await db[COL_TAILOR_PROFILES].find_one({"tailor_id": tailor_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Tailor profile not found.")
        return {
            "user_id": doc.get("tailor_id"),
            "name": doc.get("name") or doc.get("shop_name") or "Tailor",
            "avatar": doc.get("avatar_url"),
            "specialization": doc.get("specialties", []) or [],
            "experience": doc.get("working_hours") and str(doc.get("working_hours")) or None,
            "rating": _as_float(doc.get("rating"), 0.0),
            "review_count": int(doc.get("review_count") or 0),
            "price_from": 1200,
            "price_to": 2800,
            "is_available": bool(doc.get("is_available", True)),
            "location": {"latitude": _as_float(doc.get("latitude"), 0.0), "longitude": _as_float(doc.get("longitude"), 0.0)},
            "distance_km": None,
            "last_location_at": _iso(doc.get("updated_at")),
        }

    return router