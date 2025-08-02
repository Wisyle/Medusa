import asyncio
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import BotInstance, get_database_url
from polling import run_poller
from init_strategy_monitor import initialize_strategy_monitor_system

def get_db_session():
    """Create database session for worker with retry logic"""
    import time
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            database_url = get_database_url()
            
            connect_args = {}
            if database_url.startswith('postgresql'):
                connect_args = {
                    'sslmode': 'require',
                    'connect_timeout': 30,
                    'application_name': 'tgl_medusa_worker'
                }
            
            engine = create_engine(
                database_url,
                connect_args=connect_args,
                pool_size=10,
                pool_recycle=3600,
                pool_pre_ping=True,
                pool_timeout=30
            )
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            return SessionLocal()
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise

async def monitor_instances():
    """Monitor and restart failed instances - standalone version"""
    print('TGL MEDUSA Worker Starting...')
    
    # Initialize Strategy Monitor System
    print('🎯 Initializing Strategy Monitor System...')
    initialize_strategy_monitor_system()
    
    await send_startup_notification()
    
    while True:
        try:
            db = get_db_session()
            
            active_instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
            
            print(f"Found {len(active_instances)} active instances to monitor")
            
            for instance in active_instances:
                try:
                    print(f"Processing instance {instance.id}: {instance.name}")
                    await run_poller(instance.id)
                except Exception as e:
                    print(f"Error processing instance {instance.id}: {e}")
            
            db.close()
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(60)  # Check every minute

async def worker_main():
    """Background worker for monitoring bot instances"""
    try:
        await monitor_instances()
    except KeyboardInterrupt:
        print("Worker stopped by user")
    except Exception as e:
        print(f'Worker error: {e}')
        await asyncio.sleep(30)  # Wait before retry

async def send_startup_notification():
    """Send startup confirmation notification via Telegram"""
    try:
        from config import settings
        from telegram import Bot
        from datetime import datetime
        
        token = settings.default_telegram_bot_token
        chat_id = settings.default_telegram_chat_id
        topic_id = settings.default_telegram_topic_id
        
        if not token or not chat_id:
            print("No Telegram configuration found for startup notification")
            return
        
        bot = Bot(token=token)
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        
        message = f"""📡 [Bot Starting...] - {timestamp}

🤖 TGL MEDUSA Worker Instance Started
🔁 Initializing monitoring system
🧠 Strategy: Multi-Instance Monitoring
💰 Ready to process bot instances

✅ System online and monitoring active."""
        
        send_params = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        if topic_id:
            send_params['message_thread_id'] = int(topic_id)
        
        await bot.send_message(**send_params)
        print("Startup notification sent successfully")
        
    except Exception as e:
        print(f"Failed to send startup notification: {e}")

if __name__ == '__main__':
    asyncio.run(worker_main())
