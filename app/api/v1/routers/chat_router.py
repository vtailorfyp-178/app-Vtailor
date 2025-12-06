from fastapi import APIRouter, HTTPException
from app.models.message_model import Message
from app.schemas.chat_schema import ChatMessageSchema
from app.services.chat_service import ChatService

router = APIRouter()
chat_service = ChatService()

@router.post("/send", response_model=ChatMessageSchema)
async def send_message(message: ChatMessageSchema):
    try:
        return await chat_service.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/messages/{chat_id}", response_model=list[ChatMessageSchema])
async def get_messages(chat_id: str):
    try:
        return await chat_service.get_messages(chat_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))