from fastapi import APIRouter
from app.api.v1.routers import auth, users, wallet, fashion_chatbot, stream_chat, notifications, orders

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(wallet.router)
api_router.include_router(fashion_chatbot.router)
api_router.include_router(stream_chat.router)
api_router.include_router(notifications.router)
api_router.include_router(orders.router)
