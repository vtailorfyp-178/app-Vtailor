from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("uvicorn.error")

# Try to import real routers / websockets; fall back to minimal placeholders if missing
try:
    from app.api.v1.routers import (
        auth_router,
        user_router,
        tailor_router,
        admin_router,
        order_router,
        chat_router,
        payment_router,
        file_router,
    )
except Exception as e:
    logger.warning("Some routers failed to import: %s", e)
    # create dummy routers to avoid import-time failures
    dummy = APIRouter()
    @dummy.get("/_placeholder")
    async def _placeholder():
        return {"ok": True}
    auth_router = user_router = tailor_router = admin_router = order_router = chat_router = payment_router = file_router = type("R", (), {"router": dummy})()

try:
    from app.api.v1.websocket.chat_ws import chat_websocket
except Exception:
    async def chat_websocket(ws: WebSocket):
        await ws.accept()
        await ws.send_text("chat_ws placeholder")
        await ws.close()

try:
    from app.api.v1.websocket.notifications_ws import notifications_websocket
except Exception:
    async def notifications_websocket(ws: WebSocket):
        await ws.accept()
        await ws.send_text("notifications_ws placeholder")
        await ws.close()

try:
    from app.api.v1.websocket.call_ws import call_websocket
except Exception:
    async def call_websocket(ws: WebSocket):
        await ws.accept()
        await ws.send_text("call_ws placeholder")
        await ws.close()

# db helpers may not exist during early development; handle gracefully
try:
    from app.db import close_database, get_database
except Exception:
    async def get_database():
        return None
    async def close_database():
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VTailor Backend...")
    try:
        db = await get_database()
        logger.info("Database connected: %s", bool(db))
    except Exception as e:
        logger.warning("Database connect failed at startup: %s", e)
    yield
    logger.info("Shutting down...")
    try:
        await close_database()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (only include if router attribute exists)
for r, prefix, tag in [
    (auth_router, "/api/v1/auth", "auth"),
    (user_router, "/api/v1/users", "users"),
    (tailor_router, "/api/v1/tailors", "tailors"),
    (admin_router, "/api/v1/admin", "admin"),
    (order_router, "/api/v1/orders", "orders"),
    (chat_router, "/api/v1/chat", "chat"),
    (payment_router, "/api/v1/payments", "payments"),
    (file_router, "/api/v1/files", "files"),
]:
    if hasattr(r, "router"):
        app.include_router(r.router, prefix=prefix, tags=[tag])

# WebSocket routes
app.add_websocket_route("/ws/chat", chat_websocket)
app.add_websocket_route("/ws/notifications", notifications_websocket)
app.add_websocket_route("/ws/call", call_websocket)

@app.get("/")
async def root():
    return {"message": "Welcome to VTailor Backend API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}