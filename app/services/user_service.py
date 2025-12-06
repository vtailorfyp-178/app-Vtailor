from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate
from app.db.collections import user_collection
from bson import ObjectId

class UserService:
    @staticmethod
    def create_user(user_data: UserCreate) -> User:
        user = User(**user_data.dict())
        user_collection.insert_one(user.dict())
        return user

    @staticmethod
    def get_user(user_id: str) -> User:
        user_data = user_collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(**user_data)
        return None

    @staticmethod
    def update_user(user_id: str, user_data: UserUpdate) -> User:
        user_collection.update_one({"_id": ObjectId(user_id)}, {"$set": user_data.dict()})
        updated_user_data = user_collection.find_one({"_id": ObjectId(user_id)})
        return User(**updated_user_data) if updated_user_data else None

    @staticmethod
    def delete_user(user_id: str) -> bool:
        result = user_collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

    @staticmethod
    def list_users() -> list:
        users = user_collection.find()
        return [User(**user) for user in users]