from fastapi import APIRouter, Depends
from app.schemas.user_schema import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService
from app.dependencies.auth_dependency import get_current_user

router = APIRouter()

@router.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate):
    return await UserService.create_user(user)

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: UserResponse = Depends(get_current_user)):
    return await UserService.get_user(user_id)

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserUpdate, current_user: UserResponse = Depends(get_current_user)):
    return await UserService.update_user(user_id, user)

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: UserResponse = Depends(get_current_user)):
    await UserService.delete_user(user_id)
    return {"message": "User deleted successfully"}