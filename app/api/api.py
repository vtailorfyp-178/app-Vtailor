from fastapi import APIRouter
from app.api.v1.routers import auth, users, wallet, fashion_chatbot, fabric_prints, measurement_models

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(wallet.router)
api_router.include_router(fashion_chatbot.router)
api_router.include_router(fabric_prints.router)
api_router.include_router(measurement_models.router)
