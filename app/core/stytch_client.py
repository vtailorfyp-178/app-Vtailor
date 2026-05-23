from stytch import Client       # used to interact with Stytch's user authentication services from your server-side
from app.core.config import get_settings

settings = get_settings()

stytch_client = Client(
    project_id=settings.STYTCH_PROJECT_ID,
    secret=settings.STYTCH_SECRET
    # environment="test",  # change to "live" later
)
