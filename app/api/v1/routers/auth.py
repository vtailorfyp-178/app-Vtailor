from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.stytch_client import stytch_client        # Stytch SDK client instance
from app.core.security import create_access_token, verify_token  # JWT helpers
from app.schemas.auth import (
    TokenResponse,
    UserProfile,
    ErrorResponse,
    EmailOTPStartRequest,
    EmailOTPStartResponse,
    EmailOTPVerifyRequest,
    RefreshTokenRequest,
)
from app.services.user_services import (
    get_user_by_email,
    create_user,
    get_user_by_id,
)

# ─────────────────────────────────────────────
# Router — all routes prefixed with /auth
# ─────────────────────────────────────────────
router = APIRouter(prefix="/auth", tags=["Authentication"])

# HTTPBearer extracts the JWT from "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer()


# ─────────────────────────────────────────────
# DEPENDENCY: get_current_user
# Use in ANY protected route to require authentication.
#
# Usage in any other router:
#   from app.api.v1.routers.auth import get_current_user
#   @router.get("/something")
#   async def something(current_user: dict = Depends(get_current_user)):
#       ...
# ─────────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
        )
    user = await get_user_by_id(payload.get("user_id"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )
    return user


# ─────────────────────────────────────────────
# ENDPOINT 1: Send Email OTP
# POST /auth/otp/start
#
# Flow:
#   1. Frontend sends user's email address
#   2. Backend calls Stytch → Stytch sends 6-digit OTP to that email
#   3. Frontend receives method_id — must store it for step 2
# ─────────────────────────────────────────────
@router.post(
    "/otp/start",
    response_model=EmailOTPStartResponse,
    responses={
        200: {"description": "OTP sent successfully via Email"},
        400: {"model": ErrorResponse, "description": "Invalid email or Stytch error"},
    },
    summary="Send Email OTP to user's email address",
)
async def otp_start(data: EmailOTPStartRequest):
    """
    Start passwordless login — sends a 6-digit OTP via Email.
    - **email**: Valid email address e.g. `user@example.com`
    """
    try:
        # Ask Stytch to send OTP to the email
        # login_or_create = works for both new and existing Stytch users
        resp = stytch_client.otps.email.login_or_create(email=data.email)

        return EmailOTPStartResponse(
            status="success",
            message=f"OTP sent to {data.email}",
            method_id=resp.method_id,  # Frontend MUST store this for verify step
            email=data.email,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send OTP: {str(e)}",
        )


# ─────────────────────────────────────────────
# ENDPOINT 2: Verify Email OTP
# POST /auth/otp/verify
#
# Flow:
#   1. Frontend sends method_id (from step 1) + OTP code from email
#   2. Backend sends both to Stytch for verification
#   3. Stytch confirms OTP is correct and not expired
#   4. Backend finds or creates user in OUR MongoDB
#   5. Backend issues a JWT — frontend stores this for all future requests
# ─────────────────────────────────────────────
@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    responses={
        200: {"description": "OTP verified, JWT token issued"},
        401: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
    },
    summary="Verify Email OTP and receive JWT token",
)
async def otp_verify(data: EmailOTPVerifyRequest):
    """
    Verify OTP and get a JWT access token.
    - **method_id**: Returned from `/auth/otp/start`
    - **code**: 6-digit OTP received via email
    """
    try:
        # Send method_id + OTP code to Stytch for verification
        resp = stytch_client.otps.authenticate(
            method_id=data.method_id,
            code=data.code,
            session_duration_minutes=60,
        )

        # Extract email from Stytch user object
        email = None
        if getattr(resp.user, "emails", None):
            if resp.user.emails:
                email = resp.user.emails[0].email

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract email from Stytch user.",
            )

        # Look up user in OUR MongoDB
        mongo_user = await get_user_by_email(email)

        # First-time user: create their record in MongoDB
        if mongo_user is None:
            mongo_user = await create_user(
                email=email,
                phone=None,
                role="customer",
            )

        # Convert MongoDB _id (ObjectId) to plain string
        mongo_user_id = str(mongo_user.get("_id"))

        # Issue our own JWT token
        access_token = create_access_token(
            data={
                "user_id": mongo_user_id,
                "email": mongo_user.get("email"),
                "role": mongo_user.get("role", "customer"),
            }
        )

        return TokenResponse(
            access_token=access_token,
            user_id=mongo_user_id,
            email=mongo_user.get("email"),
            phone=mongo_user.get("phone"),
            token_type="bearer",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OTP verification failed: {str(e)}",
        )


# ─────────────────────────────────────────────
# ENDPOINT 3: Refresh JWT Token
# POST /auth/refresh-token
# ─────────────────────────────────────────────
@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    responses={
        200: {"description": "New JWT token issued"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Refresh JWT access token",
)
async def refresh_token(data: RefreshTokenRequest):
    """
    Exchange a valid JWT for a fresh one.
    - **token**: Your current JWT access token
    """
    payload = verify_token(data.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await get_user_by_id(payload.get("user_id"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

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
        phone=user.get("phone"),
        token_type="bearer",
    )


# ─────────────────────────────────────────────
# ENDPOINT 4: Get Current User Profile
# GET /auth/me  (Protected — requires JWT)
#
# Frontend usage:
#   GET /auth/me
#   Headers: { Authorization: "Bearer <your_jwt_token>" }
# ─────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfile,
    responses={
        200: {"description": "Current user profile"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get current logged-in user's profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.
    Requires: `Authorization: Bearer <your_jwt_token>` header.
    """
    return UserProfile(
        user_id=str(current_user.get("_id")),
        email=current_user.get("email"),
        phone=current_user.get("phone"),
        role=current_user.get("role", "customer"),
        is_active=current_user.get("is_active", True),
        created_at=current_user.get("created_at"),
    )