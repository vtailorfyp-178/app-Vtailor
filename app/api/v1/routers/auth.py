from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.core.stytch_client import stytch_client

router = APIRouter(prefix="/auth", tags=["Auth"])


class MagicLinkRequest(BaseModel):
    email: EmailStr


@router.post("/login")
async def send_magic_link(data: MagicLinkRequest):
    try:
        response = stytch_client.magic_links.email.login_or_create(
            email=data.email,
            login_magic_link_url="http://localhost:3000/auth/callback",
            signup_magic_link_url="http://localhost:3000/auth/callback",
        )
        return {
            "status": "success",
            "message": "Magic link sent",
            "request_id": response.request_id,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class MagicLinkVerifyRequest(BaseModel):
    token: str


@router.post("/verify")
async def verify_magic_link(data: MagicLinkVerifyRequest):
    try:
        response = stytch_client.magic_links.authenticate(
            token=data.token,
            session_duration_minutes=60
        )

        user_id = response.user_id
        email = response.user.emails[0].email

        return {
            "status": "success",
            "user_id": user_id,
            "email": email,
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
