from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from database import Base

class StrategyMonitor(Base):
    __tablename__ = "strategy_monitors"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(50), nullable=False, unique=True)  # 'Combo', 'DCA', 'Grid', etc.
    is_active = Column(Boolean, default=True)
    
    # Telegram configuration
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True) 
    telegram_topic_id = Column(String(100), nullable=True)
    
    # Reporting configuration
    report_interval = Column(Integer, default=3600)  # seconds between reports
    include_positions = Column(Boolean, default=True)
    include_orders = Column(Boolean, default=True)
    include_trades = Column(Boolean, default=True)
    include_pnl = Column(Boolean, default=True)
    max_recent_positions = Column(Integer, default=10)
    
    # Status tracking
    last_report = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
