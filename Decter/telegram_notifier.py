"""
Enhanced Telegram Notification Module for Decter Trading System
Provides structured trade alerts and daily summary reports
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Enhanced Telegram notification system with structured trade alerts and reporting
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config = self._load_config()
        self.notification_queue = []
        
        logger.info("📱 Telegram Notifier initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load Telegram configuration"""
        try:
            # Load from web interface config
            config_file = self.data_dir / "telegram_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"❌ Error loading Telegram config: {e}")
            return {}
    
    async def send_trade_notification(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send structured trade notification to Telegram
        
        Args:
            trade_data: Dictionary containing trade information
                - action: 'open', 'close', 'fail'
                - asset_pair: e.g., 'R_10'
                - direction: 'Long' or 'Short'
                - entry_price: float
                - exit_price: float (for close actions)
                - pnl: float
                - timestamp: datetime
                - reason: string explanation
                - engine: 'continuous' or 'decision'
        """
        try:
            if not self._is_configured():
                return {"success": False, "message": "Telegram not configured"}
            
            message = self._format_trade_message(trade_data)
            result = await self._send_message(message)
            
            # Log the trade notification
            await self._log_notification(trade_data, message, result.get("success", False))
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending trade notification: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _format_trade_message(self, trade_data: Dict[str, Any]) -> str:
        """Format trade data into structured Telegram message"""
        try:
            action = trade_data.get("action", "unknown").upper()
            asset_pair = trade_data.get("asset_pair", "N/A")
            direction = trade_data.get("direction", "N/A")
            entry_price = trade_data.get("entry_price", 0)
            exit_price = trade_data.get("exit_price", 0)
            pnl = trade_data.get("pnl", 0)
            reason = trade_data.get("reason", "N/A")
            engine = trade_data.get("engine", "N/A")
            timestamp = trade_data.get("timestamp", datetime.now())
            
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Determine emoji and color based on action and PnL
            if action == "OPEN":
                emoji = "🔵"
                color = "BLUE"
            elif action == "CLOSE":
                if pnl > 0:
                    emoji = "🟢"
                    color = "GREEN"
                elif pnl < 0:
                    emoji = "🔴"
                    color = "RED"
                else:
                    emoji = "⚪"
                    color = "WHITE"
            elif action == "FAIL":
                emoji = "❌"
                color = "RED"
            else:
                emoji = "⚫"
                color = "GRAY"
            
            # Format timestamp
            time_str = timestamp.strftime("%H:%M:%S")
            date_str = timestamp.strftime("%Y-%m-%d")
            
            # Build structured message with code formatting
            message = f"{emoji} **Decter Engine (ACCU) - {action}**\n\n"
            
            # Trade details in code block for clean formatting
            message += "```\n"
            message += f"Asset:      {asset_pair}\n"
            message += f"Direction:  {direction}\n"
            message += f"Entry:      {entry_price:.6f}\n"
            
            if action == "CLOSE" and exit_price:
                message += f"Exit:       {exit_price:.6f}\n"
                pnl_sign = "+" if pnl >= 0 else ""
                message += f"PnL:        {pnl_sign}{pnl:.2f}\n"
            
            message += f"Time:       {time_str} ({date_str})\n"
            message += f"Engine:     {engine.title()}\n"
            message += f"Reason:     {reason}\n"
            message += "```\n"
            
            # Add summary footer
            if action == "CLOSE":
                pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➡️"
                message += f"\n{pnl_emoji} Trade {color}: {pnl_sign}${abs(pnl):.2f}"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting trade message: {e}")
            return f"🤖 **Decter Engine (ACCU)**\n\nTrade notification error: {str(e)}"
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send daily summary report to Telegram
        
        Args:
            summary_data: Dictionary containing daily summary
                - date: date string
                - total_trades: int
                - wins: int
                - losses: int
                - net_pnl: float
                - win_rate: float
                - profit_factor: float
                - best_trade: float
                - worst_trade: float
                - active_currency: string
                - engine_stats: dict
        """
        try:
            if not self._is_configured():
                return {"success": False, "message": "Telegram not configured"}
            
            message = self._format_daily_summary(summary_data)
            result = await self._send_message(message)
            
            # Log the summary notification
            await self._log_notification({"type": "daily_summary", **summary_data}, message, result.get("success", False))
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending daily summary: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _format_daily_summary(self, summary_data: Dict[str, Any]) -> str:
        """Format daily summary into structured Telegram message"""
        try:
            date = summary_data.get("date", datetime.now().strftime("%Y-%m-%d"))
            total_trades = summary_data.get("total_trades", 0)
            wins = summary_data.get("wins", 0)
            losses = summary_data.get("losses", 0)
            net_pnl = summary_data.get("net_pnl", 0)
            win_rate = summary_data.get("win_rate", 0)
            profit_factor = summary_data.get("profit_factor", 0)
            best_trade = summary_data.get("best_trade", 0)
            worst_trade = summary_data.get("worst_trade", 0)
            active_currency = summary_data.get("active_currency", "XRP")
            engine_stats = summary_data.get("engine_stats", {})
            
            # Determine overall performance emoji
            if net_pnl > 0:
                performance_emoji = "🎉"
                performance_text = "PROFITABLE"
            elif net_pnl < 0:
                performance_emoji = "⚠️"
                performance_text = "LOSS"
            else:
                performance_emoji = "➡️"
                performance_text = "BREAKEVEN"
            
            # Build summary message
            message = f"{performance_emoji} **Decter Engine (ACCU) - Daily Summary**\n\n"
            message += f"📅 **{date}** | Currency: **{active_currency}**\n\n"
            
            # Performance summary in code block
            message += "```\n"
            message += "PERFORMANCE SUMMARY\n"
            message += "==================\n"
            message += f"Total Trades:    {total_trades}\n"
            message += f"Wins:           {wins} ({win_rate:.1f}%)\n"
            message += f"Losses:         {losses}\n"
            
            pnl_sign = "+" if net_pnl >= 0 else ""
            message += f"Net PnL:        {pnl_sign}${net_pnl:.2f}\n"
            message += f"Profit Factor:   {profit_factor:.2f}\n"
            message += f"Best Trade:     +${best_trade:.2f}\n"
            message += f"Worst Trade:    -${abs(worst_trade):.2f}\n"
            message += "```\n"
            
            # Engine statistics if available
            if engine_stats:
                message += "\n📊 **Engine Statistics:**\n```\n"
                
                continuous_stats = engine_stats.get("continuous", {})
                if continuous_stats:
                    message += f"Continuous Engine:\n"
                    message += f"  Status:        {continuous_stats.get('status', 'Unknown')}\n"
                    message += f"  Risk Level:    {continuous_stats.get('risk_level', 'Normal')}\n"
                    message += f"  Win Streak:    {continuous_stats.get('consecutive_wins', 0)}\n"
                
                decision_stats = engine_stats.get("decision", {})
                if decision_stats:
                    message += f"\nDecision Engine:\n"
                    message += f"  Status:        {decision_stats.get('status', 'Unknown')}\n"
                    message += f"  Recovery Mode: {'Yes' if decision_stats.get('recovery_mode') else 'No'}\n"
                    if decision_stats.get("selected_asset"):
                        message += f"  Asset:         {decision_stats.get('selected_asset')}\n"
                
                message += "```\n"
            
            # Performance footer
            message += f"\n🎯 **{performance_text}**: {pnl_sign}${abs(net_pnl):.2f}"
            
            if total_trades > 0:
                avg_per_trade = net_pnl / total_trades
                avg_sign = "+" if avg_per_trade >= 0 else ""
                message += f" | Avg/Trade: {avg_sign}${avg_per_trade:.2f}"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting daily summary: {e}")
            return f"🤖 **Decter Engine (ACCU)**\n\nDaily summary error: {str(e)}"
    
    async def send_engine_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send engine state change alerts
        
        Args:
            alert_data: Dictionary containing alert information
                - engine: 'continuous' or 'decision'
                - event: 'started', 'stopped', 'risk_reduced', 'recovery_entered', etc.
                - details: additional context
        """
        try:
            if not self._is_configured():
                return {"success": False, "message": "Telegram not configured"}
            
            message = self._format_engine_alert(alert_data)
            result = await self._send_message(message)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending engine alert: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _format_engine_alert(self, alert_data: Dict[str, Any]) -> str:
        """Format engine alert into Telegram message"""
        try:
            engine = alert_data.get("engine", "unknown").title()
            event = alert_data.get("event", "unknown")
            details = alert_data.get("details", {})
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Determine emoji based on event
            event_emojis = {
                "started": "🟢",
                "stopped": "🔴", 
                "risk_reduced": "🔻",
                "recovery_entered": "🚨",
                "recovery_exited": "✅",
                "profit_cap_reached": "🛑",
                "asset_switched": "🔄"
            }
            
            emoji = event_emojis.get(event, "⚪")
            
            message = f"{emoji} **Decter Engine Alert**\n\n"
            message += f"**{engine} Engine** - {event.replace('_', ' ').title()}\n"
            message += f"Time: {timestamp}\n\n"
            
            if details:
                message += "```\n"
                for key, value in details.items():
                    formatted_key = key.replace('_', ' ').title()
                    message += f"{formatted_key}: {value}\n"
                message += "```"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting engine alert: {e}")
            return f"🤖 **Decter Engine Alert**\n\nAlert formatting error: {str(e)}"
    
    async def _send_message(self, message: str) -> Dict[str, Any]:
        """Send message to Telegram"""
        try:
            bot_token = self.config.get("telegram_bot_token")
            group_id = self.config.get("telegram_group_id")
            topic_id = self.config.get("telegram_topic_id")
            
            if not bot_token or not group_id:
                return {"success": False, "message": "Telegram credentials not configured"}
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                "chat_id": group_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            if topic_id:
                payload["message_thread_id"] = int(topic_id)
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Telegram message sent successfully")
                return {"success": True, "message": "Message sent successfully"}
            else:
                error_msg = f"Telegram API error: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                return {"success": False, "message": error_msg}
                
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return {"success": False, "message": f"Send error: {str(e)}"}
    
    def _is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(
            self.config.get("telegram_bot_token") and 
            self.config.get("telegram_group_id")
        )
    
    async def _log_notification(self, data: Dict[str, Any], message: str, success: bool) -> None:
        """Log notification attempt for debugging"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "data": data,
                "message_length": len(message),
                "success": success
            }
            
            log_file = self.data_dir / "telegram_notifications.log"
            
            # Keep only last 100 log entries
            logs = []
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        logs = json.load(f)
                    logs = logs[-99:]  # Keep last 99, add 1 new = 100 total
                except:
                    logs = []
            
            logs.append(log_entry)
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error logging notification: {e}")
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""
        try:
            log_file = self.data_dir / "telegram_notifications.log"
            if not log_file.exists():
                return {"total": 0, "successful": 0, "failed": 0, "success_rate": 0}
            
            with open(log_file, 'r') as f:
                logs = json.load(f)
            
            total = len(logs)
            successful = sum(1 for log in logs if log.get("success"))
            failed = total - successful
            success_rate = (successful / total * 100) if total > 0 else 0
            
            return {
                "total": total,
                "successful": successful,
                "failed": failed,
                "success_rate": success_rate,
                "last_24h": len([log for log in logs if self._is_within_24h(log.get("timestamp"))])
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting notification stats: {e}")
            return {"error": str(e)}
    
    def _is_within_24h(self, timestamp_str: Optional[str]) -> bool:
        """Check if timestamp is within last 24 hours"""
        if not timestamp_str:
            return False
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            return (datetime.now() - timestamp) <= timedelta(hours=24)
        except:
            return False

# Global instance
telegram_notifier: Optional[TelegramNotifier] = None

def get_telegram_notifier(data_dir: Path) -> TelegramNotifier:
    """Get or create telegram notifier instance"""
    global telegram_notifier
    if telegram_notifier is None:
        telegram_notifier = TelegramNotifier(data_dir)
    return telegram_notifier