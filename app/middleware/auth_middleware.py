from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.jwt_manager import verify_jwt

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if not token:
            raise HTTPException(status_code=401, detail="Authorization token is missing")
        
        try:
            payload = verify_jwt(token)
            request.state.user = payload  # Attach user info to the request state
        except Exception as e:
            raise HTTPException(status_code=403, detail=str(e))
        
        response = await call_next(request)
        return response