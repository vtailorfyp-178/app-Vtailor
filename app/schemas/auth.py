from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfile(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    code: Optional[str] = None
