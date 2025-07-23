#!/usr/bin/env python3
"""
Strategy Monitor Worker - Background service for running strategy monitors
"""

import asyncio
import signal
import sys
import logging
from datetime import datetime

from strategy_monitor import run_all_strategy_monitors

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StrategyMonitorWorker:
    def __init__(self):
        self.running = False
        self.tasks = []
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down strategy monitor worker...")
        self.running = False
        
        # Cancel all running tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
    
    async def run(self):
        """Main worker loop"""
        logger.info("Starting Strategy Monitor Worker...")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        
        try:
            # Start the main strategy monitor service
            monitor_task = asyncio.create_task(run_all_strategy_monitors())
            self.tasks.append(monitor_task)
            
            # Keep the worker running
            while self.running:
                await asyncio.sleep(1)
                
                # Check if monitor task died and restart if needed
                if monitor_task.done():
                    exception = monitor_task.exception()
                    if exception:
                        logger.error(f"Strategy monitor task crashed: {exception}")
                    else:
                        logger.info("Strategy monitor task completed normally")
                    
                    # Restart the monitor task
                    if self.running:
                        logger.info("Restarting strategy monitor task...")
                        monitor_task = asyncio.create_task(run_all_strategy_monitors())
                        self.tasks.append(monitor_task)
            
        except Exception as e:
            logger.error(f"Strategy monitor worker error: {e}")
        finally:
            logger.info("Strategy monitor worker stopped")

async def main():
    worker = StrategyMonitorWorker()
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Strategy monitor worker interrupted by user")
    except Exception as e:
        logger.error(f"Strategy monitor worker failed: {e}")
        sys.exit(1)
