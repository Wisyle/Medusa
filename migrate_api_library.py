#!/usr/bin/env python3
"""
Migration script to add API Library support
"""

from database import SessionLocal, engine, Base, BotInstance
from api_library_model import ApiCredential
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_api_library():
    """Add API Library tables and migrate existing instances"""
    
    logger.info("🔄 Starting API Library migration...")
    
    # Create all tables (including new ones)
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Created API Library tables")
    
    # Update BotInstance table to add api_credential_id column and make api fields nullable
    db = SessionLocal()
    try:
        # Check if api_credential_id column exists
        result = db.execute(text("PRAGMA table_info(bot_instances);"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'api_credential_id' not in columns:
            logger.info("📊 Adding api_credential_id column to bot_instances table...")
            db.execute(text("ALTER TABLE bot_instances ADD COLUMN api_credential_id INTEGER;"))
            db.commit()
            logger.info("✅ Added api_credential_id column")
        else:
            logger.info("✅ api_credential_id column already exists")
        
        # Check existing instances
        instances = db.query(BotInstance).all()
        logger.info(f"📋 Found {len(instances)} existing bot instances")
        
        if instances:
            logger.info("ℹ️  Existing instances will continue to use direct API credentials")
            logger.info("ℹ️  You can migrate them to the API Library later through the web interface")
        
        logger.info("🎉 API Library migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_api_library()
