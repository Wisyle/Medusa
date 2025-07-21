import asyncio
import time
from main import monitor_instances

async def worker_main():
    """Background worker for monitoring bot instances"""
    print('TGL Medusa Loggers Worker Starting...')
    while True:
        try:
            await monitor_instances()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            print(f'Worker error: {e}')
            await asyncio.sleep(30)  # Wait before retry

if __name__ == '__main__':
    asyncio.run(worker_main())
