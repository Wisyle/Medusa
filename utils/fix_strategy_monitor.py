#!/usr/bin/env python3
"""
Fix Strategy Monitor Database Schema
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from migration import migrate_database
from database import SessionLocal, init_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_strategy_monitor_schema():
    """Fix the strategy monitor database schema"""
    try:
        logger.info("🔧 Fixing Strategy Monitor Database Schema...")
        
        # Run migration
        migrate_database()
        
        # Reinitialize database to ensure all tables are current
        init_db()
        
        # Test the StrategyMonitor model
        db = SessionLocal()
        try:
            from strategy_monitor_model import StrategyMonitor
            
            # Try to query (this will test if the schema is correct)
            count = db.query(StrategyMonitor).count()
            logger.info(f"✅ StrategyMonitor model working correctly - {count} monitors found")
            
            # Test creating a dummy monitor to verify all fields work
            test_monitor = StrategyMonitor(
                strategy_name="test_strategy_temp",
                telegram_bot_token="test_token",
                telegram_chat_id="test_chat",
                report_interval=3600,
                include_positions=True,
                include_orders=True,
                include_trades=True,
                include_pnl=True,
                max_recent_positions=20,
                is_active=False
            )
            
            db.add(test_monitor)
            db.commit()
            
            # Delete the test monitor
            db.delete(test_monitor)
            db.commit()
            
            logger.info("✅ All StrategyMonitor fields working correctly")
            
        except Exception as e:
            logger.error(f"❌ StrategyMonitor model test failed: {e}")
            return False
        finally:
            db.close()
        
        logger.info("🎉 Strategy Monitor schema fix completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema fix failed: {e}")
        return False

if __name__ == "__main__":
    success = fix_strategy_monitor_schema()
    sys.exit(0 if success else 1)
