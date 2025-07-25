#!/usr/bin/env python3
"""
Strategy Monitor System - Aggregates and reports on strategy performance
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from telegram import Bot

from database import SessionLocal, BotInstance, PollState, ActivityLog
from strategy_monitor_model import StrategyMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyMonitorService:
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.db = SessionLocal()
        self.monitor_config = self._load_monitor_config()
        self.telegram_bot = self._init_telegram() if self.monitor_config else None
        
    def _load_monitor_config(self) -> Optional[StrategyMonitor]:
        """Load monitor configuration for this strategy"""
        return self.db.query(StrategyMonitor).filter(
            StrategyMonitor.strategy_name == self.strategy_name,
            StrategyMonitor.is_active == True
        ).first()
    
    def _init_telegram(self) -> Optional[Bot]:
        """Initialize Telegram bot for strategy monitoring"""
        if not self.monitor_config or not self.monitor_config.telegram_bot_token:
            return None
        
        try:
            return Bot(token=self.monitor_config.telegram_bot_token)
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot for {self.strategy_name}: {e}")
            return None
    
    def _get_strategy_instances(self) -> List[BotInstance]:
        """Get all active instances running this strategy"""
        # Get all active instances and filter in Python for better compatibility
        all_instances = self.db.query(BotInstance).filter(BotInstance.is_active == True).all()
        
        strategy_instances = []
        for instance in all_instances:
            if instance.strategies and self.strategy_name in instance.strategies:
                strategy_instances.append(instance)
        
        return strategy_instances
    
    def _get_recent_positions(self, instance_ids: List[int], hours: int = 24) -> Dict[str, Any]:
        """Get recent position data for strategy instances"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        positions = self.db.query(PollState).filter(
            PollState.instance_id.in_(instance_ids),
            PollState.data_type == 'position',
            PollState.timestamp >= since
        ).order_by(desc(PollState.timestamp)).all()
        
        # Group by symbol and get latest position for each
        latest_positions = {}
        symbol_pnl = defaultdict(float)
        
        for pos in positions:
            symbol = pos.symbol
            if symbol not in latest_positions:
                latest_positions[symbol] = pos.data
                
                # Calculate PnL
                pnl = pos.data.get('unrealizedPnl', 0) if pos.data else 0
                if pnl:
                    symbol_pnl[symbol] += float(pnl)
        
        return {
            'positions': latest_positions,
            'symbol_pnl': dict(symbol_pnl),
            'total_pnl': sum(symbol_pnl.values())
        }
    
    def _get_recent_orders(self, instance_ids: List[int], hours: int = 24) -> Dict[str, Any]:
        """Get recent order data for strategy instances"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        orders = self.db.query(PollState).filter(
            PollState.instance_id.in_(instance_ids),
            PollState.data_type.like('order_%'),
            PollState.timestamp >= since
        ).order_by(desc(PollState.timestamp)).all()
        
        active_orders = []
        closed_orders = []
        total_volume = 0.0
        
        for order in orders:
            if order.data:
                status = order.data.get('status', 'unknown')
                amount = float(order.data.get('amount', 0) or 0)
                price = float(order.data.get('price', 0) or 0)
                
                if status in ['open', 'pending']:
                    active_orders.append(order.data)
                elif status in ['closed', 'filled', 'canceled']:
                    closed_orders.append(order.data)
                    if status == 'filled':
                        total_volume += amount * price
        
        return {
            'active_orders': active_orders,
            'closed_orders': closed_orders,
            'total_volume': total_volume,
            'total_orders': len(orders)
        }
    
    def _get_recent_trades(self, instance_ids: List[int], hours: int = 24) -> Dict[str, Any]:
        """Get recent trade data for strategy instances"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        trades = self.db.query(PollState).filter(
            PollState.instance_id.in_(instance_ids),
            PollState.data_type.like('trade_%'),
            PollState.timestamp >= since
        ).order_by(desc(PollState.timestamp)).all()
        
        total_trades = len(trades)
        total_volume = 0.0
        realized_pnl = 0.0
        
        for trade in trades:
            if trade.data:
                amount = float(trade.data.get('amount', 0) or 0)
                price = float(trade.data.get('price', 0) or 0)
                fee_cost = float(trade.data.get('fee', {}).get('cost', 0) or 0)
                
                total_volume += amount * price
                # Note: Realized PnL calculation would need more complex logic
                # This is a simplified version
        
        return {
            'trades': [t.data for t in trades[:10]],  # Last 10 trades
            'total_trades': total_trades,
            'total_volume': total_volume,
            'realized_pnl': realized_pnl
        }
    
    def _format_currency(self, amount: float) -> str:
        """Format currency with proper signs and decimals"""
        if amount == 0:
            return "0.00"
        elif abs(amount) >= 1000:
            return f"{amount:,.2f}"
        elif abs(amount) >= 1:
            return f"{amount:.2f}"
        else:
            return f"{amount:.4f}"
    
    def _format_percentage(self, value: float, reference: float = 100) -> str:
        """Format percentage with proper sign"""
        if reference == 0:
            return "0.00%"
        
        pct = (value / reference) * 100
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.2f}%"
    
    def _generate_report(self) -> str:
        """Generate comprehensive strategy report"""
        instances = self._get_strategy_instances()
        if not instances:
            return f"📊 **{self.strategy_name} Strategy Monitor**\\n\\nNo active instances found."
        
        instance_ids = [i.id for i in instances]
        instance_names = [i.name for i in instances]
        
        # Get data
        positions_data = self._get_recent_positions(instance_ids)
        orders_data = self._get_recent_orders(instance_ids)
        trades_data = self._get_recent_trades(instance_ids)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        report = f"""🎯 **{self.strategy_name} Strategy Monitor** - {timestamp}

📈 **Overview**
• **Active Instances:** {len(instances)}
• **Total PnL (24h):** ${self._format_currency(positions_data['total_pnl'])}
• **Active Positions:** {len(positions_data['positions'])}
• **Active Orders:** {len(orders_data['active_orders'])}
• **Trades (24h):** {trades_data['total_trades']}
• **Volume (24h):** ${self._format_currency(trades_data['total_volume'])}

🏢 **Instances**
"""
        
        for i, instance in enumerate(instances, 1):
            report += f"  {i}. `{instance.name}` - {instance.exchange}\n"
        
        # PnL Breakdown by Symbol
        if positions_data['symbol_pnl']:
            report += "\n💰 **PnL by Symbol (24h)**\n```\n"
            for symbol, pnl in sorted(positions_data['symbol_pnl'].items(), key=lambda x: x[1], reverse=True):
                pnl_formatted = self._format_currency(pnl)
                sign = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                report += f"{sign} {symbol:<15} ${pnl_formatted:>10}\n"
            report += "```\n"
        
        # Active Positions
        if positions_data['positions']:
            report += f"\n🎯 **Active Positions** ({len(positions_data['positions'])})\n```\n"
            for symbol, pos in list(positions_data['positions'].items())[:self.monitor_config.max_recent_positions]:
                side = pos.get('side', 'N/A')
                size = float(pos.get('contracts', 0) or 0)
                entry_price = float(pos.get('entryPrice', 0) or 0)
                unrealized_pnl = float(pos.get('unrealizedPnl', 0) or 0)
                
                side_emoji = "🟢" if side == 'long' else "🔴" if side == 'short' else "⚪"
                report += f"{side_emoji} {symbol:<12} {side:<5} {size:>8.4f} @${entry_price:>8.4f}\n"
                
            report += "```\n"
        
        # Recent Closed Orders
        if orders_data['closed_orders']:
            recent_closed = sorted(orders_data['closed_orders'], 
                                 key=lambda x: x.get('timestamp', 0), reverse=True)[:10]
            report += f"\n📋 **Recent Closed Orders** (Last 10)\n```\n"
            for order in recent_closed:
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A')
                amount = float(order.get('amount', 0) or 0)
                price = float(order.get('price', 0) or 0)
                status = order.get('status', 'N/A')
                
                side_emoji = "🟢" if side == 'buy' else "🔴" if side == 'sell' else "⚪"
                status_emoji = "✅" if status == 'filled' else "❌" if status == 'canceled' else "⏸️"
                
                report += f"{side_emoji}{status_emoji} {symbol:<12} {side:<4} {amount:>8.4f} @${price:>8.4f}\n"
            report += "```\n"
        
        # Recent Trades
        if trades_data['trades']:
            report += f"\n🔄 **Recent Trades** (Last 10)\n```\n"
            for trade in trades_data['trades'][:10]:
                symbol = trade.get('symbol', 'N/A')
                side = trade.get('side', 'N/A')
                amount = float(trade.get('amount', 0) or 0)
                price = float(trade.get('price', 0) or 0)
                
                side_emoji = "🟢" if side == 'buy' else "🔴" if side == 'sell' else "⚪"
                report += f"{side_emoji} {symbol:<12} {side:<4} {amount:>8.4f} @${price:>8.4f}\n"
            report += "```\n"
        
        report += f"\n📊 **Monitoring Active** | Next Report: {(datetime.now() + timedelta(seconds=self.monitor_config.report_interval)).strftime('%H:%M:%S')}"
        
        return report
    
    async def send_report(self):
        """Generate and send strategy report via Telegram"""
        if not self.monitor_config or not self.telegram_bot:
            logger.warning(f"Strategy monitor for {self.strategy_name} not configured or Telegram bot not available")
            return
        
        try:
            report = self._generate_report()
            
            send_params = {
                'chat_id': self.monitor_config.telegram_chat_id,
                'text': report,
                'parse_mode': 'Markdown'
            }
            
            if self.monitor_config.telegram_topic_id:
                send_params['message_thread_id'] = int(self.monitor_config.telegram_topic_id)
            
            await self.telegram_bot.send_message(**send_params)
            
            # Update last report time
            self.monitor_config.last_report = datetime.utcnow()
            self.monitor_config.last_error = None
            self.db.commit()
            
            logger.info(f"Strategy report sent for {self.strategy_name}")
            
        except Exception as e:
            error_msg = f"Failed to send strategy report: {e}"
            logger.error(f"Strategy monitor error for {self.strategy_name}: {error_msg}")
            
            # Update error status
            self.monitor_config.last_error = error_msg
            self.db.commit()
    
    def should_send_report(self) -> bool:
        """Check if it's time to send a report"""
        if not self.monitor_config:
            return False
        
        if not self.monitor_config.last_report:
            return True
        
        time_since_last = datetime.utcnow() - self.monitor_config.last_report
        return time_since_last.total_seconds() >= self.monitor_config.report_interval
    
    def close(self):
        """Clean up resources"""
        if self.db:
            self.db.close()

async def run_strategy_monitor(strategy_name: str):
    """Run strategy monitor for a specific strategy"""
    monitor = None
    logger.info(f"🎯 Starting strategy monitor for: {strategy_name}")
    
    while True:  # Outer restart loop
        try:
            monitor = StrategyMonitorService(strategy_name)
            
            # Check if monitor is properly configured
            if not monitor.monitor_config:
                logger.warning(f"Strategy monitor for {strategy_name} not configured, retrying in 60 seconds...")
                await asyncio.sleep(60)
                continue
            
            logger.info(f"✅ Strategy monitor initialized for {strategy_name}, checking every {monitor.monitor_config.report_interval} seconds")
            
            while True:  # Inner monitoring loop
                try:
                    if monitor.should_send_report():
                        logger.info(f"📊 Sending scheduled report for {strategy_name}")
                        await monitor.send_report()
                    
                    # Dynamic sleep based on report interval
                    # For intervals <= 5 minutes, check every 30 seconds
                    # For intervals <= 15 minutes, check every 60 seconds  
                    # For longer intervals, check every 5 minutes
                    sleep_time = 60  # Default
                    if monitor.monitor_config:
                        interval = monitor.monitor_config.report_interval
                        if interval <= 300:  # 5 minutes or less
                            sleep_time = 30
                        elif interval <= 900:  # 15 minutes or less
                            sleep_time = 60
                        else:
                            sleep_time = min(300, interval // 4)  # Check 4 times per interval, max 5 minutes
                    
                    await asyncio.sleep(sleep_time)
                    
                except Exception as e:
                    logger.error(f"Strategy monitor error for {strategy_name}: {e}")
                    # Update error status in database
                    if monitor and monitor.monitor_config:
                        try:
                            monitor.monitor_config.last_error = str(e)
                            monitor.db.commit()
                        except:
                            pass
                    await asyncio.sleep(60)  # Wait before retrying
                
        except Exception as e:
            logger.error(f"Strategy monitor for {strategy_name} crashed, restarting in 60 seconds: {e}")
            await asyncio.sleep(60)  # Wait before full restart
        finally:
            if monitor:
                try:
                    monitor.close()
                except:
                    pass
                monitor = None

async def run_all_strategy_monitors():
    """Run monitors for all configured strategies with proper task management"""
    logger.info("🚀 Starting all strategy monitors...")
    running_tasks = {}
    
    while True:
        try:
            db = SessionLocal()
            try:
                active_monitors = db.query(StrategyMonitor).filter(StrategyMonitor.is_active == True).all()
                
                # Get currently configured strategy names
                configured_strategies = {monitor.strategy_name for monitor in active_monitors}
                
                # Stop monitors that are no longer configured or active
                for strategy_name in list(running_tasks.keys()):
                    if strategy_name not in configured_strategies:
                        logger.info(f"🛑 Stopping monitor for removed/deactivated strategy: {strategy_name}")
                        running_tasks[strategy_name].cancel()
                        del running_tasks[strategy_name]
                
                # Start monitors for new or restarted strategies
                for monitor in active_monitors:
                    strategy_name = monitor.strategy_name
                    
                    # Check if task is running
                    if strategy_name not in running_tasks or running_tasks[strategy_name].done():
                        if strategy_name in running_tasks:
                            # Log why previous task stopped
                            task = running_tasks[strategy_name]
                            if task.exception():
                                logger.error(f"🔄 Restarting monitor for {strategy_name} - previous task failed: {task.exception()}")
                            else:
                                logger.warning(f"🔄 Restarting monitor for {strategy_name} - previous task completed unexpectedly")
                        else:
                            logger.info(f"🎯 Starting new monitor for: {strategy_name}")
                        
                        # Start new task
                        task = asyncio.create_task(run_strategy_monitor(strategy_name))
                        running_tasks[strategy_name] = task
                
                # Log status
                if not running_tasks:
                    logger.info("💤 No active strategy monitors configured")
                else:
                    active_count = sum(1 for task in running_tasks.values() if not task.done())
                    logger.info(f"📊 Running {active_count}/{len(running_tasks)} strategy monitors")
                
            finally:
                db.close()
            
            # Check task status and wait
            await asyncio.sleep(30)  # Check every 30 seconds for configuration changes
            
        except Exception as e:
            logger.error(f"Failed to manage strategy monitors: {e}")
            await asyncio.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    asyncio.run(run_all_strategy_monitors())
