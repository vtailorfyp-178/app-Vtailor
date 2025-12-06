import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Log the request details
        logging.info(f"Request: {request.method} {request.url}")
        
        # Process the request
        response: Response = await call_next(request)
        
        # Log the response details
        logging.info(f"Response: {response.status_code} for {request.method} {request.url}")
        
        return response

# Initialize logging configuration
logging.basicConfig(level=logging.INFO)