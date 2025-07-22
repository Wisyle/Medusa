#!/usr/bin/env python3
"""
Script to create a test bot instance for debugging
"""

from database import SessionLocal, BotInstance
from datetime import datetime

def create_test_instance():
    """Create a test bot instance"""
    db = SessionLocal()
    
    try:
        # Check if instance already exists
        existing = db.query(BotInstance).first()
        if existing:
            print(f"✅ Bot instance already exists: {existing.name}")
            return
        
        # Create test instance
        test_instance = BotInstance(
            name="Test Bot",
            exchange="bybit",
            api_key="test_key",  # You'll need to replace these with real values
            api_secret="test_secret",
            trading_pair=None,  # Process all pairs
            strategies=[],  # Process all strategies
            is_active=True,
            polling_interval=60,
            telegram_bot_token=None,  # Add your bot token here
            telegram_chat_id=None,    # Add your chat ID here
            telegram_topic_id=None,   # Optional: add topic ID here
            webhook_url=None,         # Optional: add webhook URL here
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(test_instance)
        db.commit()
        
        print("✅ Test bot instance created successfully!")
        print(f"   Instance ID: {test_instance.id}")
        print(f"   Name: {test_instance.name}")
        print("   Configure with real API keys to test")
        
    except Exception as e:
        print(f"❌ Error creating test instance: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_instance()
