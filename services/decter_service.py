#!/usr/bin/env python3
"""
Decter Engine Service - Manages Decter trading bot instances
Runs as a dedicated worker service
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.decter_controller import DecterController, DecterStatus
from app.database import SessionLocal, BotInstance

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DecterService:
    def __init__(self):
        self.running = True
        self.controllers = {}  # instance_id -> DecterController
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down Decter service...")
        self.running = False
        
        # Stop all controllers
        for instance_id, controller in self.controllers.items():
            try:
                if controller.is_running():
                    logger.info(f"Stopping Decter controller for instance {instance_id}")
                    controller.stop()
            except Exception as e:
                logger.error(f"Error stopping controller {instance_id}: {e}")
    
    async def monitor_decter_instances(self):
        """Monitor database for Decter instances and manage controllers"""
        while self.running:
            try:
                db = SessionLocal()
                
                # Find all active Decter instances
                decter_instances = db.query(BotInstance).filter(
                    BotInstance.is_active == True,
                    BotInstance.exchange == "deriv"  # Decter uses Deriv
                ).all()
                
                logger.info(f"Found {len(decter_instances)} active Decter instances")
                
                # Start controllers for new instances
                for instance in decter_instances:
                    if instance.id not in self.controllers:
                        logger.info(f"Starting Decter controller for instance {instance.id}: {instance.name}")
                        try:
                            controller = DecterController()
                            self.controllers[instance.id] = controller
                            
                            # Configure and start if needed
                            config = instance.config or {}
                            if config.get('auto_start', False):
                                controller.start(config)
                        except Exception as e:
                            logger.error(f"Failed to start controller for instance {instance.id}: {e}")
                
                # Stop controllers for inactive instances
                active_ids = {i.id for i in decter_instances}
                to_remove = []
                
                for instance_id, controller in self.controllers.items():
                    if instance_id not in active_ids:
                        logger.info(f"Stopping Decter controller for inactive instance {instance_id}")
                        try:
                            if controller.is_running():
                                controller.stop()
                            to_remove.append(instance_id)
                        except Exception as e:
                            logger.error(f"Error stopping controller {instance_id}: {e}")
                
                # Remove stopped controllers
                for instance_id in to_remove:
                    del self.controllers[instance_id]
                
                # Update status for all controllers
                for instance_id, controller in self.controllers.items():
                    try:
                        status = controller.get_status()
                        logger.debug(f"Instance {instance_id} status: {status['status']}")
                        
                        # Log to console for monitoring
                        if status['status'] == 'trading':
                            stats = status.get('stats', {})
                            logger.info(f"Decter {instance_id} - Trades: {stats.get('total_trades', 0)}, "
                                      f"Win Rate: {stats.get('win_rate', 0):.1f}%, "
                                      f"Daily P&L: ${stats.get('daily_profit', 0):.2f}")
                    except Exception as e:
                        logger.error(f"Error updating status for instance {instance_id}: {e}")
                
                db.close()
                
            except Exception as e:
                logger.error(f"Error in Decter monitoring loop: {e}")
            
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def run(self):
        """Main service loop"""
        logger.info("🤖 Decter Engine Service starting...")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Run the monitoring loop
            await self.monitor_decter_instances()
        except Exception as e:
            logger.error(f"Fatal error in Decter service: {e}")
        finally:
            logger.info("🛑 Decter Engine Service stopped")

async def main():
    """Entry point for the Decter service"""
    service = DecterService()
    await service.run()

if __name__ == "__main__":
    asyncio.run(main())
