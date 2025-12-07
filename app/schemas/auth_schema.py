from pydantic import BaseModel
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    CUSTOMER = "customer"
    TAILOR = "tailor"
    ADMIN = "admin"

class MagicLinkRequestSchema(BaseModel):
    """Request passwordless magic link"""
    email: str
    redirect_url: str = "http://localhost:3000/auth/verify"

class MagicLinkVerifySchema(BaseModel):
    """Verify magic link token"""
    token: str

class UserResponseSchema(BaseModel):
    """User info response"""
    id: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "customer"
    is_active: bool = True

    class Config:
        from_attributes = True

class LogoutSchema(BaseModel):
    """Logout request"""
    session_token: str