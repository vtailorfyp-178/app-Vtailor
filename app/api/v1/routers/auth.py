from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr                # BaseModel is structure for Data Validation. EmailStr is a type that validates email addresses
from app.core.stytch_client import stytch_client    # Stytch client for magic link authentication
from app.core.security import create_access_token, verify_token
from app.schemas.auth import (
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    TokenResponse,
    UserProfile,
    ErrorResponse
)
from app.services.user_services import get_user_by_email, create_user, get_user_by_id
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/send-magic-link",
    response_model=dict,
    responses={
        200: {"description": "Magic link sent successfully"},
        400: {"model": ErrorResponse, "description": "Invalid email or Stytch error"}
    }
)
async def send_magic_link(data: MagicLinkRequest):
    """
    Send a magic link to the user's email for passwordless authentication.
    
    - **email**: User's email address
    """
    # Validate email format
    if not data.email or "@" not in data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    try:
        response = stytch_client.magic_links.email.login_or_create(
            email=data.email,
            login_magic_link_url="http://localhost:8000/app/api/v1/auth/verify-callback",
            signup_magic_link_url="http://localhost:8000/app/api/v1/auth/verify-callback",
        )
        return {
            "status": "success",
            "message": f"Magic link sent successfully to {data.email}",
            "request_id": response.request_id,
            "email": data.email,
            "note": "Check your email (including spam folder) for the magic link"
        }
    except Exception as e:
        error_msg = str(e)
        return {
            "status": "error",
            "message": "Failed to send magic link",
            "detail": error_msg,
            "email": data.email,
            "note": "Make sure Stytch credentials are configured in .env file",
            "troubleshooting": {
                "step1": "Check .env file has STYTCH_PROJECT_ID and STYTCH_SECRET",
                "step2": "Restart backend: docker-compose restart web",
                "step3": "For testing without Stytch, use /auth/test-magic-link endpoint"
            }
        }


@router.post(
    "/test-magic-link",
    response_model=dict,
    responses={
        200: {"description": "Test magic link created successfully"}
    }
)
async def test_magic_link(data: MagicLinkRequest):
    """
    TEST ENDPOINT: Create a test magic link without requiring Stytch credentials.
    
    This endpoint generates a mock Stytch token for testing purposes.
    Use this to test the authentication flow without valid Stytch credentials.
    
    - **email**: User's email address
    """
    import uuid
    
    # Validate email format
    if not data.email or "@" not in data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Generate a mock token
    mock_token = f"test_token_{uuid.uuid4().hex[:32]}"
    
    return {
        "status": "success",
        "message": f"Test magic link created for {data.email}",
        "email": data.email,
        "token": mock_token,
        "callback_url": f"http://localhost:8000/app/api/v1/auth/verify-callback?token={mock_token}",
        "instructions": [
            "1. Copy the token above",
            "2. Go to the 'Verify Magic Link' section",
            "3. Paste the token and click 'Verify'",
            "4. You will get a JWT token (no email needed!)"
        ],
        "note": "This is a test endpoint. For production, use real Stytch credentials."
    }


@router.post(
    "/verify-magic-link",
    response_model=TokenResponse,
    responses={
        200: {"description": "Magic link verified and JWT token issued"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        500: {"model": ErrorResponse, "description": "Server error"}
    }
)
async def verify_magic_link(data: MagicLinkVerifyRequest):
    """
    Verify the magic link token and create/retrieve user, then issue JWT token.
    
    - **token**: Stytch magic link token or test token (starting with test_token_)
    """
    # Check if it's a test token
    if isinstance(data.token, str) and data.token.startswith("test_token_"):
        # Handle test token for development/testing
        test_email = "test_user@vtailor.local"
        
        existing_user = await get_user_by_email(test_email)
        
        if existing_user:
            user = existing_user
            user_id_db = str(existing_user.get("_id"))
        else:
            user = await create_user(email=test_email, role="customer")
            user_id_db = str(user.get("_id"))
        
        access_token = create_access_token(
            data={
                "user_id": user_id_db,
                "email": test_email,
                "role": user.get("role", "customer"),
            }
        )

        return TokenResponse(
            access_token=access_token,
            user_id=user_id_db,
            email=test_email,
            token_type="bearer"
        )
    
    # Handle real Stytch token
    try:
        # Verify token with Stytch
        response = stytch_client.magic_links.authenticate(
            token=data.token,
            session_duration_minutes=60
        )

        user_id = response.user_id
        email = response.user.emails[0].email

        # Check if user exists in our database
        existing_user = await get_user_by_email(email)
        
        if existing_user:
            user = existing_user
            user_id_db = str(existing_user.get("_id", user_id))
        else:
            # Create new user
            user = await create_user(email=email, role="customer")
            user_id_db = user.get("_id", user_id)

        # Create JWT token
        access_token = create_access_token(
            data={
                "user_id": user_id_db,
                "email": email,
                "role": user.get("role", "customer"),
            }
        )

        return TokenResponse(
            access_token=access_token,
            user_id=user_id_db,
            email=email,
            token_type="bearer"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Magic link verification failed: {str(e)}"
        )


@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    responses={
        200: {"description": "New token issued"},
        401: {"model": ErrorResponse, "description": "Invalid token"}
    }
)
async def refresh_token(data: dict):
    """
    Refresh a JWT token to extend session.
    
    - **token**: Current JWT token (in request body)
    """
    token = data.get("token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required"
        )
    
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get fresh user data
    user = await get_user_by_id(payload.get("user_id"))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new token
    new_token = create_access_token(
        data={
            "user_id": str(user.get("_id")),
            "email": user.get("email"),
            "role": user.get("role", "customer"),
        }
    )
    
    return TokenResponse(
        access_token=new_token,
        user_id=str(user.get("_id")),
        email=user.get("email"),
        token_type="bearer"
    )


@router.get(
    "/verify-callback",
    responses={
        200: {"description": "Magic link callback information"}
    }
)
async def verify_callback(request: Request, token: str = None):
    """
    Callback endpoint for magic link verification.
    Returns token information as JSON. Frontend should redirect to callback.html.
    
    - **token**: Stytch magic link token (from query parameter)
    """
    if not token:
        return {
            "status": "error",
            "message": "No token found in callback",
            "redirect_url": "callback.html"
        }
    
    return {
        "status": "success",
        "message": "Token received. Open callback.html with this token.",
        "token": token,
        "redirect_url": f"callback.html?token={token}"
    }
