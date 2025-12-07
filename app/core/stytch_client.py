import os
from dotenv import load_dotenv

load_dotenv()

STYTCH_PROJECT_ID = os.getenv("STYTCH_PROJECT_ID")
STYTCH_SECRET = os.getenv("STYTCH_SECRET")

# Only import stytch if credentials exist
if STYTCH_PROJECT_ID and STYTCH_SECRET:
    import stytch
    client = stytch.Client(
        project_id=STYTCH_PROJECT_ID,
        secret=STYTCH_SECRET
    )
else:
    client = None
    print("WARNING: Stytch credentials not found. Passwordless auth disabled.")

async def send_magic_link(email: str, redirect_url: str) -> dict:
    """Send passwordless magic link to user's email"""
    if not client:
        return {"success": False, "error": "Stytch not configured"}
    
    try:
        response = client.magic_links.email.send(
            email=email,
            login_magic_link_url=redirect_url
        )
        return {
            "success": True,
            "message": "Magic link sent to email",
            "user_id": response.user_id if hasattr(response, 'user_id') else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def authenticate_magic_link(token: str) -> dict:
    """Verify magic link token and authenticate user"""
    if not client:
        return {"success": False, "error": "Stytch not configured"}
    
    try:
        response = client.magic_links.authenticate(token)
        return {
            "success": True,
            "user_id": response.user_id,
            "email": response.email,
            "session_token": response.session_token if hasattr(response, 'session_token') else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def verify_session(session_token: str) -> dict:
    """Verify user session token"""
    if not client:
        return {"success": False, "error": "Stytch not configured"}
    
    try:
        response = client.sessions.authenticate(session_token)
        return {
            "success": True,
            "user_id": response.user_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def revoke_session(session_token: str) -> dict:
    """Logout user - revoke session"""
    if not client:
        return {"success": False, "error": "Stytch not configured"}
    
    try:
        client.sessions.revoke(session_token)
        return {"success": True, "message": "Session revoked"}
    except Exception as e:
        return {"success": False, "error": str(e)}