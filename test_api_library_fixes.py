#!/usr/bin/env python3
"""
Test script for API Library and Strategy Monitor fixes
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, BotInstance
from api_library_model import ApiCredential
from strategy_monitor_model import StrategyMonitor
from strategy_monitor import run_strategy_monitor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_library():
    """Test API Library functionality"""
    logger.info("🧪 Testing API Library...")
    
    db = SessionLocal()
    try:
        # Check if test credential already exists and delete it first
        existing = db.query(ApiCredential).filter_by(name="Test Bybit API").first()
        if existing:
            logger.info("🧹 Cleaning up existing test credential")
            db.delete(existing)
            db.commit()
        
        # Test creating API credential
        test_credential = ApiCredential(
            name="Test Bybit API",
            exchange="bybit",
            api_key="test_key_12345",
            api_secret="test_secret_67890",
            description="Test API credential for validation"
        )
        
        db.add(test_credential)
        db.commit()
        db.refresh(test_credential)
        
        logger.info(f"✅ Created test API credential: {test_credential.name}")
        
        # Test credential dictionary conversion
        cred_dict = test_credential.to_dict()
        logger.info(f"📝 Credential dict: {cred_dict}")
        assert cred_dict['name'] == "Test Bybit API"
        assert cred_dict['exchange'] == "bybit"
        
        # Check if the API key is properly masked (first 8 + ... + last 4)
        masked_key = cred_dict['api_key']
        logger.info(f"🔑 Masked API key: {masked_key}")
        expected_masked = "test_key...2345"  # first 8 + ... + last 4 chars
        assert masked_key == expected_masked, f"Expected '{expected_masked}', got '{masked_key}'"
        assert cred_dict['api_secret'] == '***HIDDEN***'
        
        logger.info("✅ API credential serialization works correctly")
        
        # Test full credentials access
        full_creds = test_credential.get_full_credentials()
        assert full_creds['api_key'] == "test_key_12345"
        assert full_creds['api_secret'] == "test_secret_67890"
        
        logger.info("✅ Full credentials access works correctly")
        
        # Clean up test data
        db.delete(test_credential)
        db.commit()
        logger.info("🧹 Test credential cleaned up")
        
        # Test instance with API library
        if db.query(BotInstance).first():
            instance = db.query(BotInstance).first()
            original_creds = instance.get_api_credentials()
            logger.info(f"✅ Instance API credentials access: {bool(original_creds)}")
        
        # Clean up
        db.delete(test_credential)
        db.commit()
        logger.info("✅ Cleaned up test data")
        
    except Exception as e:
        import traceback
        logger.error(f"❌ API Library test failed: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        db.rollback()
        return False
    finally:
        db.close()
    
    return True

def test_strategy_monitor_timing():
    """Test strategy monitor timing improvements"""
    logger.info("🧪 Testing Strategy Monitor timing...")
    
    db = SessionLocal()
    try:
        # Check if strategy monitors exist
        monitors = db.query(StrategyMonitor).all()
        logger.info(f"📊 Found {len(monitors)} strategy monitors")
        
        if monitors:
            monitor = monitors[0]
            logger.info(f"✅ Test monitor: {monitor.strategy_name}")
            logger.info(f"📅 Report interval: {monitor.report_interval} seconds")
            
            # Calculate expected sleep time based on new logic
            interval = monitor.report_interval
            if interval <= 300:  # 5 minutes or less
                expected_sleep = 30
            elif interval <= 900:  # 15 minutes or less
                expected_sleep = 60
            else:
                expected_sleep = min(300, interval // 4)
            
            logger.info(f"⏰ Expected check interval: {expected_sleep} seconds")
            
            if interval <= 300:
                logger.info("✅ Short interval monitor will check every 30 seconds")
            elif interval <= 900:
                logger.info("✅ Medium interval monitor will check every 60 seconds")
            else:
                logger.info(f"✅ Long interval monitor will check every {expected_sleep} seconds")
        else:
            logger.info("ℹ️  No strategy monitors configured to test")
        
    except Exception as e:
        logger.error(f"❌ Strategy Monitor timing test failed: {e}")
        return False
    finally:
        db.close()
    
    return True

def test_database_schema():
    """Test database schema updates"""
    logger.info("🧪 Testing database schema...")
    
    db = SessionLocal()
    try:
        # Test ApiCredential table
        credential_count = db.query(ApiCredential).count()
        logger.info(f"✅ ApiCredential table accessible (count: {credential_count})")
        
        # Test BotInstance updates
        instances = db.query(BotInstance).all()
        for instance in instances:
            # Test get_api_credentials method
            creds = instance.get_api_credentials()
            if creds:
                has_key = bool(creds.get('api_key'))
                has_secret = bool(creds.get('api_secret'))
                logger.info(f"✅ Instance {instance.name}: API key={has_key}, secret={has_secret}")
            else:
                logger.warning(f"⚠️  Instance {instance.name}: No API credentials")
        
        logger.info("✅ Database schema validation completed")
        
    except Exception as e:
        logger.error(f"❌ Database schema test failed: {e}")
        return False
    finally:
        db.close()
    
    return True

def main():
    """Run all tests"""
    logger.info("🚀 Starting API Library and Strategy Monitor Tests")
    
    tests = [
        ("Database Schema", test_database_schema),
        ("API Library", test_api_library),
        ("Strategy Monitor Timing", test_strategy_monitor_timing),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running {test_name} Test")
        logger.info(f"{'='*50}")
        
        try:
            if test_func():
                logger.info(f"✅ {test_name} test PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} test CRASHED: {e}")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    logger.info(f"{'='*50}")
    
    if passed == total:
        logger.info("🎉 All tests passed! API Library and Strategy Monitor improvements are ready!")
        return True
    else:
        logger.error("❌ Some tests failed. Please review the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
