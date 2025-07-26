from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from typing import Optional, Dict, Any
import json

from config import settings
import os

connect_args = {}
if settings.database_url.startswith('postgresql'):
    connect_args = {
        'sslmode': 'require',
        'connect_timeout': 30,
        'application_name': 'tgl_medusa_worker'
    }

engine = create_engine(
    settings.database_url, 
    echo=settings.debug,
    connect_args=connect_args,
    pool_size=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_timeout=30
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BotInstance(Base):
    __tablename__ = "bot_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)  # Owner of the instance
    name = Column(String(100), nullable=False)
    exchange = Column(String(50), nullable=False)
    market_type = Column(String(20), default='unified')  # 'spot', 'futures', 'unified'
    
    # API Credentials - either direct or from library
    api_credential_id = Column(Integer, ForeignKey('api_credentials.id'), nullable=True)  # New: API Library reference
    api_key = Column(String(255), nullable=True)  # Legacy: Direct API key (made nullable for backward compatibility)
    api_secret = Column(String(255), nullable=True)  # Legacy: Direct API secret
    api_passphrase = Column(String(255), nullable=True)  # For some exchanges
    
    strategies = Column(JSON, default=list)  # List of enabled strategies
    
    polling_interval = Column(Integer, default=60)  # seconds
    webhook_url = Column(String(500), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_topic_id = Column(String(100), nullable=True)
    trading_pair = Column(String(20), nullable=True)
    balance_enabled = Column(Boolean, default=False)  # Toggle for balance tracking and notifications
    
    is_active = Column(Boolean, default=False)
    last_poll = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to API Credential (defined as string to avoid circular import)
    # api_credential = relationship("ApiCredential", foreign_keys=[api_credential_id])
    
    def get_api_credentials(self):
        """Get API credentials from either direct fields or API library"""
        if self.api_credential_id:
            # Import here to avoid circular imports
            from api_library_model import ApiCredential
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=engine)
            db = Session()
            try:
                credential = db.query(ApiCredential).filter(ApiCredential.id == self.api_credential_id).first()
                if credential:
                    return credential.get_full_credentials()
            finally:
                db.close()
        
        # Fallback to direct credentials for backward compatibility
        return {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'api_passphrase': self.api_passphrase
            }

class PollState(Base):
    __tablename__ = "poll_states"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, nullable=False)
    symbol = Column(String(50), nullable=False)
    data_type = Column(String(100), nullable=False)  # 'position', 'order_<uuid>', 'trade_<uuid>'
    data_hash = Column(String(64), nullable=False)  # Hash of the data for change detection
    data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class BalanceHistory(Base):
    __tablename__ = "balance_history"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey('bot_instances.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    balance_data = Column(JSON, nullable=False)  # Full balance snapshot
    total_value_usd = Column(Float, nullable=True)  # Optional: total value in USD
    created_at = Column(DateTime, default=datetime.utcnow)

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

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship("UserRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role")

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    resource = Column(String(100), nullable=False)  # e.g., 'bot_instances', 'api_library', 'users'
    action = Column(String(50), nullable=False)  # e.g., 'read', 'write', 'delete', 'manage'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    roles = relationship("RolePermission", back_populates="permission")

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    assigned_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # Who assigned this role
    assigned_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="roles")
    role = relationship("Role", back_populates="users")
    assigner = relationship("User", foreign_keys=[assigned_by])

class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    permission_id = Column(Integer, ForeignKey('permissions.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

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
    private_key_hash = Column(String(255), nullable=True)  # Admin private key hash for enhanced security
    passphrase_hash = Column(String(255), nullable=True)  # Admin passphrase hash for enhanced security
    needs_security_setup = Column(Boolean, default=False)  # Flag for first-time login users
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    roles = relationship("UserRole", foreign_keys="UserRole.user_id", back_populates="user")
    # api_credentials = relationship("ApiCredential", back_populates="user")  # Commented out to avoid circular import
    
    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has specific permission"""
        if self.is_superuser:
            return True
            
        for user_role in self.roles:
            for role_permission in user_role.role.permissions:
                perm = role_permission.permission
                if perm.resource == resource and perm.action == action:
                    return True
        return False
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role"""
        return any(user_role.role.name == role_name for user_role in self.roles)
    
    def get_permissions(self) -> list:
        """Get all permissions for this user"""
        if self.is_superuser:
            return ['*']  # Superuser has all permissions
            
        permissions = []
        for user_role in self.roles:
            for role_permission in user_role.role.permissions:
                perm = role_permission.permission
                permissions.append(f"{perm.resource}:{perm.action}")
        return list(set(permissions))  # Remove duplicates

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
    # Import all models to ensure they're registered
    from strategy_monitor_model import StrategyMonitor
    from api_library_model import ApiCredential
    from dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
    from validator_node_model import ValidatorNode, ValidatorReward
    Base.metadata.create_all(bind=engine)
    
    try:
        from role_migration import run_migration
        run_migration()
    except Exception as e:
        print(f"Role migration failed: {e}")
