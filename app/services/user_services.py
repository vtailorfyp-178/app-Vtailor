from app.db.mongodb import get_database
from datetime import datetime
from bson import ObjectId


async def get_user_by_email(email: str, role: str | None = None):
    """Get user by email address, optionally scoped to a role."""
    db = get_database()
    query = {"email": email}
    if role:
        query["role"] = role
    user = await db.users.find_one(query)
    return user


async def get_user_by_phone(phone: str):
    """Get user by phone number (E.164)."""
    db = get_database()
    user = await db.users.find_one({"phone": phone})
    return user


async def get_user_by_id(user_id: str):
    """Get user by user ID."""
    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        return user
    except:
        return None


async def create_user(email: str | None = None, role: str = "customer", phone: str | None = None):
    """
    Create a new user in the database.
    Either email or phone must be provided.
    """
    db = get_database()
    user_data = {
        "email": email,
        "phone": phone,
        "role": role,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    # Remove None fields to avoid storing them
    user_data = {k: v for k, v in user_data.items() if v is not None}
    result = await db.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    return user_data


async def update_user(user_id: str, update_data: dict):
    """Update user information."""
    db = get_database()
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            return None
        return await get_user_by_id(user_id)
    except:
        return None


def user_to_profile(user: dict | None):
    if not user:
        return None
    return {
        "user_id": str(user.get("_id")),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "name": user.get("name"),
        "address": user.get("address"),
        "experience": user.get("experience"),
        "specialization": user.get("specialization"),
        "description": user.get("description"),
        "avatar": user.get("avatar"),
        "role": user.get("role", "customer"),
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at"),
    }


async def delete_user(user_id: str):
    """Delete a user."""
    db = get_database()
    try:
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    except:
        return False


async def list_all_users(skip: int = 0, limit: int = 10):
    """Get all users with pagination."""
    db = get_database()
    users = await db.users.find().skip(skip).limit(limit).to_list(length=limit)
    total = await db.users.count_documents({})
    return {"users": users, "total": total}
