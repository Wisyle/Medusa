"""
Enhanced Decision Engine Module for Decter Trading System
Handles recovery mode with intelligent volatility-based asset selection and recalibration
"""

import asyncio
import json
import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class TradingMode(Enum):
    """Trading mode enumeration"""
    CONTINUOUS = "continuous"
    RECOVERY = "recovery"

class EngineState(Enum):
    """Engine state enumeration"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ANALYZING = "analyzing"
    TRADING = "trading"

class AnalysisData:
    """Container for analysis data"""
    def __init__(self):
        self.state = EngineState.INACTIVE
        self.recovery_failures = 0
        self.recovery_risk_reduction = 1.0
        self.proposed_params = None
        self.confirmation_deadline = None
        self.session_start_balance = 0.0

class DecisionEngine:
    """
    Advanced decision engine for recovery trading with volatility analysis and asset selection
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.is_running = False
        self.current_loss = 0.0
        self.drawdown_percentage = 0.0
        self.recovery_mode = False
        self.selected_asset = None
        self.volatility_analysis = {}
        self.last_decision = None
        self.analysis_data = AnalysisData()
        self.current_mode = TradingMode.CONTINUOUS
        
        # Configuration
        self.config = self._load_config()
        
        # Available indices for volatility analysis
        self.available_indices = [
            "R_10", "R_25", "R_50", "R_75", "R_100",
            "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V",
            "1HZ150V", "1HZ250V"
        ]
        
        # State file for persistence
        self.state_file = data_dir / "decision_engine_state.json"
        self._load_state()
        
        logger.info("🧠 Decision Engine initialized")
    
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
                "max_loss_threshold": 100.0,
                "drawdown_threshold": 0.15,
                "volatility_lookback_periods": 1800,
                "recovery_risk_multiplier": 1.8,
                "enable_decision_engine": True
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
                
                self.current_loss = state.get("current_loss", 0.0)
                self.drawdown_percentage = state.get("drawdown_percentage", 0.0)
                self.recovery_mode = state.get("recovery_mode", False)
                self.selected_asset = state.get("selected_asset")
                self.volatility_analysis = state.get("volatility_analysis", {})
                
                if state.get("last_decision"):
                    self.last_decision = datetime.fromisoformat(state["last_decision"])
                
                logger.info(f"🧠 Decision Engine state loaded: Loss ${self.current_loss:.2f}, Recovery: {self.recovery_mode}")
        except Exception as e:
            logger.error(f"❌ Error loading state: {e}")
    
    def _save_state(self) -> None:
        """Save persistent state"""
        try:
            state = {
                "current_loss": self.current_loss,
                "drawdown_percentage": self.drawdown_percentage,
                "recovery_mode": self.recovery_mode,
                "selected_asset": self.selected_asset,
                "volatility_analysis": self.volatility_analysis,
                "last_decision": self.last_decision.isoformat() if self.last_decision else None,
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
                "decision_engine": {
                    "status": "running" if self.is_running else "stopped",
                    "recovery_mode": self.recovery_mode,
                    "current_loss": self.current_loss,
                    "drawdown_percentage": self.drawdown_percentage,
                    "selected_asset": self.selected_asset,
                    "volatility_analysis": self.volatility_analysis,
                    "last_decision": self.last_decision.isoformat() if self.last_decision else None
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
        """Start the decision engine"""
        try:
            if self.is_running:
                return {"success": False, "message": "Decision engine already running"}
            
            # Reload configuration
            self.config = self._load_config()
            
            if not self.config.get("enable_decision_engine", True):
                return {"success": False, "message": "Decision engine disabled in configuration"}
            
            self.is_running = True
            self.last_decision = datetime.now()
            
            logger.info("🧠 Decision Engine started")
            
            # Start monitoring loop
            asyncio.create_task(self._decision_loop())
            
            self._save_state()
            self._update_diagnostics()
            
            return {
                "success": True,
                "message": "Decision engine started successfully",
                "status": "running"
            }
            
        except Exception as e:
            logger.error(f"❌ Error starting decision engine: {e}")
            return {"success": False, "message": f"Error starting engine: {str(e)}"}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the decision engine"""
        try:
            self.is_running = False
            self.last_decision = datetime.now()
            
            logger.info("🛑 Decision Engine stopped")
            
            self._save_state()
            self._update_diagnostics()
            
            return {
                "success": True,
                "message": "Decision engine stopped successfully",
                "status": "stopped"
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping decision engine: {e}")
            return {"success": False, "message": f"Error stopping engine: {str(e)}"}
    
    async def _decision_loop(self) -> None:
        """Main decision-making loop"""
        logger.info("🔍 Decision Engine monitoring loop started")
        
        while self.is_running:
            try:
                # Reload configuration periodically
                self.config = self._load_config()
                
                # Check if engine should still be running
                if not self.config.get("enable_decision_engine", True):
                    logger.info("⚠️ Decision engine disabled via configuration, stopping...")
                    await self.stop()
                    break
                
                # Analyze current situation and make decisions
                await self._analyze_and_decide()
                
                # Update diagnostics
                self._update_diagnostics()
                
                # Sleep before next check (60 seconds for decision engine)
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("🔄 Decision Engine monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in decision loop: {e}")
                await asyncio.sleep(30)  # Sleep on error
    
    async def _analyze_and_decide(self) -> None:
        """Analyze current situation and make recovery decisions"""
        try:
            # Load current trading statistics
            stats = self._load_trading_stats()
            
            if not stats:
                return
            
            # Update current loss and drawdown
            self.current_loss = abs(min(0, stats.get("net_pl", 0.0)))
            starting_balance = stats.get("starting_balance", 1000.0)
            current_balance = starting_balance + stats.get("net_pl", 0.0)
            self.drawdown_percentage = (starting_balance - current_balance) / starting_balance if starting_balance > 0 else 0
            
            # Check if recovery mode should be triggered
            loss_threshold = self.config.get("max_loss_threshold", 100.0)
            drawdown_threshold = self.config.get("drawdown_threshold", 0.15)
            
            should_enter_recovery = (
                self.current_loss >= loss_threshold or 
                self.drawdown_percentage >= drawdown_threshold
            )
            
            if should_enter_recovery and not self.recovery_mode:
                await self._enter_recovery_mode()
            elif not should_enter_recovery and self.recovery_mode:
                await self._exit_recovery_mode()
            
            # If in recovery mode, perform volatility analysis and asset selection
            if self.recovery_mode:
                await self._perform_volatility_analysis()
                await self._select_optimal_asset()
                await self._apply_recovery_strategy()
            
            self.last_decision = datetime.now()
            self._save_state()
            
        except Exception as e:
            logger.error(f"❌ Error in analysis and decision: {e}")
    
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
    
    async def _enter_recovery_mode(self) -> None:
        """Enter recovery mode"""
        try:
            self.recovery_mode = True
            logger.warning(f"🚨 Entering recovery mode - Loss: ${self.current_loss:.2f}, Drawdown: {self.drawdown_percentage:.1%}")
            
            # Create recovery mode signal file
            recovery_file = self.data_dir / "recovery_mode.json"
            recovery_data = {
                "active": True,
                "entered_at": datetime.now().isoformat(),
                "trigger_loss": self.current_loss,
                "trigger_drawdown": self.drawdown_percentage
            }
            
            with open(recovery_file, 'w') as f:
                json.dump(recovery_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Error entering recovery mode: {e}")
    
    async def _exit_recovery_mode(self) -> None:
        """Exit recovery mode"""
        try:
            self.recovery_mode = False
            logger.info("✅ Exiting recovery mode - conditions normalized")
            
            # Remove recovery mode signal file
            recovery_file = self.data_dir / "recovery_mode.json"
            if recovery_file.exists():
                recovery_file.unlink()
            
            # Reset selected asset
            self.selected_asset = None
            
        except Exception as e:
            logger.error(f"❌ Error exiting recovery mode: {e}")
    
    async def _perform_volatility_analysis(self) -> None:
        """Perform comprehensive volatility analysis across all available indices"""
        try:
            logger.info("📊 Performing volatility analysis across all indices...")
            
            volatility_data = {}
            lookback_periods = self.config.get("volatility_lookback_periods", 1800)
            
            for index in self.available_indices:
                try:
                    # Simulate volatility calculation (in real implementation, this would fetch market data)
                    volatility = await self._calculate_index_volatility(index, lookback_periods)
                    
                    # Additional metrics
                    stability_score = await self._calculate_stability_score(index, lookback_periods)
                    trend_strength = await self._calculate_trend_strength(index, lookback_periods)
                    
                    volatility_data[index] = {
                        "volatility": volatility,
                        "stability_score": stability_score,
                        "trend_strength": trend_strength,
                        "recovery_suitability": self._calculate_recovery_suitability(volatility, stability_score, trend_strength),
                        "last_updated": datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    logger.error(f"❌ Error analyzing {index}: {e}")
                    volatility_data[index] = {
                        "volatility": float('inf'),  # Mark as high risk
                        "stability_score": 0,
                        "trend_strength": 0,
                        "recovery_suitability": 0,
                        "error": str(e)
                    }
            
            self.volatility_analysis = volatility_data
            
            # Save volatility analysis
            analysis_file = self.data_dir / "volatility_analysis.json"
            with open(analysis_file, 'w') as f:
                json.dump(volatility_data, f, indent=2)
            
            logger.info(f"✅ Volatility analysis completed for {len(volatility_data)} indices")
            
        except Exception as e:
            logger.error(f"❌ Error in volatility analysis: {e}")
    
    async def _calculate_index_volatility(self, index: str, periods: int) -> float:
        """Calculate volatility for a specific index (simulated)"""
        try:
            # In real implementation, this would:
            # 1. Fetch historical price data for the index
            # 2. Calculate returns over the specified periods
            # 3. Compute standard deviation of returns
            
            # Simulated volatility based on index characteristics
            base_volatilities = {
                "R_10": 0.12,   # Lower volatility
                "R_25": 0.18,
                "R_50": 0.25,
                "R_75": 0.32,
                "R_100": 0.40,
                "1HZ10V": 0.08,  # Very low volatility
                "1HZ25V": 0.15,
                "1HZ50V": 0.28,
                "1HZ75V": 0.35,
                "1HZ100V": 0.45,
                "1HZ150V": 0.65,  # High volatility
                "1HZ250V": 0.85   # Very high volatility
            }
            
            base_vol = base_volatilities.get(index, 0.30)
            
            # Add some randomness to simulate real market conditions
            import random
            random_factor = random.uniform(0.8, 1.2)
            
            return base_vol * random_factor
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility for {index}: {e}")
            return float('inf')
    
    async def _calculate_stability_score(self, index: str, periods: int) -> float:
        """Calculate stability score (inverse of volatility with trend consideration)"""
        try:
            volatility = await self._calculate_index_volatility(index, periods)
            
            # Stability is inverse of volatility, normalized to 0-1 scale
            if volatility == 0:
                return 1.0
            
            stability = 1.0 / (1.0 + volatility)
            return min(1.0, max(0.0, stability))
            
        except Exception as e:
            logger.error(f"❌ Error calculating stability for {index}: {e}")
            return 0.0
    
    async def _calculate_trend_strength(self, index: str, periods: int) -> float:
        """Calculate trend strength for the index"""
        try:
            # Simulated trend strength (in real implementation, would analyze price trends)
            import random
            return random.uniform(0.3, 0.8)
            
        except Exception as e:
            logger.error(f"❌ Error calculating trend strength for {index}: {e}")
            return 0.0
    
    def _calculate_recovery_suitability(self, volatility: float, stability_score: float, trend_strength: float) -> float:
        """Calculate overall recovery suitability score"""
        try:
            # Weighted score favoring stability for recovery trades
            suitability = (
                stability_score * 0.6 +          # Stability is most important
                (1.0 - min(1.0, volatility)) * 0.3 +  # Low volatility is good
                trend_strength * 0.1              # Trend strength is least important
            )
            
            return min(1.0, max(0.0, suitability))
            
        except Exception as e:
            logger.error(f"❌ Error calculating recovery suitability: {e}")
            return 0.0
    
    async def _select_optimal_asset(self) -> None:
        """Select the most suitable asset for recovery trading"""
        try:
            if not self.volatility_analysis:
                logger.warning("⚠️ No volatility analysis available for asset selection")
                return
            
            # Find asset with highest recovery suitability
            best_asset = None
            best_score = -1
            
            for index, data in self.volatility_analysis.items():
                if "error" in data:
                    continue
                
                suitability = data.get("recovery_suitability", 0)
                
                if suitability > best_score:
                    best_score = suitability
                    best_asset = index
            
            if best_asset and best_asset != self.selected_asset:
                old_asset = self.selected_asset
                self.selected_asset = best_asset
                
                logger.info(f"🎯 Optimal asset selected for recovery: {best_asset} (score: {best_score:.3f})")
                if old_asset:
                    logger.info(f"📈 Switched from {old_asset} to {best_asset}")
                
                # Save asset selection
                selection_file = self.data_dir / "asset_selection.json"
                selection_data = {
                    "selected_asset": best_asset,
                    "suitability_score": best_score,
                    "selected_at": datetime.now().isoformat(),
                    "previous_asset": old_asset,
                    "selection_reason": "recovery_mode_volatility_analysis"
                }
                
                with open(selection_file, 'w') as f:
                    json.dump(selection_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Error selecting optimal asset: {e}")
    
    async def _apply_recovery_strategy(self) -> None:
        """Apply recovery trading strategy with selected asset"""
        try:
            if not self.selected_asset:
                logger.warning("⚠️ No asset selected for recovery strategy")
                return
            
            # Load current parameters
            params_file = self.data_dir / "saved_params.json"
            if not params_file.exists():
                logger.warning("⚠️ No saved parameters found for recovery strategy")
                return
            
            with open(params_file, 'r') as f:
                params = json.load(f)
            
            # Apply recovery modifications
            recovery_multiplier = self.config.get("recovery_risk_multiplier", 1.8)
            
            # Modify parameters for recovery
            recovery_params = params.copy()
            recovery_params["index"] = self.selected_asset
            
            # Increase stake for recovery (but carefully)
            if "stake" in recovery_params:
                recovery_params["stake"] *= recovery_multiplier
            
            # Adjust other parameters based on selected asset volatility
            asset_data = self.volatility_analysis.get(self.selected_asset, {})
            volatility = asset_data.get("volatility", 0.3)
            
            # Lower take profit for high volatility assets
            if "take_profit" in recovery_params:
                volatility_adjustment = max(0.5, 1.0 - volatility)
                recovery_params["take_profit"] *= volatility_adjustment
            
            # Save recovery parameters
            recovery_file = self.data_dir / "recovery_params.json"
            with open(recovery_file, 'w') as f:
                json.dump(recovery_params, f, indent=2)
            
            logger.info(f"⚡ Recovery strategy applied for {self.selected_asset}")
            logger.info(f"📊 Volatility: {volatility:.3f}, Risk multiplier: {recovery_multiplier}")
            
        except Exception as e:
            logger.error(f"❌ Error applying recovery strategy: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status"""
        return {
            "is_running": self.is_running,
            "recovery_mode": self.recovery_mode,
            "current_loss": self.current_loss,
            "drawdown_percentage": self.drawdown_percentage,
            "selected_asset": self.selected_asset,
            "volatility_analysis_count": len(self.volatility_analysis),
            "last_decision": self.last_decision.isoformat() if self.last_decision else None,
            "thresholds": {
                "max_loss_threshold": self.config.get("max_loss_threshold", 100.0),
                "drawdown_threshold": self.config.get("drawdown_threshold", 0.15),
                "recovery_risk_multiplier": self.config.get("recovery_risk_multiplier", 1.8)
            }
        }
    
    # Compatibility methods for legacy trading_state.py integration
    def get_current_mode(self) -> TradingMode:
        """Get current trading mode"""
        return self.current_mode
    
    def is_active(self) -> bool:
        """Check if engine is active"""
        return self.is_running
    
    def switch_to_continuous_mode(self, reason: str = None) -> None:
        """Switch to continuous mode"""
        self.current_mode = TradingMode.CONTINUOUS
        self.recovery_mode = False
        if reason:
            logger.info(f"🔄 Switched to continuous mode: {reason}")
    
    def reset_engine(self) -> None:
        """Reset engine state"""
        self.analysis_data = AnalysisData()
        self.current_mode = TradingMode.CONTINUOUS
        self.recovery_mode = False
        logger.info("🔄 Engine reset")
    
    def _save_analysis_data(self) -> None:
        """Save analysis data to file"""
        try:
            analysis_file = self.data_dir / "analysis_data.json"
            analysis_dict = {
                "state": self.analysis_data.state.value,
                "recovery_failures": self.analysis_data.recovery_failures,
                "recovery_risk_reduction": self.analysis_data.recovery_risk_reduction,
                "session_start_balance": self.analysis_data.session_start_balance,
                "confirmation_deadline": self.analysis_data.confirmation_deadline.isoformat() if self.analysis_data.confirmation_deadline else None,
                "updated_at": datetime.now().isoformat()
            }
            
            with open(analysis_file, 'w') as f:
                json.dump(analysis_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error saving analysis data: {e}")
    
    async def handle_recovery_success(self) -> None:
        """Handle successful recovery"""
        logger.info("✅ Recovery success handled")
        self.analysis_data.recovery_failures = 0
        self.analysis_data.recovery_risk_reduction = 1.0
        self.switch_to_continuous_mode("Recovery successful")
        self._save_analysis_data()
    
    async def handle_recovery_failure(self) -> None:
        """Handle recovery failure"""
        self.analysis_data.recovery_failures += 1
        self.analysis_data.recovery_risk_reduction *= 0.8  # Reduce risk by 20%
        logger.warning(f"❌ Recovery failure #{self.analysis_data.recovery_failures}")
        self._save_analysis_data()
    
    async def check_continuous_mode_conditions(self, *args, **kwargs) -> bool:
        """Check if continuous mode conditions are met"""
        return True  # Simplified implementation
    
    def apply_continuous_mode_adjustments(self, params):
        """Apply continuous mode adjustments to parameters"""
        return params  # Return unchanged for now
    
    async def trigger_drawdown_analysis(self, *args, **kwargs) -> None:
        """Trigger drawdown analysis"""
        self.current_mode = TradingMode.RECOVERY
        self.recovery_mode = True
        self.analysis_data.state = EngineState.ANALYZING
        logger.info("🚨 Drawdown analysis triggered")
        self._save_analysis_data()
    
    def get_proposed_parameters(self):
        """Get proposed parameters"""
        return self.analysis_data.proposed_params
    
    def apply_recovery_risk_reduction(self, params):
        """Apply risk reduction to recovery parameters"""
        if hasattr(params, 'stake'):
            reduced_params = params.copy() if hasattr(params, 'copy') else params
            if hasattr(reduced_params, 'stake'):
                reduced_params.stake *= self.analysis_data.recovery_risk_reduction
            return reduced_params
        return params
    
    async def _execute_confirmation(self, confirmed: bool, auto_confirmed: bool = False) -> None:
        """Execute confirmation decision"""
        if confirmed:
            self.analysis_data.state = EngineState.ACTIVE
            logger.info(f"✅ Recovery confirmed {'(auto)' if auto_confirmed else '(manual)'}")
        else:
            self.analysis_data.state = EngineState.INACTIVE
            logger.info("❌ Recovery declined")
        self._save_analysis_data()

# Global instance
decision_engine: Optional[DecisionEngine] = None

def get_decision_engine(data_dir: Path) -> DecisionEngine:
    """Get or create decision engine instance"""
    global decision_engine
    if decision_engine is None:
        decision_engine = DecisionEngine(data_dir)
    return decision_engine