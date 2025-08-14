#!/usr/bin/env python3
"""
API Library Model - Manage reusable API credentials
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ApiCredential(Base):
    __tablename__ = "api_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)  # Owner of the credential
    name = Column(String(100), nullable=False)  # Human-readable name (unique per user)
    exchange = Column(String(50), nullable=False)  # binance, bybit, etc.
    api_key = Column(String(255), nullable=False)
    api_secret = Column(String(255), nullable=False)
    api_passphrase = Column(String(255), nullable=True)  # For OKX, KuCoin
    
    # Using string reference to avoid circular import
    # user = relationship("User", back_populates="api_credentials")
    
    # Status and usage tracking
    is_active = Column(Boolean, default=True)
    is_in_use = Column(Boolean, default=False)  # Track if currently assigned to an instance
    current_instance_id = Column(Integer, nullable=True)  # Which instance is using it
    
    # Metadata
    description = Column(Text, nullable=True)  # Optional description
    tags = Column(String(255), nullable=True)  # Comma-separated tags
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ApiCredential(name='{self.name}', exchange='{self.exchange}', in_use={self.is_in_use})>"
    
    def to_dict(self, include_user_info=False):
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'exchange': self.exchange,
            'api_key': self.api_key[:8] + '...' + self.api_key[-4:] if len(self.api_key) > 12 else self.api_key,  # Masked
            'api_secret': '***HIDDEN***',  # Never expose in API
            'has_passphrase': bool(self.api_passphrase),
            'is_active': self.is_active,
            'is_in_use': self.is_in_use,
            'current_instance_id': self.current_instance_id,
            'description': self.description,
            'tags': self.tags.split(',') if self.tags else [],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_used': self.last_used
        }
        
        if include_user_info and hasattr(self, 'user') and self.user:
            result['user_email'] = self.user.email
            result['user_name'] = self.user.full_name
            
        return result
    
    def get_full_credentials(self):
        """Get full credentials for internal use only"""
        return {
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'api_passphrase': self.api_passphrase
        }
