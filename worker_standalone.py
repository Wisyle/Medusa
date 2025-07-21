import asyncio
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from database import BotInstance, get_database_url
from polling import run_poller

def get_db_session():
    """Create database session for worker"""
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

async def monitor_instances():
    """Monitor and restart failed instances - standalone version"""
    print('TGL MEDUSA Worker Starting...')
    
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
    """Main worker function"""
    try:
        await monitor_instances()
    except KeyboardInterrupt:
        print("Worker stopped by user")
    except Exception as e:
        print(f"Worker error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(worker_main())
