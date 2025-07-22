#!/usr/bin/env python3

import sys
sys.path.append('.')
import asyncio
from database import SessionLocal, BotInstance
from polling import ExchangePoller
from config import settings
from telegram import Bot

async def test_telegram_config():
    """Test Telegram bot configuration"""
    print("=== Testing Telegram Configuration ===")
    
    db = SessionLocal()
    try:
        instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
        
        for instance in instances:
            print(f"\n--- Instance {instance.id}: {instance.name} ---")
            
            if instance.telegram_bot_token:
                print(f"Instance token: {instance.telegram_bot_token[:10]}...")
                try:
                    bot = Bot(token=instance.telegram_bot_token)
                    me = await bot.get_me()
                    print(f"✅ Instance bot connected: @{me.username}")
                except Exception as e:
                    print(f"❌ Instance bot failed: {e}")
            
            if settings.default_telegram_bot_token:
                print(f"Default token: {settings.default_telegram_bot_token[:10]}...")
                try:
                    bot = Bot(token=settings.default_telegram_bot_token)
                    me = await bot.get_me()
                    print(f"✅ Default bot connected: @{me.username}")
                except Exception as e:
                    print(f"❌ Default bot failed: {e}")
            
            chat_id = instance.telegram_chat_id or settings.default_telegram_chat_id
            print(f"Chat ID: {chat_id}")
            
            if chat_id and (instance.telegram_bot_token or settings.default_telegram_bot_token):
                try:
                    token = instance.telegram_bot_token or settings.default_telegram_bot_token
                    bot = Bot(token=token)
                    await bot.send_message(chat_id=chat_id, text="🧪 Test notification from combologger debug script")
                    print("✅ Test message sent successfully")
                except Exception as e:
                    print(f"❌ Failed to send test message: {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_telegram_config())
