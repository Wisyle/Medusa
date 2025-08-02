from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from database import Base
from datetime import datetime

class MigrationHistory(Base):
    __tablename__ = 'migration_history'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    status = Column(String(50), default='pending')  # pending, running, completed, failed
    applied_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    tables_affected = Column(Text, nullable=True)  # JSON list of tables
    changes_made = Column(Text, nullable=True)  # JSON list of changes
    rollback_available = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<MigrationHistory(name='{self.name}', status='{self.status}')>" 