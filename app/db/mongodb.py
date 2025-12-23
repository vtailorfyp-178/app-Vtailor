from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings

client: Optional[AsyncIOMotorClient] = None


async def connect_to_mongo():
    global client
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)


async def close_mongo_connection():
    global client
    if client is not None:
        client.close()


async def check_mongo_connection() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        return False


def get_database():
    settings = get_settings()
    return client[settings.MONGO_DB_NAME]
