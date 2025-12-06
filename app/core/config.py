import os

class Config:
    """Configuration settings for the application."""
    
    # General settings
    DEBUG = os.getenv("DEBUG", "False") == "True"
    ENV = os.getenv("ENV", "development")
    
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017/vtailor")
    
    # Security settings
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    # Stytch API settings
    STYTCH_PROJECT_ID = os.getenv("STYTCH_PROJECT_ID", "your_project_id_here")
    STYTCH_SECRET = os.getenv("STYTCH_SECRET", "your_secret_here")
    
    # Other settings can be added as needed
