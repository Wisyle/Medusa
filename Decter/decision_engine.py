"""
Refined Decision Engine for Trading Bot

This module implements a decision engine that only triggers when max drawdown is reached,
analyzes market volatility, and proposes new parameters with admin confirmation.
"""

import asyncio
import json
import time
import traceback
import statistics
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

import config
import utils
from deriv_api import DerivAPI
from dict import ACCUMULATOR_INDICES, get_index

# Initialize logger
logger = utils.setup_logging()


class EngineState(Enum):
    """Current state of the decision engine."""
    INACTIVE = "inactive"
    ANALYZING = "analyzing" 
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class TradingMode(Enum):
    """Trading mode types."""
    CONTINUOUS = "continuous"
    RECOVERY = "recovery"


@dataclass
class VolatilityMetrics:
    """Volatility metrics for a trading pair."""
    symbol: str
    volatility_percentage: float
    price_swings: List[float]
    volatility_score: float  # 0-100 scale
    data_points: int
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RecoveryForecast:
    """Recovery mode forecasting data."""
    loss_to_recover: float
    estimated_trades_min: int
    estimated_trades_max: int
    recovery_probability: float
    required_win_rate: float
    risk_assessment: str
    time_estimate_minutes: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ProposedParameters:
    """Parameters proposed by the decision engine."""
    stake: float
    take_profit: float
    growth_rate: float
    frequency: str  # "low", "medium", "high"
    account_percentage: float
    volatility_reasoning: str
    trading_mode: TradingMode
    recovery_forecast: Optional[RecoveryForecast] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['trading_mode'] = self.trading_mode.value
        return data


@dataclass
class AnalysisData:
    """Current analysis data for the decision engine."""
    state: EngineState
    analysis_start_time: Optional[datetime]
    current_step: str
    thought_process: str
    volatility_data: Optional[VolatilityMetrics]
    proposed_params: Optional[ProposedParameters]
    confirmation_deadline: Optional[datetime]
    countdown_seconds: int
    auto_confirm: bool
    params_confirmed: bool = False  # Track if parameters were actually confirmed
    current_mode: TradingMode = TradingMode.CONTINUOUS
    daily_profit_target: float = 0.0
    session_start_balance: float = 0.0
    final_recovery_message_id: Optional[int] = None  # Track recovery result message
    recovery_failures: int = 0  # Track consecutive recovery failures
    recovery_risk_reduction: float = 1.0  # Risk reduction factor for failed recoveries
    
    def to_dict(self) -> Dict:
        return {
            'state': self.state.value,
            'analysis_start_time': self.analysis_start_time.isoformat() if self.analysis_start_time else None,
            'current_step': self.current_step,
            'thought_process': self.thought_process,
            'volatility_data': self.volatility_data.to_dict() if self.volatility_data else None,
            'proposed_params': self.proposed_params.to_dict() if self.proposed_params else None,
            'confirmation_deadline': self.confirmation_deadline.isoformat() if self.confirmation_deadline else None,
            'countdown_seconds': self.countdown_seconds,
            'auto_confirm': self.auto_confirm,
            'params_confirmed': self.params_confirmed,
            'current_mode': self.current_mode.value,
            'daily_profit_target': self.daily_profit_target,
            'session_start_balance': self.session_start_balance,
            'final_recovery_message_id': self.final_recovery_message_id,
            'recovery_failures': self.recovery_failures,
            'recovery_risk_reduction': self.recovery_risk_reduction
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AnalysisData':
        volatility_data = None
        if data.get('volatility_data'):
            vdata = data['volatility_data']
            volatility_data = VolatilityMetrics(
                symbol=vdata['symbol'],
                volatility_percentage=vdata['volatility_percentage'],
                price_swings=vdata['price_swings'],
                volatility_score=vdata['volatility_score'],
                data_points=vdata['data_points'],
                timestamp=datetime.fromisoformat(vdata['timestamp'])
            )
        
        proposed_params = None
        if data.get('proposed_params'):
            pdata = data['proposed_params']
            # Handle recovery forecast reconstruction
            recovery_forecast = None
            if pdata.get('recovery_forecast'):
                recovery_forecast = RecoveryForecast(**pdata['recovery_forecast'])
            
            # Reconstruct ProposedParameters
            proposed_params = ProposedParameters(
                stake=pdata['stake'],
                take_profit=pdata['take_profit'],
                growth_rate=pdata['growth_rate'],
                frequency=pdata['frequency'],
                account_percentage=pdata['account_percentage'],
                volatility_reasoning=pdata['volatility_reasoning'],
                trading_mode=TradingMode(pdata.get('trading_mode', 'continuous')),
                recovery_forecast=recovery_forecast
            )
            
        return cls(
            state=EngineState(data.get('state', 'inactive')),
            analysis_start_time=datetime.fromisoformat(data['analysis_start_time']) if data.get('analysis_start_time') else None,
            current_step=data.get('current_step', ''),
            thought_process=data.get('thought_process', ''),
            volatility_data=volatility_data,
            proposed_params=proposed_params,
            confirmation_deadline=datetime.fromisoformat(data['confirmation_deadline']) if data.get('confirmation_deadline') else None,
            countdown_seconds=data.get('countdown_seconds', 0),
            auto_confirm=data.get('auto_confirm', True),
            params_confirmed=data.get('params_confirmed', False),
            current_mode=TradingMode(data.get('current_mode', 'continuous')),
            daily_profit_target=data.get('daily_profit_target', 0.0),
            session_start_balance=data.get('session_start_balance', 0.0),
            final_recovery_message_id=data.get('final_recovery_message_id'),
            recovery_failures=data.get('recovery_failures', 0),
            recovery_risk_reduction=data.get('recovery_risk_reduction', 1.0)
        )


class RefinedDecisionEngine:
    """
    Decision engine that triggers only when max drawdown is reached,
    analyzes volatility, and proposes new parameters.
    """
    
    def __init__(self, api: DerivAPI, telegram_bot=None, trading_state=None):
        self.api = api
        self.telegram_bot = telegram_bot
        self.trading_state = trading_state  # Add reference to trading state
        self.analysis_data: AnalysisData = self._load_analysis_data()
        self.thought_process_task: Optional[asyncio.Task] = None
        self.thought_message_id: Optional[int] = None
        self.last_trade_history: List[Dict] = []
        self.resume_trading_signal: bool = False
        self._failed_recovery_indices: Dict[str, int] = {}  # Track failed recovery attempts per index
        
        # Define valid growth rates for Deriv API
        self.valid_growth_rates = [1.0, 2.0, 3.0, 4.0, 5.0]  # Only these rates are accepted by Deriv API
        
        # Account size thresholds for different trading strategies
        self.account_thresholds = {
            'small': 50.0,   # Less than 50 XRP
            'medium': 200.0,  # 50-200 XRP
            'large': 500.0    # 200+ XRP
        }
        
        # Risk adjustment for failed recoveries
        self.recovery_risk_reduction_per_failure = 0.15  # Reduce stake by 15% per failure
        
        logger.info("Refined Decision Engine initialized with dictionary-based index selection")

    def _validate_growth_rate(self, growth_rate: float) -> float:
        """
        Validate and round growth rate to the nearest valid value.
        Deriv API only accepts: 1%, 2%, 3%, 4%, 5%
        """
        if growth_rate <= 0:
            logger.warning(f"Invalid growth rate {growth_rate}%, using default 1%")
            return 1.0
        
        # Find the closest valid growth rate
        closest_rate = min(self.valid_growth_rates, key=lambda x: abs(x - growth_rate))
        
        if abs(closest_rate - growth_rate) > 0.1:  # More than 0.1% difference
            logger.info(f"Growth rate {growth_rate}% rounded to nearest valid rate: {closest_rate}%")
        
        return closest_rate

    def _load_analysis_data(self) -> AnalysisData:
        """Load analysis data from persistent storage."""
        try:
            data = utils.load_json_file(config.DECISION_ENGINE_STATE_FILE)
            if data:
                return AnalysisData.from_dict(data)
        except Exception as e:
            logger.warning(f"Could not load analysis data: {e}")
        
        # Return default inactive state
        return AnalysisData(
            state=EngineState.INACTIVE,
            analysis_start_time=None,
            current_step="",
            thought_process="",
            volatility_data=None,
            proposed_params=None,
            confirmation_deadline=None,
            countdown_seconds=0,
            auto_confirm=True,
            params_confirmed=False,
            current_mode=TradingMode.CONTINUOUS,
            daily_profit_target=0.0,
            session_start_balance=0.0,
            final_recovery_message_id=None,
            recovery_failures=0,
            recovery_risk_reduction=1.0
        )

    def _save_analysis_data(self):
        """Save analysis data to persistent storage."""
        try:
            utils.save_json_file(config.DECISION_ENGINE_STATE_FILE, self.analysis_data.to_dict())
        except Exception as e:
            logger.error(f"Failed to save analysis data: {e}")

    async def trigger_drawdown_analysis(self, current_balance: float, max_drawdown: float, trading_pair: str, trade_history: List[Dict]):
        """Trigger recovery mode analysis when max drawdown is reached."""
        logger.info(f"=== DECISION ENGINE TRIGGER REQUESTED ===")
        logger.info(f"Current state: {self.analysis_data.state.value}")
        logger.info(f"Max drawdown: {max_drawdown} XRP")
        logger.info(f"Current balance: {current_balance} XRP")
        logger.info(f"Trading pair: {trading_pair}")
        logger.info(f"Trade history length: {len(trade_history)}")
        
        if self.analysis_data.state != EngineState.INACTIVE:
            logger.warning(f"Analysis already in progress (state: {self.analysis_data.state.value}), ignoring trigger")
            return
            
        logger.info(f"✅ TRIGGERING RECOVERY MODE ANALYSIS - Max drawdown of {max_drawdown} XRP reached")
        
        try:
            # Start analysis but DON'T switch to recovery mode yet - wait until confirmation
            logger.info("Setting engine state to ANALYZING...")
            self.analysis_data.state = EngineState.ANALYZING
            self.analysis_data.analysis_start_time = datetime.now()
            self.analysis_data.current_step = "Initializing recovery mode analysis..."
            self.analysis_data.thought_process = "🚨 RECOVERY MODE ANALYSIS ACTIVATED - CALCULATING LOSS RECOVERY STRATEGY"
            self.last_trade_history = trade_history[-10:] if trade_history else []  # Last 10 trades
            
            logger.info(f"✅ State updated to: {self.analysis_data.state.value}")
            logger.info(f"Mode remains: {self.analysis_data.current_mode.value} (will switch to recovery after confirmation)")
            
            # Save the state first
            logger.info("Saving analysis data...")
            self._save_analysis_data()
            logger.info("✅ Analysis data saved to persistent storage")
            
            # Check if telegram bot is available before starting thought process
            if not self.telegram_bot:
                logger.error("❌ CRITICAL: No telegram bot available - thought process will not display!")
            else:
                logger.info(f"✅ Telegram bot available for thought process: {type(self.telegram_bot)}")
            
            # Start the thought process display FIRST
            logger.info("Starting thought process display...")
            await self._start_thought_process_display()
            logger.info("✅ Thought process display started")
            
            # Small delay to ensure thought process starts
            await asyncio.sleep(1)
            
            # Start the recovery analysis in the background
            logger.info("Creating recovery analysis task...")
            analysis_task = asyncio.create_task(self._run_recovery_analysis(current_balance, max_drawdown, trading_pair))
            logger.info(f"✅ Recovery analysis task created: {analysis_task}")
            
            # Don't await the task - let it run in background while thought process displays
            logger.info("Recovery analysis started in background - thought process should be visible")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL: Error in trigger_drawdown_analysis: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Reset state on error
            self.analysis_data.state = EngineState.INACTIVE
            self._save_analysis_data()
            
            # Send error notification if telegram bot is available
            if self.telegram_bot:
                try:
                    await utils.send_telegram_message(
                        self.telegram_bot,
                        f"❌ <b>RECOVERY ANALYSIS ERROR</b>\n\n"
                        f"Failed to start recovery mode analysis.\n"
                        f"Error: <code>{str(e)}</code>\n\n"
                        f"Please restart trading or contact support."
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to send error notification: {notify_error}")

    async def check_continuous_mode_conditions(self, consecutive_wins: int, current_balance: float, session_start_balance: float) -> Dict[str, Any]:
        """Check continuous mode conditions for profit targets and risk reduction."""
        result = {
            "should_reduce_risk": False,
            "should_stop_trading": False,
            "profit_target_reached": False,
            "message": ""
        }
        
        if self.analysis_data.current_mode != TradingMode.CONTINUOUS:
            return result
        
        # Calculate daily profit percentage
        daily_profit_pct = ((current_balance - session_start_balance) / session_start_balance * 100) if session_start_balance > 0 else 0.0
        
        # Check for consecutive wins threshold
        if consecutive_wins >= config.CONSECUTIVE_WIN_THRESHOLD:
            result["should_reduce_risk"] = True
            result["message"] = f"🎯 {consecutive_wins} consecutive wins achieved! Reducing risk to preserve profits."
        
        # Check daily profit targets
        if not self.analysis_data.daily_profit_target:
            # Set initial daily target between 3-5%
            import random
            self.analysis_data.daily_profit_target = random.uniform(config.DAILY_PROFIT_TARGET_MIN, config.DAILY_PROFIT_TARGET_MAX)
            self.analysis_data.session_start_balance = session_start_balance
            self._save_analysis_data()
        
        # Check if daily profit target reached
        if daily_profit_pct >= self.analysis_data.daily_profit_target:
            result["profit_target_reached"] = True
            # Calculate additional buffer target
            final_target = self.analysis_data.daily_profit_target + config.ADDITIONAL_PROFIT_BUFFER
            
            if daily_profit_pct >= final_target:
                result["should_stop_trading"] = True
                result["message"] = f"🎯 Final profit target of {final_target:.1f}% reached! Auto-stopping trading."
            else:
                remaining = final_target - daily_profit_pct
                result["message"] = f"📈 Daily target reached! {remaining:.1f}% more to final stop at {final_target:.1f}%"
        
        return result

    async def _start_thought_process_display(self):
        """Start the thought process display that updates every 3 seconds."""
        logger.info("=== STARTING THOUGHT PROCESS DISPLAY ===")
        
        # Check if telegram bot is available
        if not self.telegram_bot:
            logger.error("❌ CRITICAL: No telegram bot available for thought process display!")
            return
        else:
            logger.info(f"✅ Telegram bot available: {type(self.telegram_bot)}")
        
        if self.thought_process_task and not self.thought_process_task.done():
            logger.info("Cancelling existing thought process task")
            self.thought_process_task.cancel()
            try:
                await self.thought_process_task
            except asyncio.CancelledError:
                logger.info("Previous thought process task cancelled successfully")
            except Exception as e:
                logger.error(f"Error cancelling previous thought process task: {e}")
            
        logger.info("Creating new thought process loop task")
        try:
            self.thought_process_task = asyncio.create_task(self._thought_process_loop())
            logger.info(f"✅ Thought process task created successfully: {self.thought_process_task}")
            
            # Give the task a moment to start and send first message
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to create thought process task: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _thought_process_loop(self):
        """Main loop for updating the thought process display every 8 seconds."""
        logger.info("=== THOUGHT PROCESS LOOP STARTED ===")
        
        if not self.telegram_bot:
            logger.error("❌ CRITICAL: No telegram bot in thought process loop!")
            return
        
        try:
            loop_count = 0
            max_loops = 120  # Safety limit (16 minutes max with 8-second intervals)
            
            # Send initial message immediately
            logger.info("Sending initial thought process message...")
            await self._update_thought_display()
            logger.info("✅ Initial thought process message sent")
            
            while (self.analysis_data.state in [EngineState.ANALYZING, EngineState.AWAITING_CONFIRMATION] and 
                   loop_count < max_loops):
                loop_count += 1
                logger.debug(f"Thought process loop iteration {loop_count}, state: {self.analysis_data.state.value}")
                
                # Wait before updating (not before first message) - increased to avoid rate limits
                await asyncio.sleep(8)  # Update every 8 seconds to avoid Telegram flood control
                
                # Check if we should still continue
                if self.analysis_data.state not in [EngineState.ANALYZING, EngineState.AWAITING_CONFIRMATION]:
                    logger.info(f"State changed to {self.analysis_data.state.value}, ending thought process loop")
                    break
                
                # Update the display
                try:
                    await self._update_thought_display()
                    logger.debug(f"✅ Thought process updated (iteration {loop_count})")
                except Exception as e:
                    logger.error(f"❌ Error updating thought display in loop iteration {loop_count}: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Continue the loop even if one update fails
                
        except asyncio.CancelledError:
            logger.info("Thought process loop cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ CRITICAL: Error in thought process loop: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            logger.info("=== THOUGHT PROCESS LOOP ENDED ===")

    async def _update_thought_display(self):
        """Update the thought process display message."""
        try:
            if not self.telegram_bot:
                logger.error("❌ CRITICAL: No telegram bot available for thought display update")
                return
                
            # Build the current thought display
            logger.debug("Building thought display text...")
            display_text = self._build_thought_display()
            logger.debug(f"✅ Built thought display text (length: {len(display_text)})")
            
            if not display_text or len(display_text) < 10:
                logger.error(f"❌ Invalid thought display text: '{display_text}'")
                return
            
            if self.thought_message_id:
                # Edit existing message
                logger.debug(f"Editing existing thought message {self.thought_message_id}")
                try:
                    await self.telegram_bot.edit_message_text(
                        chat_id=config.GROUP_ID,
                        message_id=self.thought_message_id,
                        text=display_text,
                        parse_mode='HTML'
                    )
                    logger.debug(f"✅ Successfully edited thought message {self.thought_message_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to edit thought message {self.thought_message_id}: {e}")
                    logger.error(f"Error details: {type(e).__name__}: {str(e)}")
                    # Clear the message ID so we try to send a new one
                    self.thought_message_id = None
            
            if not self.thought_message_id:
                # Send new message
                logger.info("Creating new thought process message...")
                try:
                    msg = await utils.send_telegram_message(self.telegram_bot, display_text)
                    if msg and hasattr(msg, 'message_id'):
                        self.thought_message_id = msg.message_id
                        logger.info(f"✅ Created new thought message with ID {self.thought_message_id}")
                    else:
                        logger.error(f"❌ Failed to create new thought message - invalid response: {msg}")
                except Exception as e:
                    logger.error(f"❌ CRITICAL: Failed to send new thought message: {e}")
                    logger.error(f"Error details: {type(e).__name__}: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    
        except Exception as e:
            logger.error(f"❌ CRITICAL: Error in _update_thought_display: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _build_thought_display(self) -> str:
        """Build the thought process display text."""
        state = self.analysis_data
        current_time = datetime.now().strftime("%I:%M %p")
        
        if state.state == EngineState.ANALYZING:
            # Calculate elapsed time
            elapsed = "0s"
            if state.analysis_start_time:
                elapsed_seconds = (datetime.now() - state.analysis_start_time).total_seconds()
                elapsed = f"{elapsed_seconds:.0f}s"
            
            # Build analysis display
            display = (
                f"🧠 <b>[Bot Thought Process - Updated {current_time}]</b>\n"
                f"{'='*50}\n\n"
                f"🔥 <b>STATUS:</b> {state.current_step}\n"
                f"⏱️ <b>ELAPSED:</b> {elapsed}\n\n"
                f"💭 <b>CURRENT THOUGHTS:</b>\n"
                f"<pre>{state.thought_process}</pre>"
            )
            
            # Add volatility data if available
            if state.volatility_data:
                vol = state.volatility_data
                display += (
                    f"\n\n📊 <b>VOLATILITY ANALYSIS:</b>\n"
                    f"└ Pair: <code>{vol.symbol}</code>\n"
                    f"└ Volatility: <code>{vol.volatility_percentage:.1f}%</code>\n"
                    f"└ Score: <code>{vol.volatility_score:.0f}/100</code>\n"
                    f"└ Data Points: <code>{vol.data_points}</code>"
                )
                
        elif state.state == EngineState.AWAITING_CONFIRMATION:
            if state.proposed_params:
                params = state.proposed_params
                vol_data = state.volatility_data
                
                if params.trading_mode == TradingMode.RECOVERY:
                    # Recovery mode display with forecast
                    forecast = params.recovery_forecast
                    mode_title = "🚨 RECOVERY MODE CONFIRMATION"
                    mode_color = "🔥"
                    
                    display = (
                        f"🚨 <b>[{mode_title} - Updated {current_time}]</b>\n"
                        f"{'='*50}\n\n"
                        f"📊 <b>RECOVERY INDEX:</b> {vol_data.symbol if vol_data else 'Unknown'} | "
                        f"<b>VOLATILITY:</b> {vol_data.volatility_percentage:.1f}%\n\n"
                    )
                    
                    if forecast:
                        display += (
                            f"📊 <b>RECOVERY FORECAST:</b>\n"
                            f"└ Loss to Recover: <code>{forecast.loss_to_recover:.2f} XRP</code>\n"
                            f"└ Estimated Trades: <code>{forecast.estimated_trades_min}-{forecast.estimated_trades_max}</code>\n"
                            f"└ Recovery Probability: <code>{forecast.recovery_probability*100:.1f}%</code>\n"
                            f"└ Required Win Rate: <code>{forecast.required_win_rate*100:.1f}%</code>\n"
                            f"└ Time Estimate: <code>{forecast.time_estimate_minutes//60}h {forecast.time_estimate_minutes%60}m</code>\n"
                            f"└ Risk Level: <code>{forecast.risk_assessment}</code>\n\n"
                        )
                    
                    display += (
                        f"🎲 <b>RECOVERY PARAMETERS:</b>\n"
                        f"└ Stake: <code>{params.stake:.2f} XRP</code> ({params.account_percentage:.1f}% - HIGH RISK)\n"
                        f"└ Take Profit: <code>{params.take_profit:.0f}%</code>\n"
                        f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                        f"└ Frequency: <code>{params.frequency.upper()}</code>\n"
                        f"└ Mode: <code>RECOVERY</code> 🚨\n\n"
                        f"🧮 <b>STRATEGY:</b>\n"
                        f"<pre>{params.volatility_reasoning}</pre>\n\n"
                        f"⏰ <b>CONFIRM RECOVERY?</b> (Yes/No, auto-confirm in <code>{state.countdown_seconds}s</code>)"
                    )
                else:
                    # Continuous mode display
                    display = (
                        f"🎯 <b>[Bot Thought Process - Updated {current_time}]</b>\n"
                        f"{'='*50}\n\n"
                        f"📊 <b>PAIR:</b> {vol_data.symbol if vol_data else 'Unknown'} | "
                        f"<b>VOLATILITY:</b> {vol_data.volatility_percentage:.1f}% | "
                        f"<b>MODE:</b> CONTINUOUS\n\n"
                        f"📈 <b>PAST TRADES:</b> {self._get_trade_summary()}\n\n"
                        f"🎲 <b>PROPOSED PARAMETERS:</b>\n"
                        f"└ Stake: <code>{params.stake:.2f} XRP</code> ({params.account_percentage:.1f}% of account)\n"
                        f"└ Take Profit: <code>{params.take_profit:.0f}%</code>\n"
                        f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                        f"└ Frequency: <code>{params.frequency.upper()}</code>\n\n"
                        f"🧮 <b>REASONING:</b>\n"
                        f"<pre>{params.volatility_reasoning}</pre>\n\n"
                        f"⏰ <b>CONFIRM?</b> (Yes/No, auto-confirm in <code>{state.countdown_seconds}s</code>)"
                    )
            else:
                display = "❌ <b>Error:</b> No proposed parameters available"
        else:
            display = "💤 <b>Decision Engine Inactive</b>"
            
        return display

    def _get_trade_summary(self) -> str:
        """Get a summary of recent trade performance."""
        if not self.last_trade_history:
            return "No recent trades"
            
        wins = sum(1 for trade in self.last_trade_history if trade.get('win', False))
        losses = len(self.last_trade_history) - wins
        
        # Calculate average duration (simplified)
        avg_duration = "5m"  # Placeholder - would calculate from actual trade data
        
        return f"{wins} Wins, {losses} Losses | Avg. Duration: {avg_duration}"

    async def _run_recovery_analysis(self, current_balance: float, loss_amount: float, trading_pair: str):
        """Run the complete recovery mode analysis process."""
        logger.info(f"=== STARTING RECOVERY ANALYSIS ===")
        logger.info(f"Balance: {current_balance}, Loss: {loss_amount}, Pair: {trading_pair}")
        
        try:
            # Step 1: Analyze ALL available indices to find the best one for recovery
            logger.info("Step 1: Analyzing all indices...")
            await self._analyze_all_indices()
            logger.info("✅ Index analysis complete")
            
            # Step 2: Calculate recovery forecast
            logger.info("Step 2: Calculating recovery forecast...")
            await self._calculate_recovery_forecast(current_balance, loss_amount)
            logger.info("✅ Recovery forecast complete")
            
            # Step 3: Calculate optimal recovery parameters 
            logger.info("Step 3: Calculating recovery parameters...")
            await self._calculate_recovery_parameters(current_balance, loss_amount)
            logger.info("✅ Recovery parameters calculated")
            
            # Step 4: Request confirmation
            logger.info("Step 4: Requesting admin confirmation...")
            await self._request_admin_confirmation()
            logger.info("✅ Confirmation request sent")
            
        except Exception as e:
            logger.error(f"Error in recovery analysis: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.analysis_data.state = EngineState.INACTIVE
            self._save_analysis_data()
            logger.info("Engine state reset to inactive due to error")
    
    async def _run_complete_analysis(self, current_balance: float, trading_pair: str):
        """Run the complete analysis process for continuous mode."""
        try:
            # Step 1: Analyze ALL available indices to find the best one
            await self._analyze_all_indices()
            
            # Step 2: Calculate optimal parameters for the best index
            await self._calculate_optimal_parameters(current_balance)
            
            # Step 3: Request confirmation
            await self._request_admin_confirmation()
            
        except Exception as e:
            logger.error(f"Error in complete analysis: {e}")
            self.analysis_data.state = EngineState.INACTIVE
            self._save_analysis_data()

    async def _analyze_all_indices(self):
        """Analyze volatility and performance for ALL available indices, completely excluding problematic pairs."""
        
        # Get excluded indices using the new comprehensive exclusion logic
        excluded_indices = self._get_excluded_indices_for_recovery()
        logger.info(f"Completely excluding indices for recovery: {excluded_indices}")
        
        # Use dict.py data to prioritize indices by volatility for recovery mode
        available_indices_from_dict = []
        for symbol, data in ACCUMULATOR_INDICES.items():
            if symbol not in excluded_indices:
                available_indices_from_dict.append({
                    'symbol': symbol,
                    'volatility': data['volatility_pct'],
                    'risk_level': data['risk_level']
                })
        
        # Sort by volatility (lowest first for recovery)
        available_indices_from_dict.sort(key=lambda x: x['volatility'])
        
        self.analysis_data.current_step = "Scanning safe indices for optimal recovery using volatility data..."
        self.analysis_data.thought_process = (
            f"🔍 Scanning {len(available_indices_from_dict)} safe indices (excluded {len(excluded_indices)})...\n"
            f"📊 Using volatility data from index dictionary...\n"
            f"❌ EXCLUDED INDICES: {', '.join(excluded_indices)}\n"
            f"🎯 Prioritizing low volatility for recovery safety..."
        )
        self._save_analysis_data()
        
        index_analysis = {}
        total_indices = len(available_indices_from_dict)
        
        for i, index_info in enumerate(available_indices_from_dict):
            symbol = index_info['symbol']
            dict_volatility = index_info['volatility']
            
            self.analysis_data.current_step = f"Analyzing {symbol} ({i+1}/{total_indices}) - Vol: {dict_volatility}%..."
            self.analysis_data.thought_process = (
                f"📊 Progress: {i+1}/{total_indices} safe indices analyzed\n"
                f"🔍 Current: {symbol} (Dict Volatility: {dict_volatility}%)\n"
                f"📈 Fetching fresh tick data for validation...\n"
                f"⚡ Computing recovery-optimized scores...\n"
                f"🎯 Prioritizing stability and safety..."
            )
            self._save_analysis_data()
            
            # Try to get live data, but use dict.py data as backup
            analysis = await self._analyze_index_performance(symbol)
            if not analysis:
                # Use dict.py data as fallback
                logger.info(f"Using dict.py fallback data for {symbol}")
                analysis = {
                    'symbol': symbol,
                    'volatility_percentage': dict_volatility,
                    'mean_return': 0.0,
                    'price_swings': [],
                    'volatility_score': max(10, 110 - dict_volatility),  # Lower volatility = higher score
                    'stability_score': max(10, 110 - dict_volatility),
                    'risk_score': max(10, 110 - dict_volatility),
                    'recovery_score': max(10, 110 - dict_volatility),
                    'total_score': max(10, 110 - dict_volatility),
                    'data_points': 0,  # Flag for dict.py data
                    'return_consistency': 1.0
                }
            
            # Apply recovery-specific scoring adjustments for ALL indices
            if self.analysis_data.current_mode == TradingMode.RECOVERY:
                # For recovery mode, heavily prioritize low volatility using dict.py data
                recovery_score = self._calculate_recovery_score_with_dict_data(analysis, symbol, dict_volatility)
                analysis['recovery_optimized_score'] = recovery_score
                analysis['original_score'] = analysis['total_score']  # Keep original for reference
                analysis['total_score'] = recovery_score  # Use recovery score for ranking
            
            index_analysis[symbol] = analysis
            logger.info(f"Analyzed {symbol}: dict_vol={dict_volatility}%, live_vol={analysis['volatility_percentage']:.1f}%, recovery_score={analysis.get('recovery_optimized_score', analysis['total_score']):.4f}")
            
            # Brief pause to avoid rate limits and show progress (5 seconds per index)
            await asyncio.sleep(5.0)
        
        # Rank indices by recovery-optimized score (best to worst)
        if index_analysis:
            ranked_indices = sorted(
                index_analysis.items(),
                key=lambda x: x[1]['total_score'],  # This now contains the recovery-optimized score
                reverse=True
            )
            
            best_symbol, best_analysis = ranked_indices[0]
            
            # Store the best analysis as volatility_data
            dict_data = get_index(best_symbol)
            actual_volatility = dict_data['volatility_pct'] if dict_data else best_analysis['volatility_percentage']
            
            self.analysis_data.volatility_data = VolatilityMetrics(
                symbol=best_symbol,
                volatility_percentage=actual_volatility,
                price_swings=best_analysis['price_swings'][-20:] if best_analysis['price_swings'] else [],
                volatility_score=best_analysis['volatility_score'],
                data_points=best_analysis['data_points'],
                timestamp=datetime.now()
            )
            
            # Create summary of top 3 indices with recovery info
            top_3 = ranked_indices[:3]
            top_summary = "\n".join([
                f"{i+1}. {symbol}: Score {data['total_score']:.3f} (Dict Vol: {get_index(symbol)['volatility_pct'] if get_index(symbol) else 'N/A'}%)"
                for i, (symbol, data) in enumerate(top_3)
            ])
            
            dict_info = get_index(best_symbol)
            self.analysis_data.thought_process = (
                f"✅ Safe recovery analysis complete! Scanned {len(index_analysis)} safe indices\n\n"
                f"❌ COMPLETELY EXCLUDED: {', '.join(excluded_indices)}\n\n"
                f"🏆 TOP 3 SAFE RECOVERY CANDIDATES:\n{top_summary}\n\n"
                f"🎯 Selected for Recovery: {best_symbol}\n"
                f"📊 Dict Volatility: {dict_info['volatility_pct'] if dict_info else 'Unknown'}% (Lower = Safer)\n"
                f"🛡️ Risk Level: {dict_info['risk_level'] if dict_info else 'Unknown'}\n"
                f"🎲 Recovery Score: {best_analysis['total_score']:.3f}\n"
                f"📈 Data source: {'Live + Dict' if best_analysis['data_points'] > 0 else 'Dict.py fallback'}"
            )
            self._save_analysis_data()
            
        else:
            logger.warning("No safe indices could be analyzed - using safest fallback from dict.py")
            # Use the safest option from dict.py
            safest_indices = sorted(ACCUMULATOR_INDICES.items(), key=lambda x: x[1]['volatility_pct'])
            if safest_indices:
                for symbol, data in safest_indices:
                    if symbol not in excluded_indices:
                        fallback_symbol = symbol
                        fallback_volatility = data['volatility_pct']
                        break
                else:
                    # If all are excluded, use the safest one anyway
                    fallback_symbol = safest_indices[0][0]
                    fallback_volatility = safest_indices[0][1]['volatility_pct']
            else:
                fallback_symbol = "R_10"
                fallback_volatility = 10.0
                
            self.analysis_data.volatility_data = VolatilityMetrics(
                symbol=fallback_symbol,
                volatility_percentage=fallback_volatility,
                price_swings=[],
                volatility_score=50.0,
                data_points=0,
                timestamp=datetime.now()
            )

    def _calculate_recovery_score_with_dict_data(self, analysis: Dict, symbol: str, dict_volatility: float) -> float:
        """Calculate recovery-optimized score using both live data and dict.py volatility data."""
        
        # Base scores from analysis
        volatility_score = analysis['volatility_score']  # Higher = lower volatility (good)
        stability_score = analysis['stability_score']    # Higher = more stable (good)
        risk_score = analysis['risk_score']              # Higher = lower risk (good)
        
        # Use dict.py volatility as primary reference for recovery mode
        dict_volatility_score = max(10, 110 - dict_volatility)  # Lower volatility = higher score
        
        # Weight the scores - prioritize dict.py data for consistency
        combined_volatility_score = (dict_volatility_score * 0.7) + (volatility_score * 0.3)
        
        # Recovery-specific score calculation with heavy emphasis on low volatility
        recovery_score = (
            combined_volatility_score * 0.5 +  # 50% weight on low volatility (highest priority)
            stability_score * 0.25 +           # 25% weight on stability
            risk_score * 0.15 +                # 15% weight on low risk
            analysis['recovery_score'] * 0.1   # 10% weight on recovery potential
        )
        
        # Additional bonuses/penalties based on dict.py volatility
        if dict_volatility <= 2.0:
            recovery_score += 25  # Huge bonus for very low volatility
        elif dict_volatility <= 5.0:
            recovery_score += 15  # Good bonus for low volatility
        elif dict_volatility <= 10.0:
            recovery_score += 5   # Small bonus for moderate volatility
        elif dict_volatility > 20.0:
            recovery_score -= 20  # Penalty for high volatility
        elif dict_volatility > 15.0:
            recovery_score -= 10  # Small penalty for elevated volatility
        
        # Progressive failure penalty for indices that have failed before
        if hasattr(self, '_failed_recovery_indices'):
            failure_count = self._failed_recovery_indices.get(symbol, 0)
            recovery_score -= (failure_count * 15)  # -15 points per previous failure
        
        # Cap the score to reasonable range
        recovery_score = max(5, min(100, recovery_score))
        
        logger.info(f"Recovery score for {symbol}: dict_vol={dict_volatility}%, combined_score={recovery_score:.2f}")
        return recovery_score

    def _calculate_recovery_score(self, analysis: Dict, symbol: str, losing_pair: str) -> float:
        """Calculate recovery-optimized score that heavily favors stability and low volatility."""
        
        # Base scores from analysis
        volatility_score = analysis['volatility_score']  # Higher = lower volatility (good)
        stability_score = analysis['stability_score']    # Higher = more stable (good)
        risk_score = analysis['risk_score']              # Higher = lower risk (good)
        
        # Recovery-specific adjustments
        recovery_score = (
            volatility_score * 0.4 +      # 40% weight on low volatility (increased from 25%)
            stability_score * 0.3 +       # 30% weight on stability (increased from 15%)
            risk_score * 0.2 +            # 20% weight on low risk
            analysis['recovery_score'] * 0.1  # 10% weight on recovery potential (reduced)
        )
        
        # Bonus for very low volatility (recovery preference)
        if analysis['volatility_percentage'] < 3.0:
            recovery_score += 20  # Significant bonus for very stable pairs
        elif analysis['volatility_percentage'] < 5.0:
            recovery_score += 10  # Good bonus for stable pairs
        elif analysis['volatility_percentage'] > 10.0:
            recovery_score -= 15  # Penalty for high volatility in recovery
        
        # Heavy penalty if this is the losing pair
        if symbol == losing_pair:
            recovery_score -= 50  # Make it very unlikely to be selected
            logger.info(f"Applied losing pair penalty to {symbol}: -50 points")
        
        # Cap the score to reasonable range
        recovery_score = max(0, min(100, recovery_score))
        
        return recovery_score

    async def _analyze_index_performance(self, symbol: str) -> Optional[Dict]:
        """Analyze performance metrics for a single index."""
        try:
            logger.debug(f"Starting analysis for {symbol}")
            
            # Fetch fresh tick data for this symbol
            tick_data = await self._fetch_tick_data(symbol, 300)
            if not tick_data or len(tick_data) < 10:
                logger.warning(f"Insufficient tick data for {symbol}: {len(tick_data) if tick_data else 0} points")
                return None
            
            # Extract prices
            prices = [tick['price'] for tick in tick_data]
            
            # Calculate volatility (standard deviation of returns)
            returns = []
            for i in range(1, len(prices)):
                return_val = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(return_val)
            
            if len(returns) < 5:
                logger.warning(f"Insufficient returns data for {symbol}: {len(returns)} returns")
                return None
            
            # Calculate volatility metrics
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0
            volatility_percentage = volatility * 100
            mean_return = statistics.mean(returns)
            
            # Calculate price swings (for additional analysis)
            price_swings = []
            for i in range(1, len(prices)):
                swing = abs(prices[i] - prices[i-1]) / prices[i-1] * 100
                price_swings.append(swing)
            
            # Calculate stability score (inverse of volatility, scaled 0-100)
            # Lower volatility = higher stability score
            if volatility_percentage > 0:
                stability_score = max(0, min(100, (10 / volatility_percentage) * 10))
            else:
                stability_score = 100
            
            # Calculate volatility score (0-100, higher = lower volatility = better)
            if volatility_percentage <= 1:
                volatility_score = 100
            elif volatility_percentage <= 3:
                volatility_score = 80
            elif volatility_percentage <= 5:
                volatility_score = 60
            elif volatility_percentage <= 10:
                volatility_score = 40
            elif volatility_percentage <= 15:
                volatility_score = 20
            else:
                volatility_score = 5
            
            # Calculate risk score (combination of volatility and return consistency)
            return_consistency = 1 / (statistics.stdev(returns) + 0.001)  # Higher = more consistent
            risk_score = min(100, (return_consistency * 20) + (volatility_score * 0.5))
            
            # Calculate recovery potential (balance of volatility and mean return)
            if mean_return > 0:
                recovery_potential = min(100, (abs(mean_return) * 1000) + (50 - volatility_percentage))
            else:
                recovery_potential = max(0, 50 - volatility_percentage)
            
            # Calculate total score (standard scoring before recovery optimization)
            total_score = (
                volatility_score * 0.25 +      # 25% weight on low volatility
                stability_score * 0.15 +       # 15% weight on stability
                risk_score * 0.25 +            # 25% weight on low risk
                recovery_potential * 0.35      # 35% weight on recovery potential
            )
            
            # Create analysis result
            analysis = {
                'symbol': symbol,
                'volatility_percentage': volatility_percentage,
                'mean_return': mean_return,
                'price_swings': price_swings[-20:],  # Keep last 20 swings
                'volatility_score': volatility_score,
                'stability_score': stability_score,
                'risk_score': risk_score,
                'recovery_score': recovery_potential,
                'total_score': total_score,
                'data_points': len(tick_data),
                'return_consistency': return_consistency
            }
            
            logger.debug(f"Analysis complete for {symbol}: volatility={volatility_percentage:.2f}%, score={total_score:.2f}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    async def _calculate_optimal_parameters(self, current_balance: float):
        """Calculate optimal trading parameters based on comprehensive analysis."""
        self.analysis_data.current_step = "Calculating optimal parameters..."
        self.analysis_data.thought_process = (
            f"🧮 Account Balance: {current_balance:.2f} XRP\n"
            f"📊 Best Index: {self.analysis_data.volatility_data.symbol}\n"
            f"📈 Volatility: {self.analysis_data.volatility_data.volatility_percentage:.1f}%\n"
            f"🎯 Calculating risk-adjusted parameters..."
        )
        self._save_analysis_data()
        
        vol_data = self.analysis_data.volatility_data
        if not vol_data:
            logger.error("No volatility data available for parameter calculation")
            return
        
        # Determine account size category
        if current_balance < self.account_thresholds['small']:
            account_category = 'small'
            base_percentage = 0.8  # More conservative for small accounts
        elif current_balance < self.account_thresholds['medium']:
            account_category = 'medium'
            base_percentage = 1.5  # Moderate for medium accounts
        else:
            account_category = 'large'
            base_percentage = 2.5  # More aggressive for large accounts
        
        # Advanced volatility-based adjustments with extreme volatility support
        if vol_data.volatility_percentage >= 250:
            # Ultra-extreme volatility (1HZ250V) - survival mode settings
            volatility_factor = 0.1
            frequency = 'low'
            take_profit_base = 5.0  # Ultra-conservative for 250% volatility
        elif vol_data.volatility_percentage >= 150:
            # Extreme volatility (1HZ150V) - maximum caution
            volatility_factor = 0.15
            frequency = 'low'
            take_profit_base = 8.0  # Very conservative for 150% volatility
        elif vol_data.volatility_percentage > 100:
            # High-extreme volatility - maximum caution
            volatility_factor = 0.2
            frequency = 'low'
            take_profit_base = 10.0
        elif vol_data.volatility_percentage > 75:
            # Very high volatility - maximum caution
            volatility_factor = 0.25
            frequency = 'low'
            take_profit_base = 15.0
        elif vol_data.volatility_percentage > 50:
            # High volatility - reduce stake significantly
            volatility_factor = 0.3
            frequency = 'low'
            take_profit_base = 20.0
        elif vol_data.volatility_percentage > 25:
            # Medium-high volatility
            volatility_factor = 0.4
            frequency = 'low'
            take_profit_base = 25.0
        elif vol_data.volatility_percentage > 10:
            # Medium volatility
            volatility_factor = 0.6
            frequency = 'medium'
            take_profit_base = 35.0
        elif vol_data.volatility_percentage > 5:
            # Low-medium volatility
            volatility_factor = 0.8
            frequency = 'medium'
            take_profit_base = 45.0
        else:
            # Very low volatility - can be more aggressive
            volatility_factor = 1.0
            frequency = 'high'
            take_profit_base = 55.0
        
        # Calculate final stake with additional safety margin for recovery
        recovery_margin = 0.8  # 20% additional safety for recovery scenarios
        calculated_stake = (current_balance * base_percentage / 100.0) * volatility_factor * recovery_margin
        stake = max(0.5, calculated_stake)  # Minimum 0.5 XRP
        
        # Adjust if calculated stake is less than minimum
        final_account_percentage = (stake / current_balance) * 100.0
        
        # Calculate take profit with volatility adjustment
        take_profit = take_profit_base
        
        # Conservative growth rate for recovery
        growth_rate = self._validate_growth_rate(1.0)  # Always 1% for safety during recovery
        
        # Create comprehensive reasoning
        reasoning = (
            f"🏆 SELECTED INDEX: {vol_data.symbol}\n"
            f"💰 Account: {account_category.upper()} ({current_balance:.0f} XRP)\n"
            f"📊 Volatility: {vol_data.volatility_percentage:.1f}% ({frequency} risk)\n"
            f"🎯 Recovery Mode: Extra safety margin applied\n"
            f"💸 Stake: {final_account_percentage:.1f}% of account = {stake:.2f} XRP\n"
            f"🎪 Take-Profit: {take_profit:.0f}% (volatility-adjusted)\n"
            f"📈 Growth: {growth_rate:.1f}% (conservative for recovery)\n"
            f"⚡ Frequency: {frequency.upper()} (risk-based)"
        )
        
        self.analysis_data.proposed_params = ProposedParameters(
            stake=stake,
            take_profit=take_profit,
            growth_rate=growth_rate,
            frequency=frequency,
            account_percentage=final_account_percentage,
            volatility_reasoning=reasoning,
            trading_mode=TradingMode.CONTINUOUS
        )
        
        self.analysis_data.thought_process = (
            f"✅ Recovery parameters calculated!\n"
            f"🏆 Best Index: {vol_data.symbol}\n"
            f"💰 Stake: {stake:.2f} XRP ({final_account_percentage:.1f}%)\n"
            f"🎯 Take-Profit: {take_profit:.0f}%\n"
            f"📈 Growth Rate: {growth_rate:.1f}%\n"
            f"⚡ Frequency: {frequency.upper()}\n"
            f"🛡️ Recovery mode with enhanced safety"
        )
        self._save_analysis_data()

    async def _calculate_recovery_forecast(self, current_balance: float, loss_amount: float):
        """Calculate detailed recovery forecast for the loss amount."""
        self.analysis_data.current_step = "Calculating recovery forecast..."
        self.analysis_data.thought_process = (
            f"🔍 RECOVERY FORECAST CALCULATION\n"
            f"💸 Loss to Recover: {loss_amount:.2f} XRP\n"
            f"💰 Current Balance: {current_balance:.2f} XRP\n"
            f"🧮 Computing recovery scenarios..."
        )
        self._save_analysis_data()
        
        vol_data = self.analysis_data.volatility_data
        if not vol_data:
            logger.error("No volatility data available for recovery forecast")
            return
        
        # Recovery parameters (more aggressive than normal)
        recovery_stake_pct = 2.0 * config.RECOVERY_RISK_MULTIPLIER  # Higher risk for recovery
        recovery_stake = (current_balance * recovery_stake_pct / 100.0)
        recovery_stake = max(0.5, min(recovery_stake, current_balance * 0.1))  # Cap at 10% of balance
        
        # Take profit based on volatility (higher for recovery)
        if vol_data.volatility_percentage > 10:
            recovery_take_profit = 35.0
        elif vol_data.volatility_percentage > 5:
            recovery_take_profit = 50.0
        else:
            recovery_take_profit = 65.0
        
        # Calculate expected profit per trade
        expected_profit_per_trade = recovery_stake * (recovery_take_profit / 100.0)
        
        # Estimate number of trades needed
        trades_needed_optimal = max(1, math.ceil(loss_amount / expected_profit_per_trade))
        trades_needed_conservative = max(1, math.ceil(loss_amount * config.RECOVERY_SAFETY_MARGIN / expected_profit_per_trade))
        
        # Estimate win rate needed
        # Assuming some losses, calculate required win rate
        assumed_loss_rate = 0.3  # Assume 30% loss rate
        required_wins = math.ceil(trades_needed_optimal / (1 - assumed_loss_rate))
        required_win_rate = (trades_needed_optimal / required_wins) if required_wins > 0 else 0.8
        
        # Calculate recovery probability based on volatility and market conditions
        if vol_data.volatility_percentage > 15:
            base_probability = 0.6  # Lower probability in high volatility
        elif vol_data.volatility_percentage > 10:
            base_probability = 0.7
        elif vol_data.volatility_percentage > 5:
            base_probability = 0.8
        else:
            base_probability = 0.85  # Higher probability in stable markets
        
        # Adjust probability based on loss amount vs balance ratio
        loss_ratio = loss_amount / current_balance
        if loss_ratio > 0.5:
            probability_adjustment = 0.8  # Reduce probability for large losses
        elif loss_ratio > 0.3:
            probability_adjustment = 0.9
        else:
            probability_adjustment = 1.0
        
        recovery_probability = base_probability * probability_adjustment
        
        # Risk assessment
        if recovery_probability > 0.8:
            risk_assessment = "LOW RISK - High confidence recovery"
        elif recovery_probability > 0.7:
            risk_assessment = "MEDIUM RISK - Good recovery chances"
        elif recovery_probability > 0.6:
            risk_assessment = "HIGH RISK - Recovery possible but challenging"
        else:
            risk_assessment = "VERY HIGH RISK - Recovery uncertain"
        
        # Time estimate (assuming average trade duration based on take profit)
        # Higher take profit = longer duration per trade
        avg_trade_duration_minutes = 3 + (recovery_take_profit / 100.0) * 10  # 3-13 minutes per trade
        time_estimate_minutes = int(trades_needed_conservative * avg_trade_duration_minutes)
        
        # Create recovery forecast
        recovery_forecast = RecoveryForecast(
            loss_to_recover=loss_amount,
            estimated_trades_min=trades_needed_optimal,
            estimated_trades_max=min(trades_needed_conservative, config.RECOVERY_MAX_TRADES),
            recovery_probability=recovery_probability,
            required_win_rate=required_win_rate,
            risk_assessment=risk_assessment,
            time_estimate_minutes=time_estimate_minutes
        )
        
        # Update thought process with forecast
        self.analysis_data.thought_process = (
            f"📊 RECOVERY FORECAST COMPLETE\n\n"
            f"💸 Loss to Recover: {loss_amount:.2f} XRP\n"
            f"📈 Expected Profit/Trade: {expected_profit_per_trade:.2f} XRP\n"
            f"🎯 Estimated Trades: {trades_needed_optimal}-{trades_needed_conservative}\n"
            f"📊 Required Win Rate: {required_win_rate*100:.1f}%\n"
            f"🎲 Recovery Probability: {recovery_probability*100:.1f}%\n"
            f"⏰ Estimated Time: {time_estimate_minutes//60}h {time_estimate_minutes%60}m\n"
            f"⚠️ Risk Level: {risk_assessment}\n\n"
            f"🔍 Using optimized {vol_data.symbol} with {recovery_take_profit:.0f}% TP"
        )
        
        # Store forecast for later use
        self._recovery_forecast = recovery_forecast
        self._save_analysis_data()

    async def _calculate_recovery_parameters(self, current_balance: float, loss_amount: float):
        """Calculate optimized parameters specifically for recovery mode."""
        self.analysis_data.current_step = "Calculating recovery parameters..."
        self.analysis_data.thought_process = (
            f"🛠️ RECOVERY PARAMETER OPTIMIZATION\n"
            f"💰 Account Balance: {current_balance:.2f} XRP\n"
            f"📊 Best Recovery Index: {self.analysis_data.volatility_data.symbol}\n"
            f"🎯 Applying recovery multipliers..."
        )
        self._save_analysis_data()
        
        vol_data = self.analysis_data.volatility_data
        if not vol_data:
            logger.error("No volatility data available for recovery parameters")
            return
        
        # Recovery mode uses higher risk, medium frequency
        recovery_stake_pct = 2.0 * config.RECOVERY_RISK_MULTIPLIER
        calculated_stake = (current_balance * recovery_stake_pct / 100.0)
        stake = max(0.5, min(calculated_stake, current_balance * 0.1))  # Cap at 10% balance
        
        final_account_percentage = (stake / current_balance) * 100.0
        
        # Recovery take profit based on volatility (more conservative for extreme volatility)
        if vol_data.volatility_percentage >= 250:  # Ultra-extreme volatility (1HZ250V)
            take_profit = 5.0  # Ultra-conservative for 250% volatility
        elif vol_data.volatility_percentage >= 150:  # Extreme volatility (1HZ150V)
            take_profit = 10.0  # Very conservative for 150% volatility
        elif vol_data.volatility_percentage > 100:  # High-extreme volatility
            take_profit = 15.0  # Conservative for >100% volatility
        elif vol_data.volatility_percentage > 75:  # High volatility
            take_profit = 20.0
        elif vol_data.volatility_percentage > 50:  # Medium-high volatility
            take_profit = 25.0
        elif vol_data.volatility_percentage > 25:  # Medium volatility
            take_profit = 35.0
        elif vol_data.volatility_percentage > 10:  # Low-medium volatility
            take_profit = 45.0
        else:
            take_profit = 55.0  # Conservative for very low volatility
        
        # Conservative growth rate for safety (use valid API rate)
        growth_rate = self._validate_growth_rate(1.0)  # Use 1% for safety in recovery
        
        # Medium frequency as specified
        frequency = config.RECOVERY_FREQUENCY
        
        # Recovery-specific reasoning
        reasoning = (
            f"🚨 RECOVERY MODE PARAMETERS\n"
            f"🏆 Selected Index: {vol_data.symbol}\n"
            f"💰 Account: {current_balance:.0f} XRP\n"
            f"📊 Volatility: {vol_data.volatility_percentage:.1f}% (recovery optimized)\n"
            f"🎯 Recovery Target: {loss_amount:.2f} XRP\n"
            f"💸 Stake: {final_account_percentage:.1f}% = {stake:.2f} XRP (HIGH RISK)\n"
            f"🎪 Take-Profit: {take_profit:.0f}% (recovery tuned)\n"
            f"📈 Growth: {growth_rate:.1f}% (conservative safety)\n"
            f"⚡ Frequency: {frequency.upper()} (balanced recovery)\n"
            f"🛡️ Safety Cap: Max 10% of balance per trade"
        )
        
        # Create proposed parameters with recovery forecast
        self.analysis_data.proposed_params = ProposedParameters(
            stake=stake,
            take_profit=take_profit,
            growth_rate=growth_rate,
            frequency=frequency,
            account_percentage=final_account_percentage,
            volatility_reasoning=reasoning,
            trading_mode=TradingMode.RECOVERY,
            recovery_forecast=self._recovery_forecast if hasattr(self, '_recovery_forecast') else None
        )
        
        self.analysis_data.thought_process = (
            f"✅ RECOVERY PARAMETERS READY!\n\n"
            f"🏆 Best Recovery Index: {vol_data.symbol}\n"
            f"💰 Stake: {stake:.2f} XRP ({final_account_percentage:.1f}%)\n"
            f"🎯 Take-Profit: {take_profit:.0f}%\n"
            f"📈 Growth Rate: {growth_rate:.1f}%\n"
            f"⚡ Frequency: {frequency.upper()}\n"
            f"🚨 Mode: RECOVERY (High Risk/Medium Freq)\n\n"
            f"📊 Recovery forecast shows {self._recovery_forecast.estimated_trades_min}-{self._recovery_forecast.estimated_trades_max} trades needed\n"
            f"🎲 Success probability: {self._recovery_forecast.recovery_probability*100:.1f}%"
        )
        self._save_analysis_data()

    async def _request_admin_confirmation(self):
        """Request admin confirmation with 90-second countdown."""
        logger.info("Requesting admin confirmation with 90-second countdown")
        
        self.analysis_data.state = EngineState.AWAITING_CONFIRMATION
        self.analysis_data.confirmation_deadline = datetime.now() + timedelta(seconds=90)
        self.analysis_data.countdown_seconds = 90
        self._save_analysis_data()
        
        logger.info("Starting countdown task...")
        # Start countdown immediately
        countdown_task = asyncio.create_task(self._countdown_loop())
        
        # Don't await the countdown task - let it run in the background
        logger.info("Countdown task started - admin has 90 seconds to respond")

    async def _countdown_loop(self):
        """Countdown loop that updates every 8 seconds."""
        logger.info("Starting countdown loop - 90 seconds until auto-confirm")
        
        while (self.analysis_data.state == EngineState.AWAITING_CONFIRMATION and 
               self.analysis_data.countdown_seconds > 0):
            
            logger.debug(f"Countdown: {self.analysis_data.countdown_seconds} seconds remaining")
            await asyncio.sleep(8)  # Wait 8 seconds (increased from 3 to avoid rate limits)
            
            # Only update if still in confirmation state
            if self.analysis_data.state == EngineState.AWAITING_CONFIRMATION:
                self.analysis_data.countdown_seconds -= 8
                self._save_analysis_data()
                logger.debug(f"Updated countdown to {self.analysis_data.countdown_seconds} seconds")
        
        # Auto-confirm if countdown reached zero and still awaiting confirmation
        if (self.analysis_data.state == EngineState.AWAITING_CONFIRMATION and 
            self.analysis_data.countdown_seconds <= 0):
            logger.info("Countdown reached zero - auto-confirming")
            await self._auto_confirm()
        else:
            logger.info(f"Countdown loop ended - state: {self.analysis_data.state.value}, countdown: {self.analysis_data.countdown_seconds}")

    async def _auto_confirm(self):
        """Auto-confirm the proposed parameters after timeout."""
        logger.info("Auto-confirming proposed parameters after 90-second timeout")
        
        if self.telegram_bot:
            await utils.send_telegram_message(
                self.telegram_bot,
                "⏰ <b>AUTO-CONFIRMED</b>\n\nNo response received within 90 seconds.\nStarting trading with proposed parameters..."
            )
        
        await self._execute_confirmation(True, auto_confirmed=True)

    async def handle_confirmation_response(self, response: str) -> Dict[str, Any]:
        """Handle admin confirmation response."""
        if self.analysis_data.state != EngineState.AWAITING_CONFIRMATION:
            return {"executed": False, "message": "No confirmation pending"}
        
        response = response.lower().strip()
        
        if response == "yes":
            await self._execute_confirmation(True, auto_confirmed=False)
            return {"executed": True, "message": "Parameters confirmed and applied"}
        elif response == "no":
            await self._execute_confirmation(False, auto_confirmed=False)
            return {"executed": False, "message": "Parameters rejected, bot remains paused"}
        
        return {"executed": False, "message": "Invalid response. Please reply 'yes' or 'no'"}

    async def _execute_confirmation(self, confirmed: bool, auto_confirmed: bool = False):
        """Execute the confirmation decision."""
        logger.info(f"Executing confirmation: confirmed={confirmed}, auto_confirmed={auto_confirmed}")
        
        # Stop thought process display
        if self.thought_process_task:
            self.thought_process_task.cancel()
            logger.debug("Cancelled thought process task")
            
        # For recovery mode, preserve the final results instead of deleting
        if self.thought_message_id and self.telegram_bot:
            if self.analysis_data.current_mode == TradingMode.RECOVERY and confirmed:
                # Convert thought process to final recovery results (don't delete)
                try:
                    final_results = self._build_recovery_final_results()
                    await self.telegram_bot.edit_message_text(
                        chat_id=config.GROUP_ID,
                        message_id=self.thought_message_id,
                        text=final_results,
                        parse_mode='HTML'
                    )
                    # Store message ID to preserve it
                    self.analysis_data.final_recovery_message_id = self.thought_message_id
                    logger.info(f"Preserved recovery results in message {self.thought_message_id}")
                except Exception as e:
                    logger.error(f"Could not preserve recovery results: {e}")
            else:
                # For continuous mode or rejected recovery, delete as normal
                try:
                    await self.telegram_bot.delete_message(
                        chat_id=config.GROUP_ID,
                        message_id=self.thought_message_id
                    )
                    logger.info(f"Deleted thought process message {self.thought_message_id}")
                except Exception as e:
                    logger.debug(f"Could not delete thought message: {e}")
            self.thought_message_id = None
        
        if confirmed:
            logger.info(f"Parameters confirmed {'automatically' if auto_confirmed else 'by admin'}")
            self.analysis_data.state = EngineState.INACTIVE
            self.analysis_data.params_confirmed = True  # Mark parameters as confirmed
            
            # Switch to recovery mode if recovery parameters were confirmed
            if self.analysis_data.proposed_params and self.analysis_data.proposed_params.trading_mode == TradingMode.RECOVERY:
                logger.info("Switching to recovery mode after parameter confirmation")
                self.analysis_data.current_mode = TradingMode.RECOVERY
                
                # CRITICAL FIX: Reset cumulative loss when starting recovery mode
                if self.trading_state:
                    logger.info(f"Resetting cumulative loss for recovery mode (was: {self.trading_state.cumulative_loss:.2f})")
                    self.trading_state.cumulative_loss = 0.0
                    self.trading_state.save_stats()
                    logger.info("✅ Cumulative loss reset to 0 for recovery mode - fresh start!")
                
                self._save_analysis_data()
            
            if self.telegram_bot:
                params = self.analysis_data.proposed_params
                vol_data = self.analysis_data.volatility_data
                
                if params.trading_mode == TradingMode.RECOVERY:
                    # Recovery mode confirmation
                    forecast = params.recovery_forecast
                    confirmation_msg = (
                        f"🚨 <b>RECOVERY MODE CONFIRMED</b> {'(AUTO)' if auto_confirmed else ''}\n\n"
                        f"🔄 <b>CUMULATIVE LOSS RESET TO 0</b> - Fresh recovery start!\n\n"
                        f"🏆 <b>Recovery Strategy Activated:</b>\n"
                        f"└ Index: <code>{vol_data.symbol if vol_data else 'Unknown'}</code> (Optimal for recovery)\n"
                        f"└ Stake: <code>{params.stake:.2f} XRP</code> (HIGH RISK)\n"
                        f"└ Take-Profit: <code>{params.take_profit:.0f}%</code>\n"
                        f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                        f"└ Frequency: <code>{params.frequency.upper()}</code>\n\n"
                    )
                    
                    if forecast:
                        confirmation_msg += (
                            f"📊 <b>Recovery Forecast:</b>\n"
                            f"└ Target Loss Recovery: <code>{forecast.loss_to_recover:.2f} XRP</code>\n"
                            f"└ Estimated Trades: <code>{forecast.estimated_trades_min}-{forecast.estimated_trades_max}</code>\n"
                            f"└ Success Probability: <code>{forecast.recovery_probability*100:.1f}%</code>\n"
                            f"└ Estimated Time: <code>{forecast.time_estimate_minutes//60}h {forecast.time_estimate_minutes%60}m</code>\n\n"
                        )
                    
                    confirmation_msg += (
                        f"🔄 <b>Recovery trading initiated - Loss tracking starts fresh!</b>\n"
                        f"🚨 <b>High-risk recovery mode active...</b>\n\n"
                        f"✅ <b>New parameters applied! First recovery trade starting...</b>"
                    )
                else:
                    # Continuous mode confirmation
                    confirmation_msg = (
                        f"✅ <b>PARAMETERS CONFIRMED</b> {'(AUTO)' if auto_confirmed else ''}\n\n"
                        f"🎯 Trading with optimized continuous settings:\n"
                        f"└ Index: <code>{vol_data.symbol if vol_data else 'Unknown'}</code> (Best performing)\n"
                        f"└ Stake: <code>{params.stake:.2f} XRP</code>\n"
                        f"└ Take-Profit: <code>{params.take_profit:.0f}%</code>\n"
                        f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                        f"└ Frequency: <code>{params.frequency.upper()}</code>\n\n"
                        f"🔄 <b>Optimized parameters applied - Trading resumed!</b>\n"
                        f"🚀 <b>Bot is resuming trading automatically...</b>"
                    )
                
                await utils.send_telegram_message(self.telegram_bot, confirmation_msg)
        else:
            logger.info("Parameters rejected by admin")
            self.analysis_data.state = EngineState.INACTIVE
            self.analysis_data.params_confirmed = False  # Clear confirmation flag
            
            if self.telegram_bot:
                await utils.send_telegram_message(
                    self.telegram_bot,
                    f"❌ <b>PARAMETERS REJECTED</b>\n\n"
                    f"Bot will remain paused until manually restarted.\n"
                    f"Use trading commands to restart with new parameters."
                )
        
        self._save_analysis_data()
        logger.info(f"Confirmation execution complete - engine state: {self.analysis_data.state.value}")
        
        # If parameters were confirmed, signal that trading should resume
        if confirmed:
            self.resume_trading_signal = True
            
            # Trigger trading resumption for BOTH manual and auto confirmation
            if self.trading_state:
                logger.info("Parameters confirmed - triggering trading resumption")
                asyncio.create_task(self._trigger_trading_resumption())
            else:
                logger.error("No trading state reference available for resumption")

    async def _trigger_trading_resumption(self):
        """Trigger trading resumption after auto-confirmation."""
        try:
            # Small delay to ensure confirmation messages are sent
            await asyncio.sleep(1)
            
            # Check if trading state is available and trading is enabled
            if not self.trading_state:
                logger.error("No trading state reference available for resumption")
                return
                
            # Send resumption message
            if self.telegram_bot:
                await utils.send_telegram_message(
                    self.telegram_bot,
                    "🚀 <b>TRADING RESUMPTION</b>\n\n"
                    "✅ Recovery parameters confirmed and applied!\n"
                    "🎯 Starting first recovery trade with new parameters...\n"
                    "📊 Bot will now trade with recovery mode settings"
                )
            
            # Trigger a new trade
            logger.info("Triggering new trade after auto-confirmation")
            await self.trading_state.start_new_trade()
            
        except Exception as e:
            logger.error(f"Error triggering trading resumption: {e}")
            if self.telegram_bot:
                await utils.send_telegram_message(
                    self.telegram_bot,
                    f"❌ Error resuming trading after auto-confirmation: {str(e)}"
                )

    def get_proposed_parameters(self) -> Optional[Dict[str, Any]]:
        """Get the proposed parameters if confirmed and available."""
        if (self.analysis_data.state == EngineState.INACTIVE and 
            self.analysis_data.proposed_params and
            self.analysis_data.params_confirmed):  # Only return if confirmed
            params = self.analysis_data.proposed_params
            vol_data = self.analysis_data.volatility_data
            
            logger.info(f"Retrieving confirmed parameters - Trading mode: {params.trading_mode.value}")
            
            # Return the parameters including the best index and mode
            result = {
                "index": vol_data.symbol if vol_data else "R_10",  # Include the selected index
                "stake": params.stake,
                "growth_rate": params.growth_rate,
                "take_profit": params.take_profit,
                "frequency": params.frequency,
                "trading_mode": params.trading_mode.value,
                "recovery_mode": params.trading_mode == TradingMode.RECOVERY,  # Backward compatibility
                "is_recovery": params.trading_mode == TradingMode.RECOVERY,  # Clear flag for notifications
            }
            
            # Add recovery forecast if available (for notifications)
            if params.recovery_forecast:
                result["recovery_forecast"] = {
                    "loss_to_recover": params.recovery_forecast.loss_to_recover,
                    "estimated_trades": f"{params.recovery_forecast.estimated_trades_min}-{params.recovery_forecast.estimated_trades_max}",
                    "recovery_probability": f"{params.recovery_forecast.recovery_probability*100:.1f}%",
                    "time_estimate": f"{params.recovery_forecast.time_estimate_minutes//60}h {params.recovery_forecast.time_estimate_minutes%60}m",
                    "risk_assessment": params.recovery_forecast.risk_assessment
                }
            
            # Clear the proposed parameters and confirmation flag after retrieval to prevent reuse
            self.analysis_data.proposed_params = None
            self.analysis_data.params_confirmed = False
            self.resume_trading_signal = False  # Clear the resume signal
            self._save_analysis_data()
            logger.info(f"✅ Confirmed parameters retrieved and cleared: {result}")
            
            return result
        return None

    def is_active(self) -> bool:
        """Check if the engine is currently active."""
        return self.analysis_data.state != EngineState.INACTIVE

    def reset_engine(self):
        """Reset the engine to inactive state."""
        if self.thought_process_task:
            self.thought_process_task.cancel()
            
        self.analysis_data = AnalysisData(
            state=EngineState.INACTIVE,
            analysis_start_time=None,
            current_step="",
            thought_process="",
            volatility_data=None,
            proposed_params=None,
            confirmation_deadline=None,
            countdown_seconds=0,
            auto_confirm=True,
            params_confirmed=False,
            current_mode=TradingMode.CONTINUOUS,
            daily_profit_target=0.0,
            session_start_balance=0.0,
            final_recovery_message_id=None,
            recovery_failures=0,
            recovery_risk_reduction=1.0
        )
        self._save_analysis_data()
        self.thought_message_id = None

    def get_status_json(self) -> str:
        """Generate JSON status for monitoring."""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "state": self.analysis_data.state.value,
                "current_step": self.analysis_data.current_step,
                "countdown_seconds": self.analysis_data.countdown_seconds,
                "volatility_data": self.analysis_data.volatility_data.to_dict() if self.analysis_data.volatility_data else None,
                "proposed_params": self.analysis_data.proposed_params.to_dict() if self.analysis_data.proposed_params else None
            }
            
            return json.dumps(status, indent=2)
            
        except Exception as e:
            logger.error(f"Error generating status JSON: {e}")
            return json.dumps({"error": str(e), "timestamp": datetime.now().isoformat()})

    async def _fetch_tick_data(self, symbol: str, periods: int = 300) -> List[Dict]:
        """Fetch historical tick data for volatility analysis."""
        try:
            if not await self.api.connect():
                logger.error(f"Failed to connect to API for tick data: {symbol}")
                return []
            
            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": periods,
                "end": "latest",
                "style": "ticks"
            }
            
            await self.api._send_request(request)
            response = await self.api._receive_message(timeout=30)
            
            if "error" in response:
                logger.error(f"API error fetching tick data for {symbol}: {response['error']}")
                return []
            
            if response.get("msg_type") == "history":
                ticks = response.get("history", {}).get("prices", [])
                times = response.get("history", {}).get("times", [])
                
                return [{"time": t, "price": float(p)} for t, p in zip(times, ticks)]
            
            logger.warning(f"Unexpected response format for tick data: {symbol}")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching tick data for {symbol}: {e}")
            return []

    def _build_recovery_final_results(self) -> str:
        """Build the final recovery results display that will be preserved."""
        current_time = datetime.now().strftime("%I:%M %p")
        params = self.analysis_data.proposed_params
        vol_data = self.analysis_data.volatility_data
        forecast = params.recovery_forecast if params else None
        
        display = (
            f"🚨 <b>[RECOVERY MODE RESULTS - Final {current_time}]</b>\n"
            f"{'='*50}\n\n"
            f"✅ <b>RECOVERY STRATEGY CONFIRMED & ACTIVE</b>\n\n"
            f"🏆 <b>Selected Recovery Index:</b> <code>{vol_data.symbol if vol_data else 'Unknown'}</code>\n"
            f"📊 <b>Volatility:</b> <code>{vol_data.volatility_percentage:.1f}%</code>\n\n"
        )
        
        if forecast:
            display += (
                f"📊 <b>RECOVERY FORECAST:</b>\n"
                f"└ Loss to Recover: <code>{forecast.loss_to_recover:.2f} XRP</code>\n"
                f"└ Estimated Trades: <code>{forecast.estimated_trades_min}-{forecast.estimated_trades_max}</code>\n"
                f"└ Recovery Probability: <code>{forecast.recovery_probability*100:.1f}%</code>\n"
                f"└ Required Win Rate: <code>{forecast.required_win_rate*100:.1f}%</code>\n"
                f"└ Time Estimate: <code>{forecast.time_estimate_minutes//60}h {forecast.time_estimate_minutes%60}m</code>\n"
                f"└ Risk Assessment: <code>{forecast.risk_assessment}</code>\n\n"
            )
        
        if params:
            display += (
                f"🎲 <b>ACTIVE RECOVERY PARAMETERS:</b>\n"
                f"└ Stake: <code>{params.stake:.2f} XRP</code> ({params.account_percentage:.1f}% - HIGH RISK)\n"
                f"└ Take Profit: <code>{params.take_profit:.0f}%</code>\n"
                f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                f"└ Frequency: <code>{params.frequency.upper()}</code>\n"
                f"└ Mode: <code>RECOVERY</code> 🚨\n\n"
            )
        
        display += (
            f"🔄 <b>STATUS:</b> Recovery mode trading initiated\n"
            f"💡 <b>NOTE:</b> This display will remain visible for reference\n"
            f"📈 <b>Monitor progress in trade updates</b>"
        )
        
        return display

    def get_current_mode(self) -> TradingMode:
        """Get the current trading mode."""
        return self.analysis_data.current_mode

    def switch_to_continuous_mode(self, message: str = "Recovery completed successfully"):
        """Switch back to continuous mode after recovery completion."""
        self.analysis_data.current_mode = TradingMode.CONTINUOUS
        self.analysis_data.daily_profit_target = 0.0  # Reset profit target
        self.analysis_data.session_start_balance = 0.0  # Will be set next session
        self._save_analysis_data()
        logger.info(f"Switched to continuous mode: {message}")

    def apply_continuous_mode_adjustments(self, current_params: Dict, reduction_factor: float = None) -> Dict:
        """Apply risk reduction adjustments for continuous mode."""
        if reduction_factor is None:
            reduction_factor = config.CONTINUOUS_RISK_REDUCTION
        
        adjusted_params = current_params.copy()
        
        # Reduce stake by the reduction factor
        if "stake" in adjusted_params:
            adjusted_params["stake"] *= reduction_factor
            adjusted_params["stake"] = max(0.5, adjusted_params["stake"])  # Minimum stake
        
        # Adjust take profit (make it more conservative)
        if "take_profit" in adjusted_params:
            adjusted_params["take_profit"] *= 0.9  # Reduce by 10%
            adjusted_params["take_profit"] = max(15.0, adjusted_params["take_profit"])  # Minimum 15%
        
        logger.info(f"Applied continuous mode risk reduction: {reduction_factor}")
        return adjusted_params

    async def handle_recovery_failure(self):
        """Handle a recovery mode trade failure by reducing risk and changing to a safer index."""
        logger.info(f"=== RECOVERY FAILURE HANDLER CALLED ===")
        logger.info(f"Current mode: {self.analysis_data.current_mode.value}")
        logger.info(f"Engine state: {self.analysis_data.state.value}")
        
        if self.analysis_data.current_mode != TradingMode.RECOVERY:
            logger.warning(f"Recovery failure handler called but not in recovery mode (current: {self.analysis_data.current_mode.value})")
            return
        
        logger.info("Confirmed in recovery mode - processing failure")
        
        # Get current index before incrementing failures
        current_index = self.analysis_data.volatility_data.symbol if self.analysis_data.volatility_data else None
        
        # Increment failure count
        self.analysis_data.recovery_failures += 1
        
        # Calculate progressive risk reduction (reduce by 15% each failure)
        reduction_factor = 0.85 ** self.analysis_data.recovery_failures
        self.analysis_data.recovery_risk_reduction = reduction_factor
        
        # Cap minimum risk reduction to 30% of original (don't go below 0.3)
        self.analysis_data.recovery_risk_reduction = max(0.3, self.analysis_data.recovery_risk_reduction)
        
        # Change to a safer index on each failure using dict.py volatility data
        new_index = self._select_safer_index_for_recovery(current_index, self.analysis_data.recovery_failures)
        
        if new_index and new_index != current_index:
            logger.info(f"Recovery failure #{self.analysis_data.recovery_failures}: Switching from {current_index} to safer index {new_index}")
            
            # Update volatility data to the new safer index
            index_data = get_index(new_index)
            if index_data:
                self.analysis_data.volatility_data = VolatilityMetrics(
                    symbol=new_index,
                    volatility_percentage=index_data['volatility_pct'],
                    price_swings=[],
                    volatility_score=100 - index_data['volatility_pct'],  # Lower volatility = higher score
                    data_points=300,  # Default data points
                    timestamp=datetime.now()
                )
                logger.info(f"Updated volatility data for safer index {new_index} (volatility: {index_data['volatility_pct']}%)")
        
        self._save_analysis_data()
        
        logger.info(f"Recovery failure #{self.analysis_data.recovery_failures} processed - risk reduced to {self.analysis_data.recovery_risk_reduction:.2f}, index: {new_index or current_index}")
        
        if self.telegram_bot:
            index_change_msg = f"\n🔄 Index Changed: <code>{current_index}</code> → <code>{new_index}</code> (safer option)" if new_index != current_index else ""
            
            await utils.send_telegram_message(
                self.telegram_bot,
                f"🚨 <b>RECOVERY FAILURE #{self.analysis_data.recovery_failures}</b>\n\n"
                f"❌ Recovery trade failed - adjusting strategy\n"
                f"📉 Risk Reduction Applied: <code>{(1-self.analysis_data.recovery_risk_reduction)*100:.1f}%</code>\n"
                f"🎯 Next Stake Reduced: <code>{self.analysis_data.recovery_risk_reduction*100:.1f}%</code> of original{index_change_msg}\n"
                f"🔄 Continuing recovery with safer parameters..."
            )
        
        logger.info(f"Recovery failure #{self.analysis_data.recovery_failures} - risk reduced to {self.analysis_data.recovery_risk_reduction:.2f}")

    def _get_excluded_indices_for_recovery(self) -> List[str]:
        """Get list of indices to exclude from recovery mode."""
        excluded = []
        
        # Always exclude the original losing pair if we have trade history
        if self.last_trade_history:
            losing_pairs = set()
            
            # Get the last few losing trades to identify problematic indices
            recent_trades = self.last_trade_history[-5:]  # Last 5 trades
            for trade in recent_trades:
                if not trade.get('win', False):  # If it was a loss
                    losing_pairs.add(trade.get('symbol'))
            
            excluded.extend(losing_pairs)
            logger.info(f"Excluding losing pairs from recovery: {list(losing_pairs)}")
        
        # Also exclude any indices that have failed multiple times in recovery
        if hasattr(self.analysis_data, 'failed_recovery_indices'):
            excluded.extend(self.analysis_data.failed_recovery_indices)
        
        # Remove duplicates
        excluded = list(set(excluded))
        
        logger.info(f"Total excluded indices for recovery: {excluded}")
        return excluded

    def _select_safer_index_for_recovery(self, current_index: str, failure_count: int) -> str:
        """Select a safer index for recovery based on failure count and volatility data from dict.py."""
        try:
            # Get all indices sorted by volatility (lowest first)
            available_indices = []
            excluded_indices = self._get_excluded_indices_for_recovery()
            
            for symbol, data in ACCUMULATOR_INDICES.items():
                if symbol not in excluded_indices:
                    available_indices.append({
                        'symbol': symbol,
                        'volatility': data['volatility_pct'],
                        'risk_level': data['risk_level'],
                        'recommended_growth': data['recommended_growth_pct']
                    })
            
            # Sort by volatility (lowest first for recovery)
            available_indices.sort(key=lambda x: x['volatility'])
            
            if not available_indices:
                logger.warning("No safe indices available for recovery - using fallback")
                return "R_10"  # Fallback to safest option
            
            # Select index based on failure count (progressively safer)
            if failure_count <= 2:
                # First 2 failures: Use low volatility (10-25%)
                safe_indices = [idx for idx in available_indices if idx['volatility'] <= 25]
            elif failure_count <= 4:
                # Failures 3-4: Use very low volatility (10% only)
                safe_indices = [idx for idx in available_indices if idx['volatility'] <= 10]
            else:
                # 5+ failures: Use only the safest possible
                safe_indices = [idx for idx in available_indices if idx['volatility'] == 10]
            
            if not safe_indices:
                safe_indices = available_indices  # Fallback to any available
            
            # Don't use the current index if possible
            if current_index:
                different_indices = [idx for idx in safe_indices if idx['symbol'] != current_index]
                if different_indices:
                    safe_indices = different_indices
            
            # Select the safest option
            selected = safe_indices[0]['symbol']
            selected_data = safe_indices[0]
            
            logger.info(f"Selected safer index for recovery failure #{failure_count}: {selected} "
                       f"(volatility: {selected_data['volatility']}%, risk: {selected_data['risk_level']})")
            
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting safer index: {e}")
            return current_index or "R_10"  # Fallback

    async def handle_recovery_success(self):
        """Handle successful recovery completion."""
        if self.analysis_data.current_mode != TradingMode.RECOVERY:
            return
        
        failures = self.analysis_data.recovery_failures
        total_reduction = (1 - self.analysis_data.recovery_risk_reduction) * 100
        
        # Reset recovery tracking
        self.analysis_data.recovery_failures = 0
        self.analysis_data.recovery_risk_reduction = 1.0
        
        # Switch back to continuous mode
        self.switch_to_continuous_mode("Recovery completed successfully")
        
        if self.telegram_bot:
            success_msg = (
                f"🎉 <b>RECOVERY COMPLETED SUCCESSFULLY!</b>\n\n"
                f"✅ Net P/L restored to positive\n"
                f"📊 Recovery Stats:\n"
                f"└ Failed Attempts: <code>{failures}</code>\n"
                f"└ Final Risk Reduction: <code>{total_reduction:.1f}%</code>\n"
                f"└ Recovery Strategy: <code>Adaptive Risk Management</code>\n\n"
                f"🎯 <b>Switching to CONTINUOUS MODE</b>\n"
                f"🛡️ Risk will be managed for profit preservation\n"
                f"📈 Ready for sustainable trading!"
            )
            
            await utils.send_telegram_message(self.telegram_bot, success_msg)
        
        logger.info(f"Recovery completed after {failures} failures with {total_reduction:.1f}% total risk reduction")

    def apply_recovery_risk_reduction(self, params: Dict) -> Dict:
        """Apply current recovery risk reduction to parameters."""
        if not params:
            logger.error("Cannot apply risk reduction to None/empty parameters")
            return params or {}
            
        if self.analysis_data.current_mode != TradingMode.RECOVERY or self.analysis_data.recovery_risk_reduction >= 1.0:
            logger.debug("No risk reduction needed - not in recovery mode or no failures")
            return params
        
        try:
            adjusted_params = params.copy()
            
            # Apply risk reduction to stake
            if "stake" in adjusted_params and adjusted_params["stake"]:
                original_stake = float(adjusted_params["stake"])
                adjusted_params["stake"] = original_stake * self.analysis_data.recovery_risk_reduction
                adjusted_params["stake"] = max(0.5, adjusted_params["stake"])  # Minimum stake
                logger.info(f"Applied recovery risk reduction: {original_stake:.2f} → {adjusted_params['stake']:.2f}")
            else:
                logger.warning("No stake found in parameters for risk reduction")
            
            return adjusted_params
            
        except Exception as e:
            logger.error(f"Error in apply_recovery_risk_reduction: {e}")
            return params

    def _get_excluded_indices_for_recovery(self) -> List[str]:
        """Get list of indices to exclude from recovery mode."""
        excluded = []
        
        # Always exclude the original losing pair if we have trade history
        if self.last_trade_history:
            losing_pairs = set()
            
            # Get the last few losing trades to identify problematic indices
            recent_trades = self.last_trade_history[-5:]  # Last 5 trades
            for trade in recent_trades:
                if not trade.get('win', False):  # If it was a loss
                    losing_pairs.add(trade.get('symbol'))
            
            excluded.extend(losing_pairs)
            logger.info(f"Excluding losing pairs from recovery: {list(losing_pairs)}")
        
        # Also exclude any indices that have failed multiple times in recovery
        if hasattr(self.analysis_data, 'failed_recovery_indices'):
            excluded.extend(self.analysis_data.failed_recovery_indices)
        
        # Remove duplicates
        excluded = list(set(excluded))
        
        logger.info(f"Total excluded indices for recovery: {excluded}")
        return excluded


# Backward compatibility - alias for existing code
AccumulatorDecisionEngine = RefinedDecisionEngine 