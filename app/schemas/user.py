from pydantic import EmailStr
from typing import Optional, List
from pydantic import BaseModel


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