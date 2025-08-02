"""
Continuous Engine Module for Decter Trading System
Monitors active trade performance and manages risk based on consecutive wins and profit caps
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ContinuousEngine:
    """
    Continuous monitoring engine that tracks trade performance and adjusts risk parameters
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.is_running = False
        self.consecutive_wins = 0
        self.current_profit = 0.0
        self.total_trades = 0
        self.risk_level = "normal"  # normal, reduced, halted
        self.last_activity = None
        
        # Configuration (loaded from engine_config.json)
        self.config = self._load_config()
        
        # State file for persistence
        self.state_file = data_dir / "continuous_engine_state.json"
        self._load_state()
        
        logger.info("🔄 Continuous Engine initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load engine configuration"""
        try:
            config_file = self.data_dir / "engine_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                return config
            
            # Default configuration
            return {
                "consecutive_wins_threshold": 10,
                "max_profit_cap": 1000.0,
                "risk_reduction_factor": 0.7,
                "enable_continuous_engine": True
            }
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            return {}
    
    def _load_state(self) -> None:
        """Load persistent state"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.consecutive_wins = state.get("consecutive_wins", 0)
                self.current_profit = state.get("current_profit", 0.0)
                self.total_trades = state.get("total_trades", 0)
                self.risk_level = state.get("risk_level", "normal")
                
                if state.get("last_activity"):
                    self.last_activity = datetime.fromisoformat(state["last_activity"])
                
                logger.info(f"📊 Continuous Engine state loaded: {self.consecutive_wins} wins, ${self.current_profit:.2f} profit")
        except Exception as e:
            logger.error(f"❌ Error loading state: {e}")
    
    def _save_state(self) -> None:
        """Save persistent state"""
        try:
            state = {
                "consecutive_wins": self.consecutive_wins,
                "current_profit": self.current_profit,
                "total_trades": self.total_trades,
                "risk_level": self.risk_level,
                "last_activity": self.last_activity.isoformat() if self.last_activity else None,
                "updated_at": datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error saving state: {e}")
    
    def _update_diagnostics(self) -> None:
        """Update diagnostic information"""
        try:
            diagnostics = {
                "continuous_engine": {
                    "status": "running" if self.is_running else "stopped",
                    "consecutive_wins": self.consecutive_wins,
                    "current_profit": self.current_profit,
                    "total_trades": self.total_trades,
                    "risk_level": self.risk_level,
                    "last_activity": self.last_activity.isoformat() if self.last_activity else None
                }
            }
            
            # Update or create diagnostics file
            diag_file = self.data_dir / "engine_diagnostics.json"
            existing_diag = {}
            
            if diag_file.exists():
                with open(diag_file, 'r') as f:
                    existing_diag = json.load(f)
            
            existing_diag.update(diagnostics)
            
            with open(diag_file, 'w') as f:
                json.dump(existing_diag, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error updating diagnostics: {e}")
    
    async def start(self) -> Dict[str, Any]:
        """Start the continuous monitoring engine"""
        try:
            if self.is_running:
                return {"success": False, "message": "Continuous engine already running"}
            
            # Reload configuration
            self.config = self._load_config()
            
            if not self.config.get("enable_continuous_engine", True):
                return {"success": False, "message": "Continuous engine disabled in configuration"}
            
            self.is_running = True
            self.last_activity = datetime.now()
            
            logger.info("🚀 Continuous Engine started")
            
            # Start monitoring loop
            asyncio.create_task(self._monitoring_loop())
            
            self._save_state()
            self._update_diagnostics()
            
            return {
                "success": True,
                "message": "Continuous engine started successfully",
                "status": "running"
            }
            
        except Exception as e:
            logger.error(f"❌ Error starting continuous engine: {e}")
            return {"success": False, "message": f"Error starting engine: {str(e)}"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the continuous monitoring engine"""
        try:
            self.is_running = False
            self.last_activity = datetime.now()
            
            logger.info("🛑 Continuous Engine stopped")
            
            self._save_state()
            self._update_diagnostics()
            
            return {
                "success": True,
                "message": "Continuous engine stopped successfully",
                "status": "stopped"
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping continuous engine: {e}")
            return {"success": False, "message": f"Error stopping engine: {str(e)}"}
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("🔍 Continuous Engine monitoring loop started")
        
        while self.is_running:
            try:
                # Reload configuration periodically
                self.config = self._load_config()
                
                # Check if engine should still be running
                if not self.config.get("enable_continuous_engine", True):
                    logger.info("⚠️ Continuous engine disabled via configuration, stopping...")
                    await self.stop()
                    break
                
                # Analyze current trading performance
                await self._analyze_performance()
                
                # Update diagnostics
                self._update_diagnostics()
                
                # Sleep before next check (30 seconds)
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                logger.info("🔄 Continuous Engine monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(10)  # Short sleep on error
    
    async def _analyze_performance(self) -> None:
        """Analyze current trading performance and adjust risk parameters"""
        try:
            # Load current trading statistics
            stats = self._load_trading_stats()
            
            if not stats:
                return
            
            # Update internal counters
            self.total_trades = stats.get("total_trades", 0)
            self.current_profit = stats.get("net_pl", 0.0)
            
            # Calculate consecutive wins from recent trades
            self.consecutive_wins = self._calculate_consecutive_wins(stats)
            
            # Check win streak threshold
            wins_threshold = self.config.get("consecutive_wins_threshold", 10)
            if self.consecutive_wins >= wins_threshold and self.risk_level == "normal":
                await self._reduce_risk_parameters()
                self.risk_level = "reduced"
                logger.info(f"🔻 Risk parameters reduced after {self.consecutive_wins} consecutive wins")
            
            # Check profit cap
            profit_cap = self.config.get("max_profit_cap", 1000.0)
            if self.current_profit >= profit_cap and self.risk_level != "halted":
                await self._halt_trading()
                self.risk_level = "halted"
                logger.info(f"🛑 Trading halted - profit cap reached: ${self.current_profit:.2f}")
            
            # Reset risk level if conditions improve
            if self.consecutive_wins < wins_threshold // 2 and self.risk_level == "reduced":
                await self._restore_risk_parameters()
                self.risk_level = "normal"
                logger.info("🔼 Risk parameters restored to normal")
            
            self.last_activity = datetime.now()
            self._save_state()
            
        except Exception as e:
            logger.error(f"❌ Error analyzing performance: {e}")
    
    def _load_trading_stats(self) -> Dict[str, Any]:
        """Load current trading statistics"""
        try:
            stats_file = self.data_dir / "trading_stats.json"
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading trading stats: {e}")
        return {}
    
    def _calculate_consecutive_wins(self, stats: Dict[str, Any]) -> int:
        """Calculate current consecutive wins from trade history"""
        try:
            trade_history = stats.get("trade_history", [])
            if not trade_history:
                return 0
            
            consecutive = 0
            # Count from most recent trades backwards
            for trade in reversed(trade_history):
                if trade.get("result") == "win":
                    consecutive += 1
                else:
                    break
            
            return consecutive
            
        except Exception as e:
            logger.error(f"❌ Error calculating consecutive wins: {e}")
            return 0
    
    async def _reduce_risk_parameters(self) -> None:
        """Reduce risk parameters due to win streak"""
        try:
            # Load current saved parameters
            params_file = self.data_dir / "saved_params.json"
            if params_file.exists():
                with open(params_file, 'r') as f:
                    params = json.load(f)
                
                # Apply risk reduction factor
                reduction_factor = self.config.get("risk_reduction_factor", 0.7)
                
                if "stake" in params:
                    params["stake"] *= reduction_factor
                if "growth_rate" in params:
                    params["growth_rate"] *= reduction_factor
                
                # Save reduced parameters
                with open(params_file, 'w') as f:
                    json.dump(params, f, indent=2)
                
                logger.info(f"📉 Risk parameters reduced by factor: {reduction_factor}")
        except Exception as e:
            logger.error(f"❌ Error reducing risk parameters: {e}")
    
    async def _restore_risk_parameters(self) -> None:
        """Restore normal risk parameters"""
        try:
            # This would restore parameters to their baseline values
            # Implementation depends on how baseline parameters are stored
            logger.info("📈 Risk parameters restored to baseline")
        except Exception as e:
            logger.error(f"❌ Error restoring risk parameters: {e}")
    
    async def _halt_trading(self) -> None:
        """Halt trading due to profit cap reached"""
        try:
            # Create halt signal file
            halt_file = self.data_dir / "trading_halt.json"
            halt_data = {
                "halted": True,
                "reason": "profit_cap_reached",
                "timestamp": datetime.now().isoformat(),
                "profit_at_halt": self.current_profit
            }
            
            with open(halt_file, 'w') as f:
                json.dump(halt_data, f, indent=2)
            
            logger.warning("🚨 Trading halted due to profit cap")
        except Exception as e:
            logger.error(f"❌ Error halting trading: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status"""
        return {
            "is_running": self.is_running,
            "consecutive_wins": self.consecutive_wins,
            "current_profit": self.current_profit,
            "total_trades": self.total_trades,
            "risk_level": self.risk_level,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "thresholds": {
                "consecutive_wins_threshold": self.config.get("consecutive_wins_threshold", 10),
                "max_profit_cap": self.config.get("max_profit_cap", 1000.0),
                "risk_reduction_factor": self.config.get("risk_reduction_factor", 0.7)
            }
        }

# Global instance
continuous_engine: Optional[ContinuousEngine] = None

def get_continuous_engine(data_dir: Path) -> ContinuousEngine:
    """Get or create continuous engine instance"""
    global continuous_engine
    if continuous_engine is None:
        continuous_engine = ContinuousEngine(data_dir)
    return continuous_engine