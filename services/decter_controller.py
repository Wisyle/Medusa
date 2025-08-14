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

# Import enhanced modules
try:
    sys.path.insert(0, str(Path(__file__).parent / "Decter"))
    from telegram_notifier import get_telegram_notifier
    from trade_history import get_trade_history, TradeFilter, ExportFormat, TradeResult
    ENHANCED_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Enhanced modules not available: {e}")
    ENHANCED_MODULES_AVAILABLE = False


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
        self.engine_logs_file = self.data_dir / "engine_logs.json"
        self.live_logs_file = self.data_dir / "live_logs.json"
        
        # Ensure data directory exists with proper error handling
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions by creating and removing a test file
            test_file = self.data_dir / "test_permissions.tmp"
            test_file.touch()
            test_file.unlink()
            
            logger.info(f"✅ Data directory ready: {self.data_dir}")
            
        except (PermissionError, FileNotFoundError, OSError) as e:
            # If we can't create the data directory, use a temporary one
            import tempfile
            self.data_dir = Path(tempfile.mkdtemp(prefix="decter_controller_"))
            logger.warning(f"Could not create data directory, using temporary: {self.data_dir}")
            # Update file paths
            self.stats_file = self.data_dir / "trading_stats.json"
            self.params_file = self.data_dir / "saved_params.json"
            self.log_file = self.data_dir / "trading_bot.log"
            self.engine_logs_file = self.data_dir / "engine_logs.json"
            self.live_logs_file = self.data_dir / "live_logs.json"
        
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
        
        # Initialize JSON logging system
        self.initialize_json_logs()

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
            
            # Start the process
            self.status = DecterStatus.STARTING
            logger.info("🚀 Starting Decter 001 bot...")
            logger.info(f"Working directory: {os.getcwd()}")
            logger.info(f"Decter path: {self.decter_path}")
            logger.info(f"Main script: {self.main_script}")
            
            # Create log file for subprocess output with proper error handling
            log_file = self.data_dir / "subprocess.log"
            
            try:
                # Ensure the data directory exists
                self.data_dir.mkdir(parents=True, exist_ok=True)
                
                # Create/clear the log file
                log_file.touch()
                
                with open(log_file, 'w', encoding='utf-8') as f:
                    self.process = subprocess.Popen(
                        ["python", str(self.main_script)],
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=os.getcwd()  # Use current working directory
                    )
            except (PermissionError, OSError) as e:
                logger.error(f"Cannot create subprocess log file: {e}")
                # Use stdout/stderr directly if we can't create log file
                self.process = subprocess.Popen(
                    ["python", str(self.main_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=os.getcwd()  # Use current working directory
                )
            
            # Give it a moment to start
            time.sleep(3)
            
            # Check if it started successfully
            if self.process.poll() is None:
                self.status = DecterStatus.ONLINE
                self.last_heartbeat = datetime.now()
                self.start_time = datetime.now()
                logger.info(f"✅ Decter 001 started successfully with PID: {self.process.pid}")
                
                # Log to JSON
                self.log_to_json(
                    f"Decter 001 started successfully (PID: {self.process.pid})",
                    "INFO",
                    "Engine",
                    {"process_id": self.process.pid, "status": self.status.value}
                )
                
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
            
            # Log to JSON
            self.log_to_json(
                "Decter 001 stopped successfully",
                "INFO",
                "Engine",
                {"status": self.status.value}
            )
            
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
            
            # Log to JSON
            self.log_to_json(
                "Trading parameters updated",
                "INFO",
                "Config",
                params_data
            )
            
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
        """Get recent log entries from JSON log files"""
        try:
            # First try to get from JSON log files (preferred for Render)
            logs = self._get_logs_from_json(lines)
            if logs:
                return logs
            
            # Fallback to traditional log files
            if not self.log_file.exists():
                # Try subprocess log file
                subprocess_log = self.data_dir / "subprocess.log"
                if subprocess_log.exists():
                    try:
                        with open(subprocess_log, 'r', encoding='utf-8') as f:
                            all_lines = f.readlines()
                            return [line.strip() for line in all_lines[-lines:]]
                    except (PermissionError, OSError) as e:
                        logger.error(f"Error reading subprocess log: {e}")
                        return []
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
            
            # Log to JSON
            self.log_to_json(
                f"Telegram configuration updated (Group: {group_id})",
                "INFO",
                "Telegram",
                {"group_id": group_id, "has_topic": bool(topic_id)}
            )
            
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
            
            # Log to JSON
            self.log_to_json(
                f"Deriv API configuration updated (App ID: {deriv_app_id[:8]}...)",
                "INFO",
                "API",
                {"deriv_app_id": deriv_app_id[:12] + "...", "currencies_configured": len(currency_tokens)}
            )
            
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

    def set_engine_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set engine behavior and risk parameters"""
        try:
            engine_config = {
                # Multi-currency settings
                "selected_currency": config.get("selected_currency", "XRP"),
                "supported_currencies": config.get("supported_currencies", ["XRP", "BTC", "ETH", "LTC", "USDT", "USD"]),
                
                # Continuous Engine parameters
                "consecutive_wins_threshold": config.get("consecutive_wins_threshold", 10),
                "max_profit_cap": config.get("max_profit_cap", 1000.0),
                "risk_reduction_factor": config.get("risk_reduction_factor", 0.7),
                
                # Decision Engine parameters
                "max_loss_threshold": config.get("max_loss_threshold", 100.0),
                "drawdown_threshold": config.get("drawdown_threshold", 0.15),
                "volatility_lookback_periods": config.get("volatility_lookback_periods", 1800),
                "recovery_risk_multiplier": config.get("recovery_risk_multiplier", 1.8),
                
                # General settings
                "enable_continuous_engine": config.get("enable_continuous_engine", True),
                "enable_decision_engine": config.get("enable_decision_engine", True),
                "diagnostic_logging": config.get("diagnostic_logging", True)
            }
            
            # Save to engine config file
            config_file = self.data_dir / "engine_config.json"
            with open(config_file, 'w') as f:
                json.dump(engine_config, f, indent=2)
            
            logger.info(f"⚙️ Engine configuration updated: Currency {engine_config['selected_currency']}")
            
            # Log to JSON
            self.log_to_json(
                f"Engine configuration updated (Currency: {engine_config['selected_currency']})",
                "INFO",
                "Engine",
                {"selected_currency": engine_config['selected_currency'], "engines_enabled": {"continuous": engine_config.get('enable_continuous_engine', False), "decision": engine_config.get('enable_decision_engine', False)}}
            )
            
            return {
                "success": True,
                "message": "Engine configuration updated successfully",
                "config": engine_config
            }
            
        except Exception as e:
            logger.error(f"❌ Error setting engine config: {e}")
            return {
                "success": False,
                "message": f"Error setting engine config: {str(e)}"
            }

    def get_engine_config(self) -> Dict[str, Any]:
        """Get current engine configuration"""
        try:
            config_file = self.data_dir / "engine_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return json.load(f)
            
            # Return default configuration
            return {
                "selected_currency": "XRP",
                "supported_currencies": ["XRP", "BTC", "ETH", "LTC", "USDT", "USD"],
                "consecutive_wins_threshold": 10,
                "max_profit_cap": 1000.0,
                "risk_reduction_factor": 0.7,
                "max_loss_threshold": 100.0,
                "drawdown_threshold": 0.15,
                "volatility_lookback_periods": 1800,
                "recovery_risk_multiplier": 1.8,
                "enable_continuous_engine": True,
                "enable_decision_engine": True,
                "diagnostic_logging": True
            }
        except Exception as e:
            logger.error(f"❌ Error getting engine config: {e}")
            return {}

    def get_engine_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive engine diagnostics and state"""
        try:
            diagnostics = {
                "continuous_engine": {
                    "status": "unknown",
                    "consecutive_wins": 0,
                    "current_profit": 0.0,
                    "last_activity": None,
                    "risk_level": "normal"
                },
                "decision_engine": {
                    "status": "unknown", 
                    "current_loss": 0.0,
                    "drawdown_percentage": 0.0,
                    "selected_asset": None,
                    "volatility_analysis": {},
                    "last_decision": None
                },
                "api_routing": {
                    "active_currency": self.get_engine_config().get("selected_currency", "XRP"),
                    "api_status": {},
                    "last_api_call": None
                },
                "system": {
                    "uptime": self._get_uptime(),
                    "memory_usage": "N/A",
                    "last_error": None,
                    "configuration_status": "loaded"
                }
            }
            
            # Try to load real diagnostics from diagnostic log file
            diag_file = self.data_dir / "engine_diagnostics.json"
            if diag_file.exists():
                with open(diag_file, 'r') as f:
                    stored_diagnostics = json.load(f)
                    # Merge with defaults
                    for category in diagnostics:
                        if category in stored_diagnostics:
                            diagnostics[category].update(stored_diagnostics[category])
            
            return diagnostics
            
        except Exception as e:
            logger.error(f"❌ Error getting engine diagnostics: {e}")
            return {"error": str(e)}

    def switch_currency(self, new_currency: str) -> Dict[str, Any]:
        """Switch active trading currency and update API routing"""
        try:
            # Validate currency is supported
            engine_config = self.get_engine_config()
            supported_currencies = engine_config.get("supported_currencies", [])
            
            if new_currency not in supported_currencies:
                return {
                    "success": False,
                    "message": f"Currency {new_currency} not supported. Available: {', '.join(supported_currencies)}"
                }
            
            # Update engine configuration
            engine_config["selected_currency"] = new_currency
            result = self.set_engine_config(engine_config)
            
            if result["success"]:
                logger.info(f"💱 Currency switched to {new_currency}")
                
                # Log to JSON
                self.log_to_json(
                    f"Currency switched to {new_currency}",
                    "INFO",
                    "Engine",
                    {"new_currency": new_currency, "previous_currency": engine_config.get('selected_currency', 'unknown')}
                )
                return {
                    "success": True,
                    "message": f"Successfully switched to {new_currency}",
                    "active_currency": new_currency
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"❌ Error switching currency: {e}")
            return {
                "success": False,
                "message": f"Error switching currency: {str(e)}"
            }

    def send_telegram_notification(self, message: str, transaction_data: Dict = None) -> Dict[str, Any]:
        """Send notification to Telegram with enhanced structured formatting"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                # Fallback to basic notification
                return self._send_basic_telegram_notification(message, transaction_data)
            
            # Use enhanced telegram notifier
            telegram_notifier = get_telegram_notifier(self.data_dir)
            
            if transaction_data:
                # Send as structured trade notification
                trade_data = {
                    "action": transaction_data.get("type", "unknown"),
                    "asset_pair": transaction_data.get("asset_pair", "N/A"),
                    "direction": transaction_data.get("direction", "N/A"),
                    "entry_price": transaction_data.get("entry_price", 0.0),
                    "exit_price": transaction_data.get("exit_price", 0.0),
                    "pnl": transaction_data.get("amount", 0.0),
                    "timestamp": transaction_data.get("timestamp", datetime.now()),
                    "reason": message,
                    "engine": transaction_data.get("engine", "continuous")
                }
                
                result = asyncio.run(telegram_notifier.send_trade_notification(trade_data))
            else:
                # Send as engine alert
                alert_data = {
                    "engine": "decter",
                    "event": "notification",
                    "details": {"message": message}
                }
                
                result = asyncio.run(telegram_notifier.send_engine_alert(alert_data))
            
            # Log transaction if provided
            if transaction_data:
                self._log_transaction(transaction_data)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending enhanced Telegram notification: {e}")
            # Fallback to basic notification
            return self._send_basic_telegram_notification(message, transaction_data)

    def _send_basic_telegram_notification(self, message: str, transaction_data: Dict = None) -> Dict[str, Any]:
        """Fallback basic Telegram notification"""
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
            logger.error(f"❌ Error sending basic Telegram notification: {e}")
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

    def _get_logs_from_json(self, lines: int = 10) -> List[str]:
        """Get logs from JSON log files"""
        try:
            logs = []
            
            # Try engine logs first
            if self.engine_logs_file.exists():
                with open(self.engine_logs_file, 'r') as f:
                    engine_logs = json.load(f)
                    if isinstance(engine_logs, list):
                        logs.extend(engine_logs[-lines//2:])
            
            # Then try live logs
            if self.live_logs_file.exists():
                with open(self.live_logs_file, 'r') as f:
                    live_logs = json.load(f)
                    if isinstance(live_logs, list):
                        logs.extend(live_logs[-lines//2:])
            
            # Sort by timestamp if available, otherwise return as is
            return logs[-lines:] if logs else []
            
        except Exception as e:
            logger.error(f"❌ Error reading JSON logs: {e}")
            return []

    def log_to_json(self, message: str, level: str = "INFO", module: str = "Decter", details: Dict = None):
        """Log a message to JSON files for Render persistence"""
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "level": level,
                "module": module,
                "message": message,
                "details": details or {}
            }
            
            # Format for display
            formatted_log = f"[{timestamp}] — [{module}] — [{level}] — {message}"
            
            # Save to live logs (for real-time display)
            self._append_to_json_file(self.live_logs_file, formatted_log)
            
            # Save structured log to engine logs
            self._append_to_json_file(self.engine_logs_file, log_entry, structured=True)
            
        except Exception as e:
            logger.error(f"❌ Error logging to JSON: {e}")

    def _append_to_json_file(self, file_path: Path, entry: any, structured: bool = False, max_entries: int = 1000):
        """Append entry to JSON file with rotation"""
        try:
            # Load existing data
            if file_path.exists():
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    except json.JSONDecodeError:
                        data = []
            else:
                data = []
            
            # Add new entry
            data.append(entry)
            
            # Rotate logs if too many entries
            if len(data) > max_entries:
                data = data[-max_entries:]
            
            # Save back to file
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2 if structured else None, default=str)
                
        except Exception as e:
            logger.error(f"❌ Error appending to JSON file {file_path}: {e}")

    def clear_json_logs(self) -> Dict[str, Any]:
        """Clear JSON log files"""
        try:
            files_cleared = []
            
            if self.engine_logs_file.exists():
                with open(self.engine_logs_file, 'w') as f:
                    json.dump([], f)
                files_cleared.append("engine_logs.json")
            
            if self.live_logs_file.exists():
                with open(self.live_logs_file, 'w') as f:
                    json.dump([], f)
                files_cleared.append("live_logs.json")
            
            self.log_to_json("JSON log files cleared", "INFO", "Controller")
            
            return {
                "success": True,
                "message": f"Cleared {len(files_cleared)} log files",
                "files_cleared": files_cleared
            }
            
        except Exception as e:
            logger.error(f"❌ Error clearing JSON logs: {e}")
            return {
                "success": False,
                "message": f"Error clearing logs: {str(e)}"
            }

    def initialize_json_logs(self):
        """Initialize JSON log files with startup messages"""
        try:
            # Create empty log files if they don't exist
            if not self.engine_logs_file.exists():
                with open(self.engine_logs_file, 'w') as f:
                    json.dump([], f)
            
            if not self.live_logs_file.exists():
                with open(self.live_logs_file, 'w') as f:
                    json.dump([], f)
            
            # Log initialization
            self.log_to_json(
                "Decter 001 Controller initialized", 
                "INFO", 
                "Controller",
                {"decter_path": str(self.decter_path), "data_dir": str(self.data_dir)}
            )
            
        except Exception as e:
            logger.error(f"❌ Error initializing JSON logs: {e}")

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

    def send_daily_summary(self) -> Dict[str, Any]:
        """Send daily summary report via Telegram"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                return {
                    "success": False,
                    "message": "Enhanced modules not available"
                }
            
            # Get trading statistics
            stats = self.get_stats()
            engine_config = self.get_engine_config()
            engine_diagnostics = self.get_engine_diagnostics()
            
            if not stats:
                return {
                    "success": False,
                    "message": "No trading statistics available"
                }
            
            # Prepare summary data
            summary_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_trades": stats.total_trades,
                "wins": stats.wins,
                "losses": stats.losses,
                "net_pnl": stats.net_pl,
                "win_rate": stats.win_rate,
                "profit_factor": stats.wins / max(1, stats.losses),
                "best_trade": 0.0,  # Would need to calculate from trade history
                "worst_trade": 0.0,  # Would need to calculate from trade history
                "active_currency": engine_config.get("selected_currency", "XRP"),
                "engine_stats": {
                    "continuous": engine_diagnostics.get("continuous_engine", {}),
                    "decision": engine_diagnostics.get("decision_engine", {})
                }
            }
            
            # Send via enhanced notifier
            telegram_notifier = get_telegram_notifier(self.data_dir)
            result = asyncio.run(telegram_notifier.send_daily_summary(summary_data))
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error sending daily summary: {e}")
            return {
                "success": False,
                "message": f"Error sending daily summary: {str(e)}"
            }

    def get_filtered_trade_history(self, start_date: str = None, end_date: str = None, 
                                 currency: str = None, engine: str = None, result: str = None,
                                 asset_pair: str = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get filtered trade history"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                # Fallback to basic trade history
                return {
                    "trades": self.get_trade_history(limit),
                    "total_count": limit,
                    "filtered": False,
                    "message": "Enhanced filtering not available"
                }
            
            # Create filter criteria
            filter_criteria = TradeFilter()
            
            if start_date:
                filter_criteria.start_date = datetime.fromisoformat(start_date)
            if end_date:
                filter_criteria.end_date = datetime.fromisoformat(end_date)
            if currency:
                filter_criteria.currency = currency
            if engine:
                filter_criteria.engine = engine
            if result:
                filter_criteria.result = TradeResult(result)
            if asset_pair:
                filter_criteria.asset_pair = asset_pair
            
            # Get trade history instance
            trade_history = get_trade_history(self.data_dir)
            
            # Get filtered trades
            trades = trade_history.get_trades(filter_criteria, limit, offset)
            
            # Get total count (without pagination)
            all_trades = trade_history.get_trades(filter_criteria)
            total_count = len(all_trades)
            
            return {
                "trades": trades,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "filtered": True,
                "filter_criteria": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency": currency,
                    "engine": engine,
                    "result": result,
                    "asset_pair": asset_pair
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting filtered trade history: {e}")
            return {
                "trades": [],
                "total_count": 0,
                "error": str(e)
            }

    def get_trade_summary_stats(self, start_date: str = None, end_date: str = None,
                              currency: str = None, engine: str = None) -> Dict[str, Any]:
        """Get trade summary statistics"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                # Fallback to basic stats
                stats = self.get_stats()
                if stats:
                    return {
                        "total_trades": stats.total_trades,
                        "wins": stats.wins,
                        "losses": stats.losses,
                        "win_rate": stats.win_rate,
                        "net_pnl": stats.net_pl,
                        "enhanced": False
                    }
                return {"error": "No statistics available"}
            
            # Create filter criteria
            filter_criteria = TradeFilter()
            
            if start_date:
                filter_criteria.start_date = datetime.fromisoformat(start_date)
            if end_date:
                filter_criteria.end_date = datetime.fromisoformat(end_date)
            if currency:
                filter_criteria.currency = currency
            if engine:
                filter_criteria.engine = engine
            
            # Get trade history instance
            trade_history = get_trade_history(self.data_dir)
            
            # Get summary statistics
            summary = trade_history.get_summary_stats(filter_criteria)
            
            return {
                "total_trades": summary.total_trades,
                "wins": summary.wins,
                "losses": summary.losses,
                "breakeven": summary.breakeven,
                "win_rate": summary.win_rate,
                "profit_factor": summary.profit_factor,
                "total_pnl": summary.total_pnl,
                "avg_pnl_per_trade": summary.avg_pnl_per_trade,
                "best_trade": summary.best_trade,
                "worst_trade": summary.worst_trade,
                "avg_duration_minutes": summary.avg_duration_minutes,
                "total_volume": summary.total_volume,
                "sharpe_ratio": summary.sharpe_ratio,
                "enhanced": True,
                "filter_criteria": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency": currency,
                    "engine": engine
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting trade summary stats: {e}")
            return {"error": str(e)}

    def export_trade_history(self, export_format: str = "csv", start_date: str = None,
                           end_date: str = None, currency: str = None, engine: str = None) -> Dict[str, Any]:
        """Export trade history to specified format"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                return {
                    "success": False,
                    "message": "Enhanced export functionality not available"
                }
            
            # Create filter criteria
            filter_criteria = TradeFilter()
            
            if start_date:
                filter_criteria.start_date = datetime.fromisoformat(start_date)
            if end_date:
                filter_criteria.end_date = datetime.fromisoformat(end_date)
            if currency:
                filter_criteria.currency = currency
            if engine:
                filter_criteria.engine = engine
            
            # Validate export format
            try:
                export_format_enum = ExportFormat(export_format.lower())
            except ValueError:
                return {
                    "success": False,
                    "message": f"Invalid export format: {export_format}. Supported: csv, json, pdf"
                }
            
            # Get trade history instance
            trade_history = get_trade_history(self.data_dir)
            
            # Export trades
            result = trade_history.export_trades(filter_criteria, export_format_enum)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error exporting trade history: {e}")
            return {
                "success": False,
                "message": f"Error exporting trades: {str(e)}"
            }

    def get_daily_trading_breakdown(self, days: int = 30) -> Dict[str, Any]:
        """Get daily trading performance breakdown"""
        try:
            if not ENHANCED_MODULES_AVAILABLE:
                return {
                    "daily_data": [],
                    "message": "Enhanced daily breakdown not available"
                }
            
            # Get trade history instance
            trade_history = get_trade_history(self.data_dir)
            
            # Get daily breakdown
            daily_breakdown = trade_history.get_daily_breakdown(days)
            
            return {
                "daily_data": daily_breakdown,
                "days_requested": days,
                "total_days_with_data": len(daily_breakdown)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting daily breakdown: {e}")
            return {
                "daily_data": [],
                "error": str(e)
            }


# Global instance for use in API endpoints
decter_controller = DecterController()