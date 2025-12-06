from app.core.security import hash_password, verify_password
from app.models.user_model import User
from app.utils.jwt_manager import create_jwt_token
from app.db.collections import user_collection
from fastapi import HTTPException, status

class AuthService:
    @staticmethod
    def register_user(email: str, password: str) -> User:
        if user_collection.find_one({"email": email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        hashed_password = hash_password(password)
        new_user = User(email=email, password=hashed_password)
        user_collection.insert_one(new_user.dict())
        return new_user

    @staticmethod
    def login_user(email: str, password: str) -> str:
        user = user_collection.find_one({"email": email})
        if not user or not verify_password(password, user['password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        token = create_jwt_token({"email": user['email']})
        return token

    @staticmethod
    def get_user_from_token(token: str) -> User:
        email = decode_jwt_token(token)
        user = user_collection.find_one({"email": email})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return User(**user)