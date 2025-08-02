#!/usr/bin/env python3
"""
Test Deployment Migration Script
Verifies that the automatic migration system works correctly
"""

import os
import sys
from sqlalchemy import create_engine, text
from startup_migration import run_startup_migrations, verify_migration_success
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_migration():
    """Test the migration system"""
    logger.info("🧪 Testing deployment migration system...")
    
    # Show current configuration
    logger.info(f"📊 Database URL: {settings.database_url}")
    logger.info(f"📊 Database type: {'PostgreSQL' if settings.database_url.startswith('postgresql') else 'SQLite'}")
    
    # Test connection first
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1;"))
            logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
    
    # Run migrations
    try:
        success = run_startup_migrations()
        if not success:
            logger.error("❌ Migration test failed")
            return False
        
        # Verify migrations
        success = verify_migration_success()
        if not success:
            logger.error("❌ Migration verification failed")
            return False
        
        logger.info("🎉 Migration test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration test error: {e}")
        return False

def test_login():
    """Test that the default admin user can be used"""
    try:
        from auth import authenticate_user
        from database import SessionLocal
        
        db = SessionLocal()
        
        # Test authentication with default credentials
        user = authenticate_user(db, "admin@tarstrategies.com", "admin123")
        
        if user and user != "totp_required":
            logger.info("✅ Default admin user login test successful")
            logger.info(f"👤 User: {user.email} (Superuser: {user.is_superuser})")
            return True
        else:
            logger.error("❌ Default admin user login test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Login test error: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

def main():
    """Run all tests"""
    logger.info("🚀 Starting deployment migration tests...")
    
    # Test 1: Migration system
    migration_success = test_migration()
    
    # Test 2: Login system
    login_success = test_login()
    
    # Summary
    if migration_success and login_success:
        logger.info("🎉 All deployment tests passed!")
        logger.info("✅ Your application is ready for Render deployment")
        logger.info("🔑 Default login: admin@tarstrategies.com / admin123")
        logger.info("⚠️  Remember to change the default password after first login!")
        return True
    else:
        logger.error("❌ Some deployment tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 