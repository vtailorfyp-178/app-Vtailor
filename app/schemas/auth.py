from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# REQUEST SCHEMAS (what frontend sends)
# ─────────────────────────────────────────────

class EmailOTPStartRequest(BaseModel):
    """Step 1: Frontend sends email to receive OTP"""
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {"email": "user@example.com"}
        }


class EmailOTPVerifyRequest(BaseModel):
    """Step 2: Frontend sends method_id + OTP code to verify"""
    method_id: str   # Returned from /otp/start
    code: str        # 6-digit OTP from email

    class Config:
        json_schema_extra = {
            "example": {
                "method_id": "email-test-d5a3b580-e538-4e05-9e87-cbf857e82f6f",
                "code": "123456"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Refresh token endpoint: send current JWT to get a new one"""
    token: str

    class Config:
        json_schema_extra = {
            "example": {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }


# ─────────────────────────────────────────────
# RESPONSE SCHEMAS (what backend returns)
# ─────────────────────────────────────────────

class EmailOTPStartResponse(BaseModel):
    """Response after sending OTP email"""
    status: str       # "success"
    message: str      # Human-readable e.g. "OTP sent to user@example.com"
    method_id: str    # IMPORTANT: frontend must store this for verify step
    email: str        # Echo back the email for confirmation

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "OTP sent to user@example.com",
                "method_id": "email-test-d5a3b580-e538-4e05-9e87-cbf857e82f6f",
                "email": "user@example.com"
            }
        }


class TokenResponse(BaseModel):
    """Response after successful OTP verification or token refresh"""
    access_token: str          # JWT — frontend stores and sends in every request
    token_type: str = "bearer" # Always "bearer"
    user_id: str               # MongoDB _id as string
    email: Optional[str] = None
    phone: Optional[str] = None  # May be None for email-only users

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user_id": "64f1a2b3c4d5e6f7a8b9c0d1",
                "email": "user@example.com",
                "phone": None
            }
        }


class UserProfile(BaseModel):
    """User profile returned by GET /auth/me"""
    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "customer"
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "64f1a2b3c4d5e6f7a8b9c0d1",
                "email": "user@example.com",
                "phone": None,
                "role": "customer",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str

    class Config:
        json_schema_extra = {
            "example": {"detail": "OTP verification failed: invalid code"}
        }
