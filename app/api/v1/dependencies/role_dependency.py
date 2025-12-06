# role_dependency.py

from fastapi import Depends, HTTPException
from app.utils.custom_exceptions import RoleException
from app.db.collections import UserCollection

def get_current_user_role(user_id: str):
    user = UserCollection.find_one({"_id": user_id})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.get("role")

def role_required(required_role: str):
    def role_checker(user_role: str = Depends(get_current_user_role)):
        if user_role != required_role:
            raise RoleException(detail="Insufficient permissions")
    return role_checker