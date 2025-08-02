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
        self.restart_count = 0
        self.max_restarts = 10  # Maximum restarts before giving up
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down strategy monitor worker gracefully...")
        self.running = False
        
        # Cancel all running tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
    
    async def run(self):
        """Main worker loop with improved restart logic"""
        logger.info("🚀 Starting Strategy Monitor Worker...")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        
        try:
            while self.running and self.restart_count < self.max_restarts:
                try:
                    # Start the main strategy monitor service
                    logger.info("🎯 Starting strategy monitor service...")
                    monitor_task = asyncio.create_task(run_all_strategy_monitors())
                    self.tasks.append(monitor_task)
                    
                    # Monitor the task and handle crashes
                    while self.running:
                        await asyncio.sleep(5)  # Check every 5 seconds
                        
                        if monitor_task.done():
                            exception = monitor_task.exception()
                            if exception:
                                self.restart_count += 1
                                logger.error(f"💥 Strategy monitor task crashed (restart #{self.restart_count}): {exception}")
                                
                                if self.restart_count >= self.max_restarts:
                                    logger.error(f"❌ Maximum restart limit ({self.max_restarts}) reached. Stopping worker.")
                                    self.running = False
                                    break
                                
                                # Wait before restarting
                                wait_time = min(60, 10 * self.restart_count)  # Exponential backoff, max 60s
                                logger.info(f"⏰ Waiting {wait_time} seconds before restart...")
                                await asyncio.sleep(wait_time)
                                
                                if self.running:
                                    logger.info(f"🔄 Restarting strategy monitor task (attempt #{self.restart_count + 1})...")
                                    monitor_task = asyncio.create_task(run_all_strategy_monitors())
                                    self.tasks.append(monitor_task)
                            else:
                                logger.warning("⚠️ Strategy monitor task completed normally (unexpected)")
                                break
                                
                except Exception as e:
                    self.restart_count += 1
                    logger.error(f"💥 Worker error (restart #{self.restart_count}): {e}")
                    
                    if self.restart_count >= self.max_restarts:
                        logger.error(f"❌ Maximum restart limit ({self.max_restarts}) reached. Stopping worker.")
                        break
                    
                    wait_time = min(60, 10 * self.restart_count)
                    logger.info(f"⏰ Waiting {wait_time} seconds before worker restart...")
                    await asyncio.sleep(wait_time)
            
            if self.restart_count >= self.max_restarts:
                logger.error("❌ Strategy monitor worker failed too many times and is shutting down")
            else:
                logger.info("✅ Strategy monitor worker stopped gracefully")
            
        except Exception as e:
            logger.error(f"💥 Fatal worker error: {e}")
        finally:
            # Clean up any remaining tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            logger.info("🧹 Strategy monitor worker cleanup completed")

async def main():
    worker = StrategyMonitorWorker()
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Strategy monitor worker interrupted by user")
    except Exception as e:
        logger.error(f"💥 Strategy monitor worker failed to start: {e}")
        sys.exit(1)
