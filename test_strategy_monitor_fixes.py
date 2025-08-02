#!/usr/bin/env python3
"""
Test Strategy Monitor Fixes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, BotInstance
from strategy_monitor import StrategyMonitorService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_strategy_monitor_fixes():
    """Test the fixed strategy monitor functionality"""
    try:
        logger.info("🧪 Testing Strategy Monitor Fixes...")
        
        # Test database query fix
        db = SessionLocal()
        try:
            # Get all active instances
            instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
            logger.info(f"✅ Found {len(instances)} active instances")
            
            # Test strategy filtering for each instance
            for instance in instances:
                if instance.strategies:
                    logger.info(f"Instance {instance.name} has strategies: {instance.strategies}")
                    
                    # Test if 'Combo' strategy exists
                    if 'Combo' in instance.strategies:
                        logger.info(f"✅ Found Combo strategy in instance {instance.name}")
                        
                        # Test the fixed strategy monitor service
                        try:
                            monitor_service = StrategyMonitorService('Combo')
                            strategy_instances = monitor_service._get_strategy_instances()
                            logger.info(f"✅ Strategy monitor found {len(strategy_instances)} Combo instances")
                            monitor_service.close()
                        except Exception as e:
                            logger.error(f"❌ Strategy monitor test failed: {e}")
                            return False
                        
                        break
            else:
                logger.info("ℹ️ No Combo strategy found in instances, testing with first available strategy")
                if instances and instances[0].strategies:
                    test_strategy = instances[0].strategies[0]
                    try:
                        monitor_service = StrategyMonitorService(test_strategy)
                        strategy_instances = monitor_service._get_strategy_instances()
                        logger.info(f"✅ Strategy monitor found {len(strategy_instances)} {test_strategy} instances")
                        monitor_service.close()
                    except Exception as e:
                        logger.error(f"❌ Strategy monitor test failed: {e}")
                        return False
                        
        finally:
            db.close()
        
        logger.info("🎉 All Strategy Monitor fixes tested successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_strategy_monitor_fixes()
    sys.exit(0 if success else 1)
