from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth_schema import (
    MagicLinkRequestSchema,
    MagicLinkVerifySchema,
    LogoutSchema
)
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()

@router.post("/request-magic-link")
async def request_magic_link(payload: MagicLinkRequestSchema):
    """Send magic link to email"""
    return await AuthService.request_magic_link(payload)

@router.post("/verify-magic-link")
async def verify_magic_link(payload: MagicLinkVerifySchema):
    """Verify magic link token"""
    return await AuthService.verify_magic_link(payload)

@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user"""
    user = await AuthService.get_current_user(credentials.credentials)
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "phone": user.get("phone", ""),
        "role": user.get("role", "customer"),
        "is_active": user.get("is_active", True)
    }

@router.post("/logout")
async def logout(payload: LogoutSchema):
    """Logout user"""
    return await AuthService.logout(payload.session_token)