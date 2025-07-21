from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional, Dict, Any
import json

from config import settings
import os

engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BotInstance(Base):
    __tablename__ = "bot_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    exchange = Column(String(50), nullable=False)
    api_key = Column(String(255), nullable=False)
    api_secret = Column(String(255), nullable=False)
    api_passphrase = Column(String(255), nullable=True)  # For some exchanges
    
    strategies = Column(JSON, default=list)  # List of enabled strategies
    
    polling_interval = Column(Integer, default=60)  # seconds
    webhook_url = Column(String(500), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_topic_id = Column(String(100), nullable=True)
    
    is_active = Column(Boolean, default=False)
    last_poll = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PollState(Base):
    __tablename__ = "poll_states"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, nullable=False)
    symbol = Column(String(50), nullable=False)
    data_type = Column(String(20), nullable=False)  # 'position', 'order', 'trade'
    data_hash = Column(String(64), nullable=False)  # Hash of the data for change detection
    data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ErrorLog(Base):
    __tablename__ = "error_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, nullable=True)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    totp_secret = Column(String(255), nullable=True)
    totp_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_database_url():
    """Get database URL from environment or config"""
    return os.getenv("DATABASE_URL", settings.database_url)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
