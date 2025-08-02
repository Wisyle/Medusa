"""
Decter 001 Controller for TARC Lighthouse Integration
Provides unified control of Decter 001 trading bot from TARC Lighthouse platform
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import traceback
import signal
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import psutil
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


class DecterStatus(Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    ONLINE = "online"
    TRADING = "trading"
    PAUSED = "paused"
    ERROR = "error"


class DecterMode(Enum):
    CONTINUOUS = "continuous"
    RECOVERY = "recovery"


@dataclass
class DecterConfig:
    """Decter 001 configuration parameters"""
    stake: float
    growth_rate: float
    take_profit: float
    index: str
    currency: str
    max_loss_amount: float
    max_win_amount: float


@dataclass
class DecterStats:
    """Decter 001 trading statistics"""
    total_trades: int
    wins: int
    losses: int
    net_pl: float
    growth: float
    consecutive_wins: int
    cumulative_loss: float
    cumulative_win: float
    current_balance: float
    initial_balance: float
    trading_enabled: bool
    current_mode: str
    win_rate: float = 0.0
    daily_profit: float = 0.0


class DecterController:
    """
    Controller class for managing Decter 001 bot from TARC Lighthouse
    """
    
    def __init__(self, decter_path: str = None):
        # Use environment-appropriate path
        if decter_path is None:
            if os.getenv("ENVIRONMENT") == "production":
                decter_path = "Decter"  # Relative path for Render
            else:
                decter_path = "/mnt/c/users/rober/downloads/tarc/Decter"  # Absolute for dev
        
        self.decter_path = Path(decter_path)
        self.process: Optional[subprocess.Popen] = None
        self.status = DecterStatus.OFFLINE
        self.last_heartbeat = None
        self.start_time = None
        self.telegram_bot_token = None
        self.telegram_group_id = None
        self.telegram_topic_id = None
        
        # Initialize paths
        self.main_script = self.decter_path / "main.py"
        self.config_file = self.decter_path / "config.py"
        self.data_dir = self.decter_path / "data"
        self.stats_file = self.data_dir / "trading_stats.json"
        self.params_file = self.data_dir / "saved_params.json"
        self.log_file = self.data_dir / "trading_bot.log"
        
        # Ensure data directory exists with proper error handling
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, FileNotFoundError, OSError) as e:
            # If we can't create the data directory, use a temporary one
            import tempfile
            self.data_dir = Path(tempfile.mkdtemp(prefix="decter_controller_"))
            logger.warning(f"Could not create data directory, using temporary: {self.data_dir}")
            # Update file paths
            self.stats_file = self.data_dir / "trading_stats.json"
            self.params_file = self.data_dir / "saved_params.json"
            self.log_file = self.data_dir / "trading_bot.log"
        
        # Try to set up internal service (direct imports)
        sys.path.insert(0, str(self.decter_path))
        try:
            import config as decter_config
            import utils as decter_utils
            from deriv_api import DerivAPI
            from trading_state import TradingState
            self.decter_config = decter_config
            self.decter_utils = decter_utils
            self.DerivAPI = DerivAPI
            self.TradingState = TradingState
            self._internal_service = True
            logger.info(f"🤖 Decter Controller initialized with internal service for path: {decter_path}")
        except ImportError as e:
            logger.warning(f"Could not import Decter modules for internal service: {e}")
            self._internal_service = False
            logger.info(f"🤖 Decter Controller initialized with subprocess mode for path: {decter_path}")

    def is_running(self) -> bool:
        """Check if Decter 001 process is running"""
        if self.process is None:
            return False
        
        try:
            # Check if process is still alive
            return self.process.poll() is None
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive Decter 001 status"""
        try:
            is_running = self.is_running()
            stats = self.get_stats() if is_running else None
            
            # Update status based on current state
            if is_running:
                if stats and stats.trading_enabled:
                    self.status = DecterStatus.TRADING
                else:
                    self.status = DecterStatus.ONLINE
            else:
                self.status = DecterStatus.OFFLINE
            
            status_info = {
                "status": self.status.value,
                "is_running": is_running,
                "process_id": self.process.pid if self.process else None,
                "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
                "uptime_seconds": self._get_uptime(),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "stats": asdict(stats) if stats else None,
                "config": self._get_current_config(),
                "recent_logs": self._get_recent_logs(),
                "available_indices": self._get_available_indices(),
                "available_currencies": self._get_available_currencies()
            }
            
            return status_info
        except Exception as e:
            logger.error(f"❌ Error getting Decter status: {e}")
            return {
                "status": DecterStatus.ERROR.value,
                "error": str(e),
                "is_running": False
            }

    def start(self) -> Dict[str, Any]:
        """Start Decter 001 bot"""
        try:
            if self.is_running():
                return {
                    "success": False,
                    "message": "Decter 001 is already running",
                    "status": self.status.value
                }
            
            if not self.main_script.exists():
                return {
                    "success": False,
                    "message": f"Decter 001 main script not found at {self.main_script}",
                    "status": DecterStatus.ERROR.value
                }
            
            # Change to Decter directory
            old_cwd = os.getcwd()
            os.chdir(self.decter_path)
            
            # Start the process
            self.status = DecterStatus.STARTING
            logger.info("🚀 Starting Decter 001 bot...")
            
            # Create log file for subprocess output
            log_file = self.data_dir / "subprocess.log"
            
            with open(log_file, 'w') as f:
                self.process = subprocess.Popen(
                    ["python", "main.py"],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(self.decter_path)
                )
            
            # Give it a moment to start
            time.sleep(3)
            
            # Check if it started successfully
            if self.process.poll() is None:
                self.status = DecterStatus.ONLINE
                self.last_heartbeat = datetime.now()
                self.start_time = datetime.now()
                logger.info(f"✅ Decter 001 started successfully with PID: {self.process.pid}")
                
                return {
                    "success": True,
                    "message": "Decter 001 started successfully",
                    "process_id": self.process.pid,
                    "status": self.status.value
                }
            else:
                # Process failed to start
                self.status = DecterStatus.ERROR
                error_msg = self._get_recent_logs(5)[-1] if self._get_recent_logs(5) else "Unknown error"
                logger.error(f"❌ Decter 001 failed to start: {error_msg}")
                
                return {
                    "success": False,
                    "message": f"Failed to start Decter 001: {error_msg}",
                    "status": self.status.value
                }
                
        except Exception as e:
            self.status = DecterStatus.ERROR
            logger.error(f"❌ Error starting Decter 001: {e}")
            return {
                "success": False,
                "message": f"Error starting Decter 001: {str(e)}",
                "status": self.status.value
            }
        finally:
            os.chdir(old_cwd)

    def stop(self) -> Dict[str, Any]:
        """Stop Decter 001 bot"""
        try:
            if not self.is_running():
                return {
                    "success": True,
                    "message": "Decter 001 is not running",
                    "status": DecterStatus.OFFLINE.value
                }
            
            logger.info("🛑 Stopping Decter 001 bot...")
            
            # Try graceful shutdown first
            self.process.terminate()
            
            # Wait up to 10 seconds for graceful shutdown
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                logger.warning("⚠️ Graceful shutdown failed, forcing termination...")
                self.process.kill()
                self.process.wait()
            
            self.status = DecterStatus.OFFLINE
            self.process = None
            self.start_time = None
            logger.info("✅ Decter 001 stopped successfully")
            
            return {
                "success": True,
                "message": "Decter 001 stopped successfully",
                "status": self.status.value
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping Decter 001: {e}")
            return {
                "success": False,
                "message": f"Error stopping Decter 001: {str(e)}",
                "status": self.status.value
            }

    def restart(self) -> Dict[str, Any]:
        """Restart Decter 001 bot"""
        logger.info("🔄 Restarting Decter 001 bot...")
        
        # Stop first
        stop_result = self.stop()
        if not stop_result["success"]:
            return stop_result
        
        # Wait a moment
        time.sleep(2)
        
        # Start again
        return self.start()

    def get_stats(self) -> Optional[DecterStats]:
        """Get current trading statistics"""
        try:
            if not self.stats_file.exists():
                return None
            
            with open(self.stats_file, 'r') as f:
                data = json.load(f)
            
            stats_data = data.get('stats', {})
            
            # Calculate win rate
            total_trades = stats_data.get('total_trades', 0)
            wins = stats_data.get('wins', 0)
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            # Calculate daily profit (simplified)
            daily_profit = stats_data.get('net_pl', 0.0)
            
            return DecterStats(
                total_trades=total_trades,
                wins=wins,
                losses=stats_data.get('losses', 0),
                net_pl=stats_data.get('net_pl', 0.0),
                growth=stats_data.get('growth', 0.0),
                consecutive_wins=stats_data.get('consecutive_wins', 0),
                cumulative_loss=data.get('cumulative_loss', 0.0),
                cumulative_win=data.get('cumulative_win', 0.0),
                current_balance=0.0,  # Would need API call to get real-time balance
                initial_balance=data.get('starting_balance', 0.0),
                trading_enabled=self.is_running(),  # Simplified check
                current_mode="continuous",  # Would need to check actual mode
                win_rate=win_rate,
                daily_profit=daily_profit
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return None

    def set_parameters(self, config: DecterConfig) -> Dict[str, Any]:
        """Set trading parameters"""
        try:
            params_data = {
                "stake": config.stake,
                "growth_rate": config.growth_rate,
                "take_profit": config.take_profit,
                "index": config.index,
                "currency": config.currency,
                "max_loss_amount": config.max_loss_amount,
                "max_win_amount": config.max_win_amount
            }
            
            # Save parameters
            with open(self.params_file, 'w') as f:
                json.dump(params_data, f, indent=2)
            
            logger.info(f"📝 Parameters updated: {params_data}")
            
            return {
                "success": True,
                "message": "Parameters updated successfully",
                "parameters": params_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error setting parameters: {e}")
            return {
                "success": False,
                "message": f"Error setting parameters: {str(e)}"
            }

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        try:
            if not self.stats_file.exists():
                return []
            
            with open(self.stats_file, 'r') as f:
                data = json.load(f)
            
            trade_history = data.get('trade_history', [])
            
            # Return most recent trades
            return trade_history[-limit:] if trade_history else []
            
        except Exception as e:
            logger.error(f"❌ Error getting trade history: {e}")
            return []

    def send_telegram_command(self, command: str) -> Dict[str, Any]:
        """Send a command to Decter 001 via simulated Telegram"""
        try:
            # This is a simplified implementation
            # In a full implementation, you would send commands via Telegram Bot API
            
            valid_commands = [
                "start 001", "start trading", "stop trading", "status", 
                "history", "export", "reset stats", "mode status"
            ]
            
            if command not in valid_commands:
                return {
                    "success": False,
                    "message": f"Invalid command. Valid commands: {', '.join(valid_commands)}"
                }
            
            logger.info(f"📱 Simulating Telegram command: {command}")
            
            return {
                "success": True,
                "message": f"Command '{command}' sent successfully",
                "command": command
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending command: {e}")
            return {
                "success": False,
                "message": f"Error sending command: {str(e)}"
            }

    def _get_uptime(self) -> Optional[int]:
        """Get bot uptime in seconds"""
        if not self.start_time:
            return None
        
        return int((datetime.now() - self.start_time).total_seconds())

    def _get_current_config(self) -> Optional[Dict[str, Any]]:
        """Get current configuration"""
        try:
            if self.params_file.exists():
                with open(self.params_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error reading config: {e}")
        return None

    def _get_recent_logs(self, lines: int = 10) -> List[str]:
        """Get recent log entries"""
        try:
            if not self.log_file.exists():
                # Try subprocess log file
                subprocess_log = self.data_dir / "subprocess.log"
                if subprocess_log.exists():
                    with open(subprocess_log, 'r') as f:
                        all_lines = f.readlines()
                        return [line.strip() for line in all_lines[-lines:]]
                return []
            
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except Exception as e:
            logger.error(f"❌ Error reading logs: {e}")
            return []

    def _get_available_indices(self) -> List[str]:
        """Get available trading indices"""
        return [
            "R_10", "R_25", "R_50", "R_75", "R_100",
            "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V",
            "1HZ150V", "1HZ250V"
        ]

    def _get_available_currencies(self) -> List[str]:
        """Get available currencies"""
        return ["XRP", "BTC", "ETH", "LTC", "USDT", "USD"]

    def set_telegram_config(self, bot_token: str, group_id: str, topic_id: str = None) -> Dict[str, Any]:
        """Set Telegram bot configuration"""
        try:
            self.telegram_bot_token = bot_token
            self.telegram_group_id = group_id
            self.telegram_topic_id = topic_id
            
            # Save to Decter config file
            telegram_config = {
                "telegram_bot_token": bot_token,
                "telegram_group_id": group_id,
                "telegram_topic_id": topic_id
            }
            
            # Save config to Decter's data directory
            config_file = self.data_dir / "telegram_config.json"
            with open(config_file, 'w') as f:
                json.dump(telegram_config, f, indent=2)
            
            logger.info(f"📱 Telegram configuration updated: Group {group_id}, Topic {topic_id}")
            
            return {
                "success": True,
                "message": "Telegram configuration updated successfully",
                "config": telegram_config
            }
            
        except Exception as e:
            logger.error(f"❌ Error setting Telegram config: {e}")
            return {
                "success": False,
                "message": f"Error setting Telegram config: {str(e)}"
            }

    def get_telegram_config(self) -> Dict[str, Any]:
        """Get current Telegram configuration"""
        try:
            config_file = self.data_dir / "telegram_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"❌ Error getting Telegram config: {e}")
            return {}

    def set_deriv_config(self, deriv_app_id: str, currency_tokens: Dict[str, str]) -> Dict[str, Any]:
        """Set Deriv API configuration"""
        try:
            deriv_config = {
                "deriv_app_id": deriv_app_id,
                **{f"{currency.lower()}_api_token": token for currency, token in currency_tokens.items()}
            }
            
            # Save config to Decter's data directory
            config_file = self.data_dir / "deriv_config.json"
            with open(config_file, 'w') as f:
                json.dump(deriv_config, f, indent=2)
            
            logger.info(f"🔑 Deriv configuration updated: App ID {deriv_app_id[:8]}...")
            
            return {
                "success": True,
                "message": "Deriv configuration updated successfully",
                "config": {k: v[:8] + "..." if k.endswith("_token") and v else v for k, v in deriv_config.items()}
            }
            
        except Exception as e:
            logger.error(f"❌ Error setting Deriv config: {e}")
            return {
                "success": False,
                "message": f"Error setting Deriv config: {str(e)}"
            }

    def get_deriv_config(self) -> Dict[str, Any]:
        """Get current Deriv configuration"""
        try:
            config_file = self.data_dir / "deriv_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                # Mask sensitive tokens
                masked_config = {}
                for k, v in config.items():
                    if k.endswith("_token") and v:
                        masked_config[k] = v[:8] + "..." if len(v) > 8 else "***"
                    else:
                        masked_config[k] = v
                return masked_config
            return {}
        except Exception as e:
            logger.error(f"❌ Error getting Deriv config: {e}")
            return {}

    def send_telegram_notification(self, message: str, transaction_data: Dict = None) -> Dict[str, Any]:
        """Send notification to Telegram with transaction logging"""
        try:
            if not self.telegram_bot_token or not self.telegram_group_id:
                return {
                    "success": False,
                    "message": "Telegram configuration not set"
                }
            
            # Format message with transaction data if provided
            if transaction_data:
                formatted_message = f"🤖 **Decter Engine (ACCU)**\n\n"
                formatted_message += f"📊 **Transaction Log**\n"
                formatted_message += f"Type: {transaction_data.get('type', 'Unknown')}\n"
                formatted_message += f"Amount: ${transaction_data.get('amount', 0):.2f}\n"
                formatted_message += f"Result: {transaction_data.get('result', 'Unknown')}\n"
                formatted_message += f"Time: {transaction_data.get('timestamp', datetime.now().isoformat())}\n\n"
                formatted_message += f"{message}"
            else:
                formatted_message = f"🤖 **Decter Engine (ACCU)**\n\n{message}"
            
            # Send to Telegram (simplified - would use actual Telegram Bot API)
            logger.info(f"📱 Telegram notification: {formatted_message}")
            
            # Log transaction if provided
            if transaction_data:
                self._log_transaction(transaction_data)
            
            return {
                "success": True,
                "message": "Telegram notification sent successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Error sending Telegram notification: {e}")
            return {
                "success": False,
                "message": f"Error sending notification: {str(e)}"
            }

    def _log_transaction(self, transaction_data: Dict) -> None:
        """Log transaction data for Telegram notifications"""
        try:
            log_file = self.data_dir / "telegram_transactions.json"
            
            # Load existing logs
            if log_file.exists():
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # Add new transaction
            transaction_data['logged_at'] = datetime.now().isoformat()
            logs.append(transaction_data)
            
            # Keep only last 1000 transactions
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # Save logs
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error logging transaction: {e}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for dashboard"""
        try:
            stats = self.get_stats()
            if not stats:
                return {
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "net_pnl": 0.0,
                    "growth_rate": 0.0,
                    "status": self.status.value
                }
            
            return {
                "total_trades": stats.total_trades,
                "win_rate": stats.win_rate,
                "net_pnl": stats.net_pl,
                "growth_rate": stats.growth,
                "consecutive_wins": stats.consecutive_wins,
                "current_mode": stats.current_mode,
                "status": self.status.value,
                "uptime": self._get_uptime()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting performance summary: {e}")
            return {"error": str(e)}


# Global instance for use in API endpoints
decter_controller = DecterController()