from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None  # E.164 format, e.g., "+15551234567"
    role: str = "customer"


class UserInDB(UserCreate):
    id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = None
    
    class Config:
        populate_by_name = True


class UserLogin(BaseModel):
    """User login with Stytch token"""
    token: str


class CurrentUser(BaseModel):
    """Current authenticated user information"""
    user_id: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
