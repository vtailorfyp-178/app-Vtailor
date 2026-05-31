from pydantic_settings import BaseSettings # all for app configuration
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vtailor Backend"
    API_V1_PREFIX: str = "/app/api/v1"

    JWT_SECRET_KEY: str                             # JWT for authorization & session management
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    MONGODB_URL: str                 # MongoDB connection
    MONGO_DB_NAME: str

    STYTCH_PROJECT_ID: str                          # Stytch for authentication having passwordless options
    STYTCH_SECRET: str

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Wallet gateway integration (JazzCash / EasyPaisa)
    WALLET_CALLBACK_BASE_URL: str = "http://localhost:8000"
    JAZZCASH_MERCHANT_ID: str | None = None
    JAZZCASH_API_KEY: str | None = None
    JAZZCASH_API_URL: str | None = None
    JAZZCASH_VERIFY_API_URL: str | None = None
    JAZZCASH_PAYOUT_API_URL: str | None = None
    EASYPAISA_MERCHANT_ID: str | None = None
    EASYPAISA_API_KEY: str | None = None
    EASYPAISA_API_URL: str | None = None
    EASYPAISA_VERIFY_API_URL: str | None = None
    EASYPAISA_PAYOUT_API_URL: str | None = None
    WALLET_GATEWAY_SIMULATION: bool = True

    # Stream Chat — https://dashboard.getstream.io/
    STREAM_API_KEY: str | None = None
    STREAM_API_SECRET: str | None = None

    # AWS S3 for conversation media storage
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET: str = "tailor-app-media"

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings():
    return Settings()
