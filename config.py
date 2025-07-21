import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./tgl_medusa.db"
    
    secret_key: str = "your-secret-key-here-change-in-production"
    jwt_secret: str = "your-jwt-secret-here-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    admin_username: str = "admin"
    admin_password: str = "changeme123"
    
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    default_telegram_bot_token: Optional[str] = None
    default_telegram_chat_id: Optional[str] = None
    default_telegram_topic_id: Optional[str] = None
    
    app_name: str = "TGL Medusa Loggers"
    app_description: str = "Advanced Cryptocurrency Bot Monitoring System"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    webhook_secret: str = "your-webhook-secret-change-in-production"
    
    class Config:
        env_file = ".env"

settings = Settings()
