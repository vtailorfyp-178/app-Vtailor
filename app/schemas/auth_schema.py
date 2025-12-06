from pydantic import BaseModel
from typing import Optional

class AuthRequestSchema(BaseModel):
    email: str
    password: str

class AuthResponseSchema(BaseModel):
    access_token: str
    token_type: str

class TokenSchema(BaseModel):
    access_token: str
    token_type: str
    expires_in: Optional[int] = None

class RefreshTokenSchema(BaseModel):
    refresh_token: str

class AuthErrorSchema(BaseModel):
    detail: str

class LoginSchema(BaseModel):
    email: str
    password: str

# optional: other schemas
class RegisterSchema(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None