from fastapi import FastAPI
from app.core.config import get_settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection, check_mongo_connection
from app.api.api import api_router

settings = get_settings()

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup():
    print("🚀 Starting VTailor Backend...")
    await connect_to_mongo()
    if await check_mongo_connection():
        print("✅ MongoDB connected")
    else:
        print("❌ MongoDB connection failed")


@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()
    print("🛑 Application shutdown")


@app.get("/")
async def root():
    return {"status": "VTailor Backend running"}
