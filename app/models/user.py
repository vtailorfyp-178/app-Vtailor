from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    role: str = "customer"

class UserInDB(UserCreate):
    id: Optional[str]
    is_active: bool = True
    created_at: datetime = datetime.utcnow()
