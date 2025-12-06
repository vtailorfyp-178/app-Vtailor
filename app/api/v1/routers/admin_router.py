from fastapi import APIRouter, Depends
from app.dependencies.auth_dependency import get_current_user
from app.services.user_service import UserService

router = APIRouter()

@router.get("/users")
async def get_users(current_user: str = Depends(get_current_user)):
    return await UserService.get_all_users()

@router.get("/users/{user_id}")
async def get_user(user_id: str, current_user: str = Depends(get_current_user)):
    return await UserService.get_user_by_id(user_id)

@router.post("/users")
async def create_user(user_data: dict, current_user: str = Depends(get_current_user)):
    return await UserService.create_user(user_data)

@router.put("/users/{user_id}")
async def update_user(user_id: str, user_data: dict, current_user: str = Depends(get_current_user)):
    return await UserService.update_user(user_id, user_data)

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: str = Depends(get_current_user)):
    return await UserService.delete_user(user_id)