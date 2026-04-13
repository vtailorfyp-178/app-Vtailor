from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class UserUpdate(BaseModel):
    """Fields allowed when updating a user profile via PUT /users/{user_id}"""
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    experience: Optional[str] = None
    specialization: Optional[List[str]] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None        # Only admins can change this
    is_active: Optional[bool] = None  # Only admins can change this

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "name": "Ali Khan",
                "phone": "+92 300 1234567",
                "address": "Lahore, Pakistan",
                "experience": "5",
                "specialization": ["Formal Dresses", "Alterations"],
                "description": "Expert in wedding and formal wear.",
                "avatar": "https://example.com/avatar.jpg",
                "role": "tailor",
                "is_active": True
            }
        }


class TailorLocationPoint(BaseModel):
    latitude: float
    longitude: float


class TailorAvailabilityUpdate(BaseModel):
    is_available: bool


class TailorLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    is_available: Optional[bool] = None


class NearbyTailor(BaseModel):
    user_id: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    specialization: List[str] = []
    experience: Optional[str] = None
    rating: float
    review_count: int
    price_from: int
    price_to: int
    is_available: bool
    location: TailorLocationPoint
    distance_km: float
    last_location_at: Optional[datetime] = None


class NearbyTailorsResponse(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    count: int
    results: List[NearbyTailor]