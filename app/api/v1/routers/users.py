from fastapi import APIRouter, HTTPException, status, Depends
from app.api.v1.dependencies.auth import get_current_active_user, require_role, get_current_user
from app.schemas.auth import UserProfile, UserUpdate, UserResponse, ErrorResponse
from app.services.user_services import (
    get_user_by_id,
    update_user,
    delete_user,
    list_all_users
)
from bson import ObjectId

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfile,
    responses={
        200: {"description": "Current user profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
async def get_current_user_profile(current_user: dict = Depends(get_current_active_user)):
    """
    Get the current authenticated user's profile.
    """
    user_data = current_user
    return UserProfile(
        id=str(user_data.get("_id")),
        email=user_data.get("email"),
        role=user_data.get("role", "customer"),
        is_active=user_data.get("is_active", True),
        created_at=user_data.get("created_at"),
    )


@router.get(
    "/{user_id}",
    response_model=UserProfile,
    responses={
        200: {"description": "User profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "User not found"}
    }
)
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get a user's profile by ID.
    
    - **user_id**: The user's ID
    """
    # Users can only see their own profile unless they are admin
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this user's profile",
        )
    
    user = await get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserProfile(
        id=str(user.get("_id")),
        email=user.get("email"),
        role=user.get("role", "customer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


@router.put(
    "/{user_id}",
    response_model=UserProfile,
    responses={
        200: {"description": "User updated successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "User not found"}
    }
)
async def update_user_profile(
    user_id: str,
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update a user's profile.
    
    - **user_id**: The user's ID
    - **update_data**: Fields to update (email, role, is_active)
    """
    # Users can only update their own profile unless they are admin
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this user's profile",
        )
    
    # Prepare update data
    update_dict = {}
    if update_data.email:
        update_dict["email"] = update_data.email
    if update_data.role:
        update_dict["role"] = update_data.role
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active
    
    # Admins can change role, regular users cannot
    if update_dict.get("role") and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles",
        )
    
    user = await update_user(user_id, update_dict)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserProfile(
        id=str(user.get("_id")),
        email=user.get("email"),
        role=user.get("role", "customer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


@router.delete(
    "/{user_id}",
    responses={
        200: {"description": "User deleted successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "User not found"}
    }
)
async def delete_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete a user account.
    
    - **user_id**: The user's ID to delete
    """
    # Users can only delete their own account unless they are admin
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this user",
        )
    
    success = await delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return {
        "status": "success",
        "message": "User deleted successfully",
        "user_id": user_id
    }


@router.get(
    "",
    responses={
        200: {"description": "List of users (admin only)"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"}
    }
)
async def list_users(
    skip: int = 0,
    limit: int = 10,
    current_user: dict = Depends(require_role("admin"))
):
    """
    Get a list of all users (Admin only).
    
    - **skip**: Number of users to skip (default 0)
    - **limit**: Number of users to return (default 10, max 100)
    """
    if limit > 100:
        limit = 100
    
    result = await list_all_users(skip=skip, limit=limit)
    
    users = [
        UserProfile(
            id=str(u.get("_id")),
            email=u.get("email"),
            role=u.get("role", "customer"),
            is_active=u.get("is_active", True),
            created_at=u.get("created_at"),
        )
        for u in result["users"]
    ]
    
    return {
        "users": users,
        "total": result["total"],
        "skip": skip,
        "limit": limit
    }
