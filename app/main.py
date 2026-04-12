from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # allow frontend to make requests to backend APIs hosted on different origin without blocking
import boto3
from app.core.config import get_settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection, check_mongo_connection
from app.api.api import api_router
from app.api.v1.routers.conversation import create_conversation_router
from app.db.mongodb import get_database

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


app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# S3 and Conversation router will be mounted in startup
s3_client = None


@app.on_event("startup")
async def startup():
    global s3_client
    print("🚀 Starting VTailor Backend...")
    await connect_to_mongo()
    if await check_mongo_connection():
        print("✅ MongoDB connected")
    else:
        print("❌ MongoDB connection failed")

    # Initialize S3 client
    try:
        s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        print(f"✅ S3 client initialized: bucket={settings.S3_BUCKET}")
    except Exception as e:
        print(f"⚠️  S3 initialization failed: {e}")

    # Mount conversation router
    db = get_database()
    from app.conversation.service import ConversationService
    conv_svc = ConversationService(db)
    await conv_svc.ensure_indexes()
    conv_router = create_conversation_router(
        db=db,
        s3_client=s3_client,
        bucket=settings.S3_BUCKET,
    )
    app.include_router(
        conv_router,
        prefix="/app/api/v1/conversations",
        tags=["Conversations"],
    )


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
