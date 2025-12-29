from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # allow frontend to make requests to backend APIs hosted on different origin without blocking
from fastapi.middleware.trustedhost import TrustedHostMiddleware  #for security, to ensure requstes sent to trusted hosts only
from app.core.config import get_settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection, check_mongo_connection
from app.api.api import api_router

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="VTailor Backend API with Authentication and Security",
    version="1.0.0"
)

# CORS middleware - MUST be added BEFORE TrustedHostMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local testing (file:// protocol)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware - Trust only specific hosts (commented out for local file:// testing)
# Uncomment this in production with proper host configuration
# app.add_middleware(
#     TrustedHostMiddleware,
#     allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
# )

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
    return {
        "status": "VTailor Backend running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "VTailor Backend"
    }
