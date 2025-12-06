from pydantic import BaseModel
from typing import Optional, List

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    is_verified: bool

    class Config:
        orm_mode = True

class UserResponse(User):
    message: str

class UserListResponse(BaseModel):
    users: List[User]
    total: int