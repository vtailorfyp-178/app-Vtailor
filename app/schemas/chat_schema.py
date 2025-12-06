from pydantic import BaseModel
from typing import List, Optional

class MessageSchema(BaseModel):
    sender_id: str
    receiver_id: str
    content: str
    timestamp: str

class ChatSchema(BaseModel):
    chat_id: str
    participants: List[str]
    messages: List[MessageSchema]
    created_at: str
    updated_at: Optional[str] = None

class CreateChatRequest(BaseModel):
    participants: List[str]

class SendMessageRequest(BaseModel):
    chat_id: str
    sender_id: str
    content: str

class GetChatResponse(BaseModel):
    chat: ChatSchema

class SendMessageResponse(BaseModel):
    message: MessageSchema
    status: str