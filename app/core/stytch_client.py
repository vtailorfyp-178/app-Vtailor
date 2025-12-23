from stytch import Client
from app.core.config import get_settings

settings = get_settings()

stytch_client = Client(
    project_id=settings.STYTCH_PROJECT_ID,
    secret=settings.STYTCH_SECRET,
    environment="test",  # change to "live" later
)
