import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./combologger.db"
    
    admin_username: str = "admin"
    admin_password: str = "changeme123"
    
    default_telegram_bot_token: Optional[str] = None
    default_telegram_chat_id: Optional[str] = None
    
    secret_key: str = "your-secret-key-here"
    
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    webhook_secret: str = "your-webhook-secret"
    
    class Config:
        env_file = ".env"

settings = Settings()
