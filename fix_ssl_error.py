#!/usr/bin/env python3
"""
Fix SSL errors in database connections
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from database import SessionLocal, engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test database connection with SSL settings"""
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
        db.close()
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def update_env_for_ssl():
    """Update environment variables for SSL"""
    # Disable SSL verification for PostgreSQL if having issues
    os.environ['PGSSLMODE'] = 'prefer'
    logger.info("Updated SSL mode to 'prefer'")

if __name__ == "__main__":
    logger.info("Testing database connection...")
    
    if not test_connection():
        logger.info("Trying with updated SSL settings...")
        update_env_for_ssl()
        test_connection()
    
    logger.info("\nIf you're still having SSL errors, add these to your Render environment variables:")
    logger.info("PGSSLMODE=prefer")
    logger.info("Or if that doesn't work:")
    logger.info("PGSSLMODE=disable") 