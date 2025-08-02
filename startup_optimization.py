#!/usr/bin/env python3
"""
Startup Optimization Script for Render Deployment
Validates environment and optimizes startup sequence
"""
import os
import sys
import asyncio
import logging
from sqlalchemy import create_engine, text
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_environment():
    """Validate required environment variables"""
    logger.info("🔍 Validating environment variables...")
    
    required_vars = {
        'DATABASE_URL': 'Database connection string',
        'PORT': 'Port for web service'
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing.append(f"{var} ({description})")
    
    if missing:
        logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    
    logger.info("✅ All required environment variables present")
    return True

def test_database_connection():
    """Test database connection with timeout"""
    logger.info("🔍 Testing database connection...")
    
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///./medusa.db')
    
    # Configure connection with aggressive timeouts
    connect_args = {}
    if database_url.startswith('postgresql'):
        connect_args = {
            'connect_timeout': 5,
            'options': '-c statement_timeout=5000'  # 5 second statement timeout
        }
    
    try:
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        
        # Test connection
        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Database connection successful (took {elapsed:.2f}s)")
        
        if elapsed > 3:
            logger.warning(f"⚠️ Database connection is slow ({elapsed:.2f}s)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def optimize_settings():
    """Set optimized environment variables for Render"""
    logger.info("🔧 Applying startup optimizations...")
    
    # Skip migrations on startup for faster boot
    os.environ['SKIP_MIGRATIONS'] = 'true'
    
    # Reduce worker timeout for faster failure detection
    os.environ['WORKER_TIMEOUT'] = '30'
    
    # Disable debug mode in production
    os.environ['DEBUG'] = 'false'
    
    logger.info("✅ Optimizations applied")

async def main():
    """Main startup optimization routine"""
    logger.info("🚀 TAR Lighthouse - Startup Optimization")
    logger.info(f"📅 {datetime.utcnow().isoformat()}")
    
    # Step 1: Validate environment
    if not validate_environment():
        logger.error("❌ Environment validation failed")
        sys.exit(1)
    
    # Step 2: Test database connection
    if not test_database_connection():
        logger.error("❌ Database connection test failed")
        logger.info("💡 Check your DATABASE_URL and ensure the database is accessible")
        sys.exit(1)
    
    # Step 3: Apply optimizations
    optimize_settings()
    
    logger.info("✅ All startup checks passed!")
    logger.info("🚀 Starting main application...")
    
    # Start the main app with optimized settings
    import subprocess
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "main:app", 
        "--host", "0.0.0.0", 
        "--port", os.environ.get("PORT", "8000"),
        "--timeout-keep-alive", "120",
        "--workers", "1"  # Single worker for Render free tier
    ])

if __name__ == "__main__":
    asyncio.run(main()) 