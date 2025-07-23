#!/usr/bin/env python3
"""
Strategy Monitor System Initialization
"""

import logging
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from migration import migrate_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_strategy_monitor_system():
    """Initialize the Strategy Monitor System"""
    try:
        logger.info("🚀 Initializing Strategy Monitor System...")
        
        # Run database migrations first
        logger.info("📊 Running database migrations...")
        migrate_database()
        
        # Initialize database
        logger.info("🔧 Initializing database...")
        init_db()
        
        # Verify strategy_monitors table exists
        db = SessionLocal()
        try:
            from strategy_monitor_model import StrategyMonitor
            test_query = db.query(StrategyMonitor).count()
            logger.info(f"✅ Strategy monitors table verified - {test_query} monitors configured")
        except Exception as e:
            logger.error(f"❌ Strategy monitors table verification failed: {e}")
        finally:
            db.close()
        
        logger.info("🎉 Strategy Monitor System initialization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Strategy Monitor System initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = initialize_strategy_monitor_system()
    sys.exit(0 if success else 1)
