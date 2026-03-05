from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


"""
Schemas for authentication. Magic link removed; using SMS OTP.
"""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None


class UserProfile(BaseModel):
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    code: Optional[str] = None


class PhoneOTPStartRequest(BaseModel):
    phone: str  # E.164 format: "+15551234567"


class PhoneOTPStartResponse(BaseModel):
    status: str
    message: str
    method_id: str
    phone: str


class PhoneOTPVerifyRequest(BaseModel):
    method_id: str
    code: str
