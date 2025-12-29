from fastapi import APIRouter, HTTPException, status, Request
from app.core.stytch_client import stytch_client    # Stytch client for authentication
from app.core.security import create_access_token, verify_token
from app.schemas.auth import (
    TokenResponse,
    UserProfile,
    ErrorResponse,
    PhoneOTPStartRequest,
    PhoneOTPStartResponse,
    PhoneOTPVerifyRequest,
)
from app.services.user_services import get_user_by_email, create_user, get_user_by_id, get_user_by_phone

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
            "phone": user.get("phone"),
        }
    )
    
    return TokenResponse(
        access_token=new_token,
        user_id=str(user.get("_id")),
        email=user.get("email"),
        phone=user.get("phone"),
        token_type="bearer"
    )


# ---------------------------
# SMS OTP (Phone) Endpoints
# ---------------------------


def _is_e164(phone: str) -> bool:
    """Basic E.164 validation: starts with '+' and 9-15 digits."""
    if not isinstance(phone, str) or not phone.startswith("+"):
        return False
    digits = phone[1:]
    return digits.isdigit() and 9 <= len(digits) <= 15


@router.post(
    "/otp/start",
    response_model=PhoneOTPStartResponse,
    responses={
        200: {"description": "OTP sent successfully via SMS"},
        400: {"model": ErrorResponse, "description": "Invalid phone format"}
    }
)
async def otp_start(data: PhoneOTPStartRequest):
    """
    Start passwordless authentication by sending an SMS OTP to the user's phone.

    - **phone**: E.164 formatted phone number, e.g., "+15551234567"
    """
    if not _is_e164(data.phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone format. Use E.164 like +15551234567")

    try:
        # Stytch will create user if not exists and send OTP
        resp = stytch_client.otps.sms.login_or_create(phone_number=data.phone)
        return PhoneOTPStartResponse(
            status="success",
            message=f"OTP sent to {data.phone}",
            method_id=resp.method_id,
            phone=data.phone,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to send OTP: {str(e)}")


@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    responses={
        200: {"description": "OTP verified and JWT token issued"},
        401: {"model": ErrorResponse, "description": "Invalid or expired OTP"}
    }
)
async def otp_verify(data: PhoneOTPVerifyRequest):
    """
    Verify SMS OTP using Stytch and issue JWT.

    - **method_id**: Returned from `/auth/otp/start`
    - **code**: The 6-digit OTP received via SMS
    """
    try:
        resp = stytch_client.otps.authenticate(
            method_id=data.method_id,
            code=data.code,
            session_duration_minutes=60,
        )

        user_id = resp.user_id
        # Stytch returns phone numbers; pick the first if present
        phone = None
        if getattr(resp.user, "phone_numbers", None):
            phone_numbers = resp.user.phone_numbers
            if phone_numbers:
                phone = phone_numbers[0].phone_number

        # Optional email if present
        email = None
        if getattr(resp.user, "emails", None):
            emails = resp.user.emails
            if emails:
                email = emails[0].email

        # Find existing user by phone first, else by email
        user = None
        user_id_db = None
        if phone:
            existing_by_phone = await get_user_by_phone(phone)
            if existing_by_phone:
                user = existing_by_phone
                user_id_db = str(existing_by_phone.get("_id"))
        if user is None and email:
            existing_by_email = await get_user_by_email(email)
            if existing_by_email:
                user = existing_by_email
                user_id_db = str(existing_by_email.get("_id"))

        if user is None:
            # Create new user using available identifiers
            user = await create_user(email=email, phone=phone, role="customer")
            user_id_db = str(user.get("_id", user_id))

        access_token = create_access_token(
            data={
                "user_id": user_id_db,
                "email": user.get("email"),
                "role": user.get("role", "customer"),
                "phone": user.get("phone"),
            }
        )

        return TokenResponse(
            access_token=access_token,
            user_id=user_id_db,
            email=user.get("email"),
            phone=user.get("phone"),
            token_type="bearer",
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"OTP verification failed: {str(e)}")
