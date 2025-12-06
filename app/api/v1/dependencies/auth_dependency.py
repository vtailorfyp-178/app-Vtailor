from fastapi import Depends, HTTPException, status
from app.core.security import verify_token
from app.models.user_model import User
from app.db.connection import get_current_user

def auth_dependency(token: str = Depends(verify_token)) -> User:
    user = get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user