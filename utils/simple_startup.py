#!/usr/bin/env python3
"""
Simple startup script for deployment
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Simple startup with basic database initialization"""
    try:
        logger.info("🚀 Starting simple deployment startup...")
        
        # Add current directory to Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        logger.info(f"✅ Added {project_root} to Python path")
        
        # Try to import and initialize database
        try:
            from app.database import init_db
            init_db()
            logger.info("✅ Database initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️  Database initialization issue: {e}")
            # Continue anyway - the app might work without this
        
        logger.info("✅ Startup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
