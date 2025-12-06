from fastapi import APIRouter, Depends, HTTPException
from app.schemas.auth_schema import LoginSchema, RegisterSchema
from app.services.auth_service import AuthService
from app.utils.jwt_manager import create_access_token

router = APIRouter()

@router.post("/register")
async def register(user: RegisterSchema):
    user_created = await AuthService.register_user(user)
    if not user_created:
        raise HTTPException(status_code=400, detail="User registration failed")
    return {"message": "User registered successfully"}

@router.post("/login")
async def login(user: LoginSchema):
    user_data = await AuthService.authenticate_user(user)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user_data.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token/refresh")
async def refresh_token(token: str):
    new_token = await AuthService.refresh_access_token(token)
    if not new_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"access_token": new_token, "token_type": "bearer"}