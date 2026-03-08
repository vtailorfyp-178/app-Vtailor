from fastapi import APIRouter, HTTPException, status, Depends
from app.api.v1.routers.auth import get_current_user   # Single source of truth for auth
from app.schemas.auth import UserProfile, ErrorResponse
from app.schemas.user import UserUpdate                 # Update request schema (see below)
from app.services.user_services import (
    get_user_by_id,
    update_user,
    delete_user,
    list_all_users,
)

router = APIRouter(prefix="/users", tags=["Users"])


# ─────────────────────────────────────────────
# HELPER DEPENDENCY: require active user
# Rejects deactivated accounts even if JWT is valid
# ─────────────────────────────────────────────
async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )
    return current_user


# ─────────────────────────────────────────────
# HELPER DEPENDENCY: require a specific role
# Usage: Depends(require_role("admin"))
# ─────────────────────────────────────────────
def require_role(role: str):
    async def _require_role(current_user: dict = Depends(get_current_active_user)):
        if current_user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to {role} accounts only.",
            )
        return current_user
    return _require_role


# ─────────────────────────────────────────────
# GET /users/orders
# Get orders for currently logged-in user
# ─────────────────────────────────────────────
@router.get("/orders")
async def get_orders(current_user: dict = Depends(get_current_active_user)):
    """
    Get orders for the currently authenticated user.
    Requires: Authorization: Bearer <token>
    """
    user_id = str(current_user.get("_id"))
    # TODO: fetch orders from your orders collection using user_id
    return {"user_id": user_id, "orders": []}


# ─────────────────────────────────────────────
# GET /users/me
# Get current logged-in user's own profile
# ─────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfile,
    responses={
        200: {"description": "Current user profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get current user's profile",
)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get the profile of the currently authenticated user.
    Requires: Authorization: Bearer <token>
    """
    return UserProfile(
        user_id=str(current_user.get("_id")),
        email=current_user.get("email"),
        phone=current_user.get("phone"),
        role=current_user.get("role", "customer"),
        is_active=current_user.get("is_active", True),
        created_at=current_user.get("created_at"),
    )


# ─────────────────────────────────────────────
# GET /users/{user_id}
# Get any user's profile (own profile or admin only)
# ─────────────────────────────────────────────
@router.get(
    "/{user_id}",
    response_model=UserProfile,
    responses={
        200: {"description": "User profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Get a user profile by ID",
)
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get a user's profile by ID.
    - Regular users can only view their own profile.
    - Admins can view any profile.
    """
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this user's profile.",
        )

    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return UserProfile(
        user_id=str(user.get("_id")),
        email=user.get("email"),
        phone=user.get("phone"),
        role=user.get("role", "customer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


# ─────────────────────────────────────────────
# PUT /users/{user_id}
# Update a user's profile
# ─────────────────────────────────────────────
@router.put(
    "/{user_id}",
    response_model=UserProfile,
    responses={
        200: {"description": "User updated successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Update a user's profile",
)
async def update_user_profile(
    user_id: str,
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Update a user's profile.
    - Regular users can only update their own profile (cannot change role).
    - Admins can update any profile including role.
    """
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this user's profile.",
        )

    # Build update dict — only include fields that were actually provided
    update_dict = {}
    if update_data.email is not None:
        update_dict["email"] = update_data.email
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active

    # Only admins can change role
    if update_data.role is not None:
        if current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user roles.",
            )
        update_dict["role"] = update_data.role

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for update.",
        )

    user = await update_user(user_id, update_dict)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return UserProfile(
        user_id=str(user.get("_id")),
        email=user.get("email"),
        phone=user.get("phone"),
        role=user.get("role", "customer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


# ─────────────────────────────────────────────
# DELETE /users/{user_id}
# Delete a user account
# ─────────────────────────────────────────────
@router.delete(
    "/{user_id}",
    responses={
        200: {"description": "User deleted successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Delete a user account",
)
async def delete_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Delete a user account.
    - Regular users can only delete their own account.
    - Admins can delete any account.
    """
    if current_user.get("role") != "admin" and str(current_user.get("_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this user.",
        )

    success = await delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return {
        "status": "success",
        "message": "User deleted successfully",
        "user_id": user_id,
    }


# ─────────────────────────────────────────────
# GET /users
# List all users — Admin only
# ─────────────────────────────────────────────
@router.get(
    "",
    responses={
        200: {"description": "List of users (admin only)"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
    },
    summary="List all users (admin only)",
)
async def list_users(
    skip: int = 0,
    limit: int = 10,
    current_user: dict = Depends(require_role("admin")),
):
    """
    Get a paginated list of all users. Admin only.
    - **skip**: Number of users to skip (default 0)
    - **limit**: Max users to return (default 10, capped at 100)
    """
    limit = min(limit, 100)  # Cap at 100

    result = await list_all_users(skip=skip, limit=limit)

    users = [
        UserProfile(
            user_id=str(u.get("_id")),
            email=u.get("email"),
            phone=u.get("phone"),
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
        "limit": limit,
    }