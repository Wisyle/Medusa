#!/usr/bin/env python3

import sys
sys.path.append('.')
from database import SessionLocal, BotInstance
from config import settings

def test_database_state():
    """Test current database state and configuration"""
    print("=== Testing Database State ===")
    
    print(f"Database URL: {settings.database_url}")
    print(f"Default Telegram Token: {settings.default_telegram_bot_token[:10] if settings.default_telegram_bot_token else None}...")
    print(f"Default Chat ID: {settings.default_telegram_chat_id}")
    
    db = SessionLocal()
    try:
        instances = db.query(BotInstance).all()
        print(f"\nTotal instances: {len(instances)}")
        
        for i in instances:
            print(f"Instance {i.id}: {i.name}")
            print(f"  Active: {i.is_active}")
            print(f"  Exchange: {i.exchange}")
            print(f"  Trading Pair: {i.trading_pair}")
            print(f"  API Key: {i.api_key[:10] if i.api_key else None}...")
            print(f"  Telegram Token: {i.telegram_bot_token[:10] if i.telegram_bot_token else None}...")
            print(f"  Telegram Chat ID: {i.telegram_chat_id}")
            print()
            
    finally:
        db.close()

if __name__ == "__main__":
    test_database_state()
