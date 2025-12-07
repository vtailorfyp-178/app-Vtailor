from fastapi import HTTPException, status
from app.schemas.auth_schema import (
    MagicLinkRequestSchema,
    MagicLinkVerifySchema,
)
from app.db.collections import get_users_collection
from app.core.stytch_client import (
    send_magic_link,
    authenticate_magic_link,
    verify_session,
    revoke_session
)
from app.models.user_model import User
from datetime import datetime

class AuthService:
    
    @staticmethod
    async def request_magic_link(payload: MagicLinkRequestSchema) -> dict:
        """Request passwordless magic link"""
        users_collection = await get_users_collection()
        
        # Check if user exists
        user = await users_collection.find_one({"email": payload.email})
        
        # Send magic link via Stytch
        result = await send_magic_link(payload.email, payload.redirect_url)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # If user doesn't exist, create placeholder
        if not user:
            new_user = User(email=payload.email)
            await users_collection.insert_one(new_user.to_dict())
        
        return {
            "success": True,
            "message": "Magic link sent to email",
            "email": payload.email
        }

    @staticmethod
    async def verify_magic_link(payload: MagicLinkVerifySchema) -> dict:
        """Verify magic link token"""
        users_collection = await get_users_collection()
        
        # Verify token with Stytch
        result = await authenticate_magic_link(payload.token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["error"]
            )
        
        user_id = result.get("user_id")
        email = result.get("email")
        session_token = result.get("session_token")
        
        # Update or create user
        user = await users_collection.find_one({"email": email})
        if user:
            await users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "stytch_user_id": user_id,
                        "is_active": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            user_mongo_id = str(user["_id"])
        else:
            new_user = User(email=email, stytch_user_id=user_id)
            inserted = await users_collection.insert_one(new_user.to_dict())
            user_mongo_id = str(inserted.inserted_id)
        
        return {
            "success": True,
            "user_id": user_mongo_id,
            "email": email,
            "session_token": session_token,
            "message": "Magic link verified"
        }

    @staticmethod
    async def get_current_user(session_token: str) -> dict:
        """Get current user from session token"""
        users_collection = await get_users_collection()
        
        # Verify session with Stytch
        result = await verify_session(session_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )
        
        user_id = result.get("user_id")
        
        # Get user from database
        user = await users_collection.find_one({"stytch_user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user

    @staticmethod
    async def logout(session_token: str) -> dict:
        """Logout user"""
        result = await revoke_session(session_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return {"success": True, "message": "Logged out"}