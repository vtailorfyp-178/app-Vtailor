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

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings():
    return Settings()
