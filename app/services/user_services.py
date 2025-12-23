from app.db.mongodb import get_database

async def get_user_by_email(email: str):
    db = get_database()
    return await db.users.find_one({"email": email})

async def create_user(email: str, role: str = "customer"):
    db = get_database()
    user = {
        "email": email,
        "role": role,
        "is_active": True
    }
    result = await db.users.insert_one(user)
    user["_id"] = str(result.inserted_id)
    return user
