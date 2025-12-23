from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    token: str   # Stytch token (passwordless)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
