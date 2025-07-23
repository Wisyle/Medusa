#!/usr/bin/env python3
"""
Pre-deployment validation script for TGL MEDUSA API Library migration
Run this before deploying to ensure seamless migration
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings
from database import Base, BotInstance
from api_library_model import ApiCredential
from strategy_monitor_model import StrategyMonitor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_current_database():
    """Validate current database structure and data"""
    try:
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        logger.info("🔍 Validating current database structure...")
        
        # Check if core tables exist
        tables = inspector.get_table_names()
        required_tables = ['bot_instances', 'users', 'activity_logs', 'error_logs']
        
        for table in required_tables:
            if table not in tables:
                logger.error(f"❌ Required table '{table}' not found!")
                return False
            logger.info(f"✅ Table '{table}' exists")
        
        # Check bot_instances structure
        bot_instances_columns = {col['name']: col for col in inspector.get_columns('bot_instances')}
        
        required_columns = ['id', 'name', 'exchange', 'api_key', 'api_secret']
        for col in required_columns:
            if col not in bot_instances_columns:
                logger.error(f"❌ Required column '{col}' not found in bot_instances!")
                return False
            logger.info(f"✅ Column '{col}' exists in bot_instances")
        
        # Count existing instances
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM bot_instances"))
            instance_count = result.scalar()
            logger.info(f"📊 Found {instance_count} existing bot instances")
            
            if instance_count > 0:
                # Check if any instances have API credentials
                result = conn.execute(text("SELECT COUNT(*) FROM bot_instances WHERE api_key IS NOT NULL AND api_secret IS NOT NULL"))
                instances_with_creds = result.scalar()
                logger.info(f"🔑 {instances_with_creds} instances have API credentials")
        
        logger.info("✅ Database validation passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database validation failed: {e}")
        return False

def validate_migration_readiness():
    """Check if migration can be performed safely"""
    try:
        logger.info("🧪 Testing migration readiness...")
        
        # Test database connection
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("✅ Database connection successful")
        
        # Test if new models can be imported
        try:
            from api_library_model import ApiCredential
            from strategy_monitor_model import StrategyMonitor
            logger.info("✅ New models import successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import new models: {e}")
            return False
        
        # Test if API library routes can be imported
        try:
            from api_library_routes import add_api_library_routes
            logger.info("✅ API library routes import successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import API library routes: {e}")
            return False
        
        logger.info("✅ Migration readiness validated")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration readiness check failed: {e}")
        return False

def check_environment_variables():
    """Verify all required environment variables are set"""
    logger.info("🌍 Checking environment variables...")
    
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'ALGORITHM'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ All required environment variables are set")
    return True

def simulate_migration():
    """Simulate the migration process without making changes"""
    try:
        logger.info("🎭 Simulating migration process...")
        
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # Check if api_credentials table will be created
        tables = inspector.get_table_names()
        if 'api_credentials' in tables:
            logger.info("ℹ️  api_credentials table already exists")
        else:
            logger.info("📝 api_credentials table will be created")
        
        # Check if api_credential_id column will be added
        if 'bot_instances' in tables:
            columns = {col['name']: col for col in inspector.get_columns('bot_instances')}
            if 'api_credential_id' in columns:
                logger.info("ℹ️  api_credential_id column already exists")
            else:
                logger.info("📝 api_credential_id column will be added to bot_instances")
        
        # Check if API fields can be made nullable
        if settings.database_url.startswith('postgresql'):
            logger.info("📝 API key/secret fields will be made nullable (PostgreSQL)")
        else:
            logger.info("📝 SQLite migration will add new column")
        
        logger.info("✅ Migration simulation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration simulation failed: {e}")
        return False

def main():
    """Main validation function"""
    logger.info("🚀 Starting pre-deployment validation for TGL MEDUSA API Library migration")
    
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Current Database", validate_current_database),
        ("Migration Readiness", validate_migration_readiness),
        ("Migration Simulation", simulate_migration)
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {check_name}")
        logger.info(f"{'='*50}")
        
        if not check_func():
            failed_checks.append(check_name)
    
    logger.info(f"\n{'='*50}")
    logger.info("VALIDATION SUMMARY")
    logger.info(f"{'='*50}")
    
    if failed_checks:
        logger.error(f"❌ {len(failed_checks)} validation(s) failed:")
        for check in failed_checks:
            logger.error(f"   - {check}")
        logger.error("\n🚨 DO NOT DEPLOY - Fix issues above first!")
        return False
    else:
        logger.info("✅ All validations passed!")
        logger.info("🚀 Ready for deployment!")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
