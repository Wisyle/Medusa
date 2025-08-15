import asyncio
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import BotInstance, get_database_url
from services.polling import run_poller
from utils.init_strategy_monitor import initialize_strategy_monitor_system
import psutil

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

def get_memory_usage():
    """Get current memory usage of the worker process"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        return f"{memory_info.rss / 1024 / 1024:.1f} MB"
    except:
        return "N/A"

async def monitor_instances():
    """Monitor and restart failed instances - consolidated worker"""
    print('🚀 TAR Lighthouse Consolidated Worker Starting...')
    print('📊 This worker handles:')
    print('  - Bot instance monitoring and polling')
    print('  - Strategy monitor execution')
    print('  - Balance history tracking')
    print('  - Trade monitoring and logging')
    print('  - All console log aggregation')
    
    # Initialize Strategy Monitor System
    print('🎯 Initializing Strategy Monitor System...')
    initialize_strategy_monitor_system()
    
    await send_startup_notification()
    
    # Import strategy monitor functions
    try:
        from services.strategy_monitor import run_all_strategy_monitors
        strategy_monitors_available = True
        print('✅ Strategy monitors loaded successfully')
    except ImportError as e:
        print(f'⚠️ Strategy monitors not available: {e}')
        strategy_monitors_available = False
    
    # Task counters
    iteration = 0
    
    while True:
        iteration += 1
        print(f"\n--- Worker Iteration {iteration} - {asyncio.get_event_loop().time()} ---")
        
        try:
            db = get_db_session()
            
            # 1. Monitor Bot Instances
            active_instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
            print(f"📤 Found {len(active_instances)} active bot instances")
            
            for instance in active_instances:
                try:
                    print(f"  ↳ Processing: {instance.name} (ID: {instance.id})")
                    await run_poller(instance.id)
                except Exception as e:
                    print(f"  ❌ Error with {instance.name}: {e}")
            
            # 2. Run Strategy Monitors (every 5 iterations = 5 minutes)
            if strategy_monitors_available and iteration % 5 == 0:
                try:
                    print(f"\n🎯 Running strategy monitors...")
                    await run_all_strategy_monitors()
                except Exception as e:
                    print(f"❌ Strategy monitor error: {e}")
            
            # 3. Log system health
            if iteration % 10 == 0:  # Every 10 minutes
                print(f"\n💚 System Health Check:")
                print(f"  - Worker uptime: {iteration} minutes")
                print(f"  - Active instances: {len(active_instances)}")
                print(f"  - Database connection: OK")
                print(f"  - Memory usage: {get_memory_usage()}")
            
            db.close()
            
        except Exception as e:
            print(f"❌ Worker error: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait before next iteration
        print(f"⏳ Waiting 60 seconds before next check...")
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
