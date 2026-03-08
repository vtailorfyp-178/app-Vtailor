from pydantic import EmailStr
from typing import Optional
from pydantic import BaseModel


class UserUpdate(BaseModel):
    """Fields allowed when updating a user profile via PUT /users/{user_id}"""
    email: Optional[EmailStr] = None
    role: Optional[str] = None        # Only admins can change this
    is_active: Optional[bool] = None  # Only admins can change this

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "role": "tailor",
                "is_active": True
            }
        }