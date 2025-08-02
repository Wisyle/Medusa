import asyncio
import traceback
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional
import time

from telegram import Bot

# Import the refactored modules
import config
import utils
from deriv_api import DerivAPI, Trade
from decision_engine import DecisionEngine
from decision_engine import TradingMode, EngineState

# Initialize the logger from the utils module
logger = utils.setup_logging()


class TradingState:
    """Manages the high-level state and logic of the trading bot."""
    def __init__(self, api: DerivAPI, bot: Optional[Bot] = None, reset_stats=False):
        self.api = api
        self.bot = bot  # Store bot instance
        self.active_trades: Dict[str, Trade] = {}
        self.trade_history: List[Dict] = []
        
        # --- Cumulative Stats ---
        self.cumulative_loss: float = 0.0
        self.cumulative_win: float = 0.0
        self.initial_balance: float = 0.0
        
        # --- User-defined Parameters & Limits ---
        self.params: Dict = {}
        self.saved_params: Dict = {}
        self.max_loss_amount: float = 0.0
        self.max_win_amount: float = 0.0
        
        # --- Bot Operational State ---
        self.trading_enabled: bool = False
        self.is_stopping: bool = False
        self.awaiting_input: Optional[str] = None
        self.telegram_messages: Deque = deque(maxlen=100)
        self._start_time = datetime.now()
        
        # --- Trading Mode State ---
        self.consecutive_wins: int = 0
        self.session_start_balance: float = 0.0
        self.daily_profit_tracking: bool = False
        
        # Load persistent data
        self.stats = self.load_stats(reset_stats)
        self.load_saved_params()
        self.progress_message_id = None  # Store the pinned message ID
        self.last_outcome_message_id = None  # Track last trade outcome notification
        self.last_pin_notification_id = None  # Track last pin notification
        self.status_messages = [
            "Decter 001 analyzing market patterns... 🤔",
            "Decter 001 calculating optimal entry points... 📊",
            "Decter 001 monitoring price movements... 👀",
            "Decter 001 processing market data... 💻",
            "Decter 001 checking market conditions... 🔍",
            "Decter 001 evaluating trade opportunities... 📈",
            "Decter 001 scanning for profitable setups... 🎯",
            "Decter 001 running technical analysis... 📉",
            "Decter 001 optimizing trade parameters... ⚡",
            "Decter 001 synchronizing with market... 🔄",
            "Decter 001 calibrating trading algorithms... 🤖",
            "Decter 001 validating market signals... ✅",
            "Decter 001 executing precision trades... 🎮",
            "Decter 001 maintaining market presence... 🏢",
            "Decter 001 monitoring trade performance... 📊"
        ]
        self.sarcastic_comments = [
            "Making money while you sleep 😴",
            "Your personal money printer 🖨️",
            "Trading like a boss 💪",
            "Making it rain profits 🌧️",
            "Living the trading dream 🌟",
            "Printing money like it's 2020 💸",
            "Your friendly neighborhood trader 🦸‍♂️",
            "Making trading look easy 😎",
            "Your personal trading assistant 🤖",
            "Trading with style and grace 🎭",
            "Making profits look effortless ✨",
            "Your 24/7 money-making machine ⚡",
            "Trading while you're away 🏖️",
            "Making trading fun again 🎮",
            "Your automated profit generator 🚀"
        ]
        self.current_status_index = 0
        self.current_comment_index = 0
        
        # Initialize Refined Decision Engine
        self.decision_engine = DecisionEngine(config.DATA_DIR)
        
        logger.info("Trading state initialized.")

    def load_stats(self, reset: bool = False) -> Dict:
        """Loads trading statistics from a file, or resets them."""
        default_stats = {
            "total_trades": 0, "wins": 0, "losses": 0,
            "net_pl": 0.0, "growth": 0.0,
            "cumulative_win": 0.0, "cumulative_loss": 0.0
        }
        
        if reset or not config.TRADING_STATS_FILE.exists():
            logger.info("Resetting trading stats or file not found. Initializing new stats file.")
            utils.save_json_file(config.TRADING_STATS_FILE, {
                "starting_balance": 0.0,
                "cumulative_loss": 0.0,
                "cumulative_win": 0.0,
                "stats": default_stats,
                "trade_history": []
            })

        all_data = utils.load_json_file(config.TRADING_STATS_FILE)
        self.initial_balance = all_data.get("starting_balance", 0.0)
        self.cumulative_loss = all_data.get("cumulative_loss", 0.0)
        self.cumulative_win = all_data.get("cumulative_win", 0.0)
        self.trade_history = all_data.get("trade_history", [])
        
        # Ensure all keys exist in the loaded stats
        loaded_stats = all_data.get("stats", default_stats)
        for key, value in default_stats.items():
            if key not in loaded_stats:
                loaded_stats[key] = value

        logger.info(f"Stats loaded successfully: {loaded_stats}")
        return loaded_stats

    def save_stats(self):
        """Saves the current state and stats to a file."""
        data_to_save = {
            "starting_balance": self.initial_balance,
            "cumulative_loss": self.cumulative_loss,
            "cumulative_win": self.cumulative_win,
            "stats": self.stats,
            "trade_history": self.trade_history
        }
        utils.save_json_file(config.TRADING_STATS_FILE, data_to_save)
        logger.info(f"Stats saved. Current Net P/L: {self.stats.get('net_pl', 0.0):.2f}")

    def load_saved_params(self):
        """Loads saved trading parameters from a file."""
        params = utils.load_json_file(config.SAVED_PARAMS_FILE)
        if params and all(params.values()):  # Check if all required parameters are present
            self.saved_params = params
            self.params = params.copy()  # Use a copy for active trading
            self.max_loss_amount = params.get("max_loss_amount", 0.0)
            self.max_win_amount = params.get("max_win_amount", 0.0)
            logger.info(f"Saved parameters loaded: {self.saved_params}")
            return True
        logger.info("No valid saved parameters found.")
        return False

    def save_params(self):
        """Saves the current trading parameters to a file."""
        current_params = {
            "stake": self.params.get("stake"),
            "growth_rate": self.params.get("growth_rate"),
            "take_profit": self.params.get("take_profit"),
            "index": self.params.get("index"),
            "currency": self.params.get("currency"),
            "max_loss_amount": self.max_loss_amount,
            "max_win_amount": self.max_win_amount
        }
        # Ensure all required parameters are present
        if all(current_params.values()):
            utils.save_json_file(config.SAVED_PARAMS_FILE, current_params)
            self.saved_params = current_params
            logger.info(f"Parameters saved: {current_params}")
        else:
            logger.warning("Not all parameters are set, skipping save")

    async def update_stats_after_trade(self, trade: Trade):
        """Updates cumulative statistics after a trade is closed."""
        pnl = trade.profit_loss
        is_win = pnl > 0
        self.stats["total_trades"] += 1
        
        if is_win:
            self.stats["wins"] += 1
            self.cumulative_win += pnl
            self.stats["cumulative_win"] += pnl
            # Track consecutive wins for continuous mode
            self.consecutive_wins += 1
        else:
            self.stats["losses"] += 1
            # Loss is always a positive value in this context
            self.cumulative_loss += abs(pnl)
            self.stats["cumulative_loss"] += abs(pnl)
            # Reset consecutive wins on loss
            self.consecutive_wins = 0
            
        self.stats["net_pl"] = self.stats["cumulative_win"] - self.stats["cumulative_loss"]
        
        if self.initial_balance > 0:
            self.stats["growth"] = (self.stats["net_pl"] / self.initial_balance) * 100
        
        # Check for recovery mode completion or failure - ONLY if actually in recovery mode
        current_mode = self.decision_engine.get_current_mode().value
        logger.info(f"Current trading mode after trade: {current_mode}, trade result: {'win' if is_win else 'loss'}")
        
        if current_mode == "recovery":
            # Double-check that we're truly in recovery mode and not just loading stale state
            actual_mode = self.decision_engine.get_current_mode().value
            logger.info(f"Mode check - reported: {current_mode}, actual from engine: {actual_mode}")
            
            # CRITICAL FIX: Only handle recovery logic if truly in recovery mode AND parameters were confirmed
            if (actual_mode == "recovery" and 
                self.decision_engine.analysis_data.state == EngineState.INACTIVE and
                self.cumulative_loss >= self.max_loss_amount):
                logger.info("Confirmed in recovery mode - checking trade outcome for recovery logic")
                if is_win:
                    logger.info("Recovery trade won - checking if recovery is complete")
                    await self._check_recovery_completion(pnl)
                else:
                    logger.info("Recovery trade lost - applying recovery failure handling")
                    await self._handle_recovery_failure()
            else:
                logger.warning(f"RECOVERY MODE MISMATCH - reported as recovery but not truly in recovery mode!")
                logger.warning(f"Engine state: {self.decision_engine.analysis_data.state.value if self.decision_engine else 'N/A'}")
                logger.warning(f"Cumulative loss: {self.cumulative_loss:.2f}, Max loss: {self.max_loss_amount:.2f}")
                logger.warning("Skipping recovery-specific logic - likely stale state")
                
                # If we're incorrectly in recovery mode, switch back to continuous
                if actual_mode == "recovery" and self.cumulative_loss < self.max_loss_amount:
                    logger.info("Correcting mode mismatch - switching back to continuous mode")
                    self.decision_engine.switch_to_continuous_mode("Correcting stale recovery mode state")
        else:
            logger.info(f"Not in recovery mode ({current_mode}) - skipping recovery-specific logic")
        
        # Check continuous mode conditions if in continuous mode
        logger.debug(f"Checking if should apply continuous mode conditions - current mode: {current_mode}")
        if current_mode == "continuous":
            logger.debug(f"In continuous mode - checking conditions with consecutive wins: {self.consecutive_wins}")
            await self._check_continuous_mode_conditions()
        else:
            logger.debug(f"Not in continuous mode ({current_mode}), skipping continuous mode checks")
        
        # Add to historical records with enhanced information
        current_mode = self.decision_engine.get_current_mode().value
        record = {
            "timestamp": trade.close_time.strftime("%Y-%m-%d %H:%M:%S") if trade.close_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "balance": trade.post_trade_balance,
            "profit_loss": pnl,
            "win": is_win,
            "symbol": trade.symbol,
            "stake": trade.stake,
            "contract_id": trade.contract_id,
            "trading_mode": current_mode,  # Add current trading mode
            "consecutive_wins": self.consecutive_wins,  # Track consecutive wins at trade time
            "take_profit": getattr(trade, 'take_profit', 0),  # Add take profit percentage
            "growth_rate": getattr(trade, 'growth_rate', 0) * 100,  # Add growth rate as percentage
            "currency": getattr(trade, 'currency', 'XRP'),  # Add currency
            "cumulative_pl": self.stats["net_pl"],  # Add cumulative P/L at this point
            "growth_percentage": self.stats["growth"],  # Add growth percentage at this point
        }
        
        # Add recovery-specific information if in recovery mode
        if current_mode == "recovery":
            record["recovery_failures"] = self.decision_engine.analysis_data.recovery_failures
            record["recovery_risk_reduction"] = self.decision_engine.analysis_data.recovery_risk_reduction
            
            # Add recovery forecast data if available
            if (self.decision_engine.analysis_data.proposed_params and 
                self.decision_engine.analysis_data.proposed_params.recovery_forecast):
                forecast = self.decision_engine.analysis_data.proposed_params.recovery_forecast
                record["recovery_probability"] = forecast.recovery_probability
                record["recovery_risk_assessment"] = forecast.risk_assessment
        
        self.trade_history.append(record)
        
        self.save_stats()
        logger.info(f"Stats updated and saved after trade. Mode: {current_mode}, Consecutive wins: {self.consecutive_wins}")

    async def _check_recovery_completion(self, profit: float):
        """Check if recovery is complete after a successful trade."""
        if self.decision_engine.get_current_mode() != TradingMode.RECOVERY:
            return
        
        # Check if cumulative loss is back to break-even or positive
        # After cumulative loss reset, we track new recovery performance
        net_pl = self.stats.get("net_pl", 0.0)
        
        logger.info(f"Recovery completion check: cumulative_loss={self.cumulative_loss:.2f}, net_pl={net_pl:.2f}, profit={profit:.2f}")
        
        # Recovery is complete when cumulative loss is 0 or negative (profit) 
        # OR when net P/L is positive (depending on reset strategy)
        if self.cumulative_loss <= 0.0 or net_pl > 0.0:
            logger.info(f"✅ RECOVERY COMPLETED! Cumulative loss: {self.cumulative_loss:.2f}, Net P/L: {net_pl:.2f}")
            
            # Switch back to continuous mode
            await self.decision_engine.handle_recovery_success()
            
            # Send recovery completion notification
            if self.bot:
                recovery_msg = (
                    f"🎉 <b>RECOVERY COMPLETED SUCCESSFULLY!</b>\n\n"
                    f"✅ Loss recovery achieved with profitable trade\n"
                    f"📊 Recovery Stats:\n"
                    f"└ Final Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                    f"└ Current Net P/L: <code>{net_pl:+.2f} XRP</code>\n"
                    f"└ Winning Recovery Trade: <code>+{profit:.2f} XRP</code>\n\n"
                    f"🎯 <b>Switching to CONTINUOUS MODE</b>\n"
                    f"🛡️ Risk management will now focus on profit preservation\n"
                    f"📈 Ready for sustainable trading!"
                )
                await utils.send_telegram_message(self.bot, recovery_msg)
            
            # Reset consecutive wins for continuous mode
            self.consecutive_wins = 0
            self.save_stats()
            
        else:
            logger.info(f"Recovery still in progress - cumulative loss: {self.cumulative_loss:.2f}, net P/L: {net_pl:.2f}")

    async def _handle_recovery_failure(self):
        """Handle a failed recovery trade by reducing risk."""
        # CRITICAL FIX: Validate we're truly in recovery mode before handling failure
        if not self._is_truly_in_recovery_mode():
            logger.warning("_handle_recovery_failure called but not truly in recovery mode - ignoring")
            return
            
        # Use the decision engine's recovery failure handler
        await self.decision_engine.handle_recovery_failure()

    def _is_truly_in_recovery_mode(self) -> bool:
        """
        Validate that we are truly in recovery mode by checking multiple conditions.
        This prevents false recovery failure messages when the bot has stale state.
        """
        # Check decision engine mode
        current_mode = self.decision_engine.get_current_mode()
        engine_state = self.decision_engine.analysis_data.state
        
        # Check if max loss is actually reached
        max_loss_reached = self.max_loss_amount > 0 and self.cumulative_loss >= self.max_loss_amount
        
        # Log validation details
        logger.info(f"Recovery mode validation:")
        logger.info(f"  - Current mode: {current_mode.value}")
        logger.info(f"  - Engine state: {engine_state.value}")
        logger.info(f"  - Max loss reached: {max_loss_reached} (cumulative: {self.cumulative_loss:.2f}, limit: {self.max_loss_amount:.2f})")
        logger.info(f"  - Recovery failures: {self.decision_engine.analysis_data.recovery_failures}")
        
        # We're only truly in recovery mode if:
        # 1. Decision engine mode is RECOVERY
        # 2. Engine is not actively analyzing (state is INACTIVE)
        # 3. Max loss is actually reached
        truly_in_recovery = (
            current_mode == TradingMode.RECOVERY and
            engine_state == EngineState.INACTIVE and
            max_loss_reached
        )
        
        # If mode mismatch detected, fix it
        if current_mode == TradingMode.RECOVERY and not max_loss_reached:
            logger.warning(f"RECOVERY MODE MISMATCH DETECTED!")
            logger.warning(f"Engine shows recovery mode but max loss not reached")
            logger.warning(f"Cumulative loss: {self.cumulative_loss:.2f}, Max loss: {self.max_loss_amount:.2f}")
            logger.info("Switching back to continuous mode to fix mismatch")
            
            # Fix the mismatch by switching to continuous mode
            self.decision_engine.switch_to_continuous_mode("Fixing recovery mode mismatch - max loss not reached")
            
            # Reset recovery failures to clear stale state
            self.decision_engine.analysis_data.recovery_failures = 0
            self.decision_engine.analysis_data.recovery_risk_reduction = 1.0
            self.decision_engine._save_analysis_data()
            
            return False
        
        return truly_in_recovery

    async def _check_continuous_mode_conditions(self):
        """Check continuous mode conditions for risk reduction and auto-stop."""
        # Set session start balance if not set
        if self.session_start_balance <= 0:
            balance_data = await self.api.fetch_balance()
            if balance_data:
                self.session_start_balance = balance_data.get("balance", 0.0)
                self.decision_engine.analysis_data.session_start_balance = self.session_start_balance
                self.decision_engine._save_analysis_data()
        
        # Get current balance
        balance_data = await self.api.fetch_balance()
        if not balance_data:
            return
        current_balance = balance_data.get("balance", 0.0)
        
        # Check continuous mode conditions
        conditions = await self.decision_engine.check_continuous_mode_conditions(
            self.consecutive_wins, current_balance, self.session_start_balance
        )
        
        if conditions["should_stop_trading"]:
            # Auto-stop trading
            self.trading_enabled = False
            if self.bot:
                daily_profit = ((current_balance - self.session_start_balance) / self.session_start_balance * 100) if self.session_start_balance > 0 else 0.0
                await utils.send_telegram_message(
                    self.bot,
                    f"🎯 <b>AUTO-STOP TRIGGERED</b>\n\n"
                    f"📈 Daily Profit: <code>{daily_profit:.2f}%</code>\n"
                    f"💰 Balance: <code>{current_balance:.2f} XRP</code>\n"
                    f"🛑 Trading automatically stopped for profit preservation\n\n"
                    f"{conditions['message']}"
                )
            logger.info(f"Auto-stopped trading: {conditions['message']}")
            
        elif conditions["should_reduce_risk"]:
            # Apply risk reduction
            if self.params:
                original_stake = self.params.get("stake", 0.0)
                adjusted_params = self.decision_engine.apply_continuous_mode_adjustments(self.params)
                self.params.update(adjusted_params)
                self.save_params()
                
                if self.bot:
                    await utils.send_telegram_message(
                        self.bot,
                        f"🎯 <b>RISK REDUCTION APPLIED</b>\n\n"
                        f"🏆 Consecutive Wins: <code>{self.consecutive_wins}</code>\n"
                        f"📉 Stake Reduced: <code>{original_stake:.2f}</code> → <code>{self.params['stake']:.2f} XRP</code>\n"
                        f"🛡️ Take-Profit Adjusted: <code>{self.params['take_profit']:.1f}%</code>\n\n"
                        f"{conditions['message']}"
                    )
                logger.info(f"Applied risk reduction: consecutive wins = {self.consecutive_wins}")
                
                # Reset consecutive wins after applying reduction
                self.consecutive_wins = 0
                
        elif conditions["profit_target_reached"]:
            # Just send notification about profit target
            if self.bot and conditions["message"]:
                await utils.send_telegram_message(self.bot, f"📈 <b>PROFIT UPDATE</b>\n\n{conditions['message']}")

    async def check_trading_limits(self) -> bool:
        """
        Checks if cumulative win/loss limits have been reached.
        Returns True if trading can continue, False otherwise.
        """
        if self.is_stopping:
            return False

        try:
            balance_data = await self.api.fetch_balance()
            logger.debug(f"Balance data received: {balance_data}")
            
            if not balance_data or not isinstance(balance_data, dict):
                logger.error(f"Failed to fetch balance for limit check. Received: {balance_data}")
                if self.bot:
                    await utils.send_telegram_message(self.bot, "❌ Error: Could not fetch account balance. Pausing trading.")
                return False
                
            current_balance = balance_data.get("balance", 0.0)
            if current_balance == 0.0:
                logger.warning("Balance is 0.0 - this might indicate an API issue")
                
        except Exception as e:
            logger.error(f"Exception while fetching balance: {e}")
            if self.bot:
                await utils.send_telegram_message(self.bot, f"❌ Error fetching balance: {str(e)}. Pausing trading.")
            return False

        # Set initial balance if it hasn't been set yet
        if self.initial_balance <= 0:
            self.initial_balance = current_balance
            self.save_stats()
            logger.info(f"Initial balance set to: {self.initial_balance:.2f}")

        # DEBUG: Log current trading limits and cumulative values
        logger.info(f"=== TRADING LIMITS CHECK ===")
        logger.info(f"Cumulative loss: {self.cumulative_loss:.2f} XRP")
        logger.info(f"Max loss amount: {self.max_loss_amount:.2f} XRP")
        logger.info(f"Cumulative win: {self.cumulative_win:.2f} XRP")
        logger.info(f"Max win amount: {self.max_win_amount:.2f} XRP")
        logger.info(f"Net P/L: {self.stats.get('net_pl', 0.0):.2f} XRP")
        logger.info(f"Current mode: {self.decision_engine.get_current_mode().value}")
        logger.info(f"Trading enabled: {self.trading_enabled}")

        # Validate max loss amount is set
        if self.max_loss_amount <= 0:
            logger.warning("Max loss amount is not set or is 0 - limit checking may not work properly")
            if self.bot:
                await utils.send_telegram_message(
                    self.bot, 
                    f"⚠️ <b>WARNING: Max loss limit not set!</b>\n\n"
                    f"Please set a max loss amount to enable proper risk management."
                )
            return True  # Continue trading but warn user

        # Check win limit - Enhanced profit target handling
        if self.max_win_amount > 0 and self.cumulative_win >= self.max_win_amount:
            limit_msg = utils.fmt_limit("Win", self.cumulative_win, self.max_win_amount, self.initial_balance, current_balance)
            logger.warning(limit_msg)
            logger.info(f"=== MAX PROFIT TARGET REACHED ===")
            logger.info(f"Cumulative win: {self.cumulative_win:.2f} XRP")
            logger.info(f"Max win target: {self.max_win_amount:.2f} XRP")
            logger.info(f"Current balance: {current_balance:.2f} XRP")
            logger.info(f"Stopping trading for profit preservation")
            
            # Send comprehensive profit achievement notification
            if self.bot:
                growth_pct = (self.stats['net_pl'] / self.initial_balance * 100) if self.initial_balance > 0 else 0
                await utils.send_telegram_message(
                    self.bot, 
                    f"🎉 <b>PROFIT TARGET ACHIEVED!</b>\n\n"
                    f"💰 Cumulative Profit: <code>{self.cumulative_win:.2f} XRP</code>\n"
                    f"🎯 Target Reached: <code>{self.max_win_amount:.2f} XRP</code>\n"
                    f"📈 Account Growth: <code>{growth_pct:+.2f}%</code>\n"
                    f"💎 Current Balance: <code>{current_balance:.2f} XRP</code>\n"
                    f"📊 Total Trades: <code>{self.stats['total_trades']}</code>\n"
                    f"🏆 Win Rate: <code>{(self.stats['wins']/self.stats['total_trades']*100):.1f}%</code>\n\n"
                    f"🛑 <b>Trading STOPPED for profit preservation</b>\n"
                    f"💡 Use 'start trading' to continue with new targets\n"
                    f"🎯 Consider setting new profit goals for next session"
                )
            
            # Reset to continuous mode for next session
            if self.decision_engine.get_current_mode().value != "continuous":
                self.decision_engine.switch_to_continuous_mode("Profit target achieved - preparing for next session")
                logger.info("Switched to continuous mode for next trading session")
            
            # Reset consecutive wins for fresh start
            self.consecutive_wins = 0
            
            self.trading_enabled = False
            return False

        # Check loss limit - CRITICAL FIX: Always stop trading when max loss reached
        if self.max_loss_amount > 0 and self.cumulative_loss >= self.max_loss_amount:
            current_mode = self.decision_engine.get_current_mode().value
            engine_is_active = self.decision_engine.is_active()
            engine_state = self.decision_engine.analysis_data.state.value
            recovery_failures = self.decision_engine.analysis_data.recovery_failures
            
            logger.info(f"=== MAX LOSS REACHED ===")
            logger.info(f"Cumulative loss: {self.cumulative_loss:.2f} XRP (Limit: {self.max_loss_amount:.2f} XRP)")
            logger.info(f"Current mode: {current_mode}, Engine active: {engine_is_active}, Engine state: {engine_state}")
            logger.info(f"Recovery failures: {recovery_failures}")
            
            # CRITICAL FIX: Handle inconsistent engine state when max loss reached
            if engine_state == "inactive" and current_mode != "recovery":
                logger.warning("🔧 CRITICAL: Engine is inactive when max loss reached - forcing recovery analysis!")
                logger.warning("This should not happen in normal operation - forcing engine activation")
                
                if self.bot:
                    await utils.send_telegram_message(
                        self.bot, 
                        f"🔧 <b>ENGINE STATE FIX APPLIED</b>\n\n"
                        f"⚠️ Engine was inactive when max loss reached\n"
                        f"📉 Loss: <code>{self.cumulative_loss:.2f}</code> / <code>{self.max_loss_amount:.2f} XRP</code>\n"
                        f"🔄 <b>Force-triggering recovery analysis...</b>\n\n"
                        f"🛑 Trading stopped until recovery confirmation"
                    )
                
                # Force trigger recovery analysis
                try:
                    await self.decision_engine.trigger_drawdown_analysis(
                        current_balance=current_balance,
                        max_drawdown=self.max_loss_amount,
                        trading_pair=self.params.get("index", "R_10"),
                        trade_history=self.trade_history
                    )
                    logger.info("✅ Force-triggered recovery analysis successfully")
                except Exception as e:
                    logger.error(f"❌ Error force-triggering recovery analysis: {e}")
                
                # Stop trading and return
                self.trading_enabled = False
                logger.info("Trading disabled - recovery analysis force-triggered")
                return False
            
            # CRITICAL FIX: Check for stuck awaiting_confirmation state
            elif engine_state == "awaiting_confirmation":
                from datetime import datetime, timedelta
                confirmation_deadline = self.decision_engine.analysis_data.confirmation_deadline
                
                # Check if confirmation has been waiting too long (more than 2 minutes)
                if confirmation_deadline and datetime.now() > confirmation_deadline + timedelta(minutes=2):
                    logger.warning("❌ STUCK CONFIRMATION DETECTED - Engine has been awaiting confirmation for too long!")
                    logger.warning(f"Confirmation deadline was: {confirmation_deadline}")
                    logger.warning(f"Current time: {datetime.now()}")
                    logger.warning("🔧 FORCING AUTO-CONFIRMATION to unstick the engine...")
                    
                    if self.bot:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"🔧 <b>STUCK ENGINE DETECTED & FIXED</b>\n\n"
                            f"⚠️ Decision engine was stuck awaiting confirmation\n"
                            f"🕐 Deadline passed: {confirmation_deadline.strftime('%H:%M:%S') if confirmation_deadline else 'Unknown'}\n"
                            f"🔄 <b>Forcing auto-confirmation to proceed with recovery...</b>\n\n"
                            f"🚨 Switching to recovery mode now!"
                        )
                    
                    # Force auto-confirmation
                    try:
                        await self.decision_engine._execute_confirmation(True, auto_confirmed=True)
                        logger.info("✅ Forced auto-confirmation completed - engine should be unstuck now")
                    except Exception as e:
                        logger.error(f"❌ Error during forced auto-confirmation: {e}")
                        # If forced confirmation fails, reset the engine
                        logger.warning("🔄 Forced confirmation failed - resetting engine completely")
                        self.decision_engine.reset_engine()
                
                # Always stop trading when confirmation is pending
                self.trading_enabled = False
                
                # FIXED: Better time calculation to avoid negative values
                if confirmation_deadline:
                    remaining = (confirmation_deadline - datetime.now()).total_seconds()
                    remaining = max(0, remaining)  # Ensure it's never negative
                    
                    if remaining > 0:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"⏳ <b>RECOVERY CONFIRMATION PENDING</b>\n\n"
                            f"🧠 Decision engine analysis complete\n"
                            f"⏰ Auto-confirmation in: <code>{remaining:.0f}s</code>\n"
                            f"💬 Reply 'yes' or 'no' to confirm faster\n\n"
                            f"🛑 Trading stopped until confirmation"
                        )
                    else:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"⏳ <b>RECOVERY CONFIRMATION PENDING</b>\n\n"
                            f"🧠 Decision engine analysis complete\n"
                            f"⏰ Auto-confirmation in progress...\n"
                            f"💬 Reply 'yes' or 'no' to confirm now\n\n"
                            f"🛑 Trading stopped until confirmation"
                        )
                else:
                    await utils.send_telegram_message(
                        self.bot, 
                        f"⏳ <b>RECOVERY CONFIRMATION PENDING</b>\n\n"
                        f"🧠 Decision engine analysis complete\n"
                        f"💬 Reply 'yes' or 'no' to confirm\n\n"
                        f"🛑 Trading stopped until confirmation"
                    )
                
                logger.info("Trading disabled - awaiting recovery confirmation")
                return False
            
            # If not in recovery mode yet, trigger recovery analysis
            elif current_mode != "recovery":
                logger.info(f"Not in recovery mode ({current_mode}) - triggering initial recovery analysis")
                
                # TRIGGER DECISION ENGINE for first time recovery analysis
                if not engine_is_active:
                    logger.info("✅ Triggering initial recovery mode analysis")
                    try:
                        await self.decision_engine.trigger_drawdown_analysis(
                            current_balance=current_balance,
                            max_drawdown=self.max_loss_amount,
                            trading_pair=self.params.get("index", "R_10"),
                            trade_history=self.trade_history
                        )
                        logger.info("✅ Decision engine trigger completed successfully")
                    except Exception as e:
                        logger.error(f"❌ Error triggering decision engine: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        
                    if self.bot:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"🚨 <b>MAX DRAWDOWN REACHED</b>\n\n"
                            f"📉 Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                            f"⚠️ Loss Limit: <code>{self.max_loss_amount:.2f} XRP</code>\n"
                            f"🛑 <b>Trading STOPPED until recovery confirmation</b>\n\n"
                            f"🧠 Decision engine is analyzing recovery options..."
                        )
                else:
                    logger.info(f"Decision engine already active (state: {engine_state}) - forcing recovery mode")
                    
                    # Reset the engine and force recovery mode analysis when max loss is reached
                    logger.info("Resetting decision engine to force recovery mode analysis")
                    try:
                        # Force reset the engine to stop current analysis
                        self.decision_engine.reset_engine()
                        
                        # Now trigger recovery mode analysis
                        await self.decision_engine.trigger_drawdown_analysis(
                            current_balance=current_balance,
                            max_drawdown=self.max_loss_amount,
                            trading_pair=self.params.get("index", "R_10"),
                            trade_history=self.trade_history
                        )
                        logger.info("✅ Forced recovery mode analysis started successfully")
                        
                        if self.bot:
                            await utils.send_telegram_message(
                                self.bot, 
                                f"🚨 <b>MAX DRAWDOWN REACHED</b>\n\n"
                                f"📉 Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                                f"⚠️ Loss Limit: <code>{self.max_loss_amount:.2f} XRP</code>\n"
                                f"🛑 <b>Trading STOPPED</b>\n\n"
                                f"🔄 Forcing recovery mode analysis...\n"
                                f"🧠 Decision engine is analyzing recovery options..."
                            )
                            
                    except Exception as e:
                        logger.error(f"❌ Error forcing recovery mode analysis: {e}")
                        
                        if self.bot:
                            await utils.send_telegram_message(
                                self.bot, 
                                f"🚨 <b>MAX DRAWDOWN REACHED</b>\n\n"
                                f"📉 Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                                f"⚠️ Loss Limit: <code>{self.max_loss_amount:.2f} XRP</code>\n"
                                f"🛑 <b>Trading STOPPED</b>\n\n"
                                f"❌ Error starting recovery analysis: {str(e)}"
                            )
                
                # ALWAYS stop trading when max drawdown is reached
                self.trading_enabled = False
                logger.info("Trading disabled due to max drawdown - will resume only after recovery confirmation")
                return False
            
            # If already in recovery mode, allow trading unless analysis is in progress
            elif current_mode == "recovery":
                logger.info(f"Already in recovery mode with {recovery_failures} failures")
                
                # If engine is active (analysis in progress), stop trading  
                if engine_is_active:
                    self.trading_enabled = False
                    logger.info("Trading disabled - recovery analysis in progress")
                    
                    if self.bot:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"🚨 <b>RECOVERY ANALYSIS IN PROGRESS</b>\n\n"
                            f"📉 Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                            f"⚠️ Loss Limit: <code>{self.max_loss_amount:.2f} XRP</code>\n"
                            f"🔄 Recovery Mode: Active ({recovery_failures} failures)\n"
                            f"🛑 <b>Trading STOPPED while analysis completes</b>\n\n"
                            f"⏳ Please wait for recovery confirmation..."
                        )
                    
                    return False
                
                # If too many failures and engine is inactive, re-trigger analysis
                elif recovery_failures > 5 and not engine_is_active:
                    logger.warning("Too many recovery failures - re-triggering recovery analysis")
                    if self.bot:
                        await utils.send_telegram_message(
                            self.bot, 
                            f"⚠️ <b>RECOVERY MODE ISSUE DETECTED</b>\n\n"
                            f"📉 Cumulative Loss: <code>{self.cumulative_loss:.2f} XRP</code>\n"
                            f"⚠️ Loss Limit: <code>{self.max_loss_amount:.2f} XRP</code>\n"
                            f"🔄 Re-triggering recovery analysis after {recovery_failures} failures...\n\n"
                            f"🛑 Trading will stop until new recovery strategy is confirmed"
                        )
                    
                    # Force re-trigger the analysis
                    try:
                        await self.decision_engine.trigger_drawdown_analysis(
                            current_balance=current_balance,
                            max_drawdown=self.max_loss_amount,
                            trading_pair=self.params.get("index", "R_10"),
                            trade_history=self.trade_history
                        )
                        logger.info("✅ Recovery analysis re-triggered successfully")
                    except Exception as e:
                        logger.error(f"❌ Error re-triggering recovery analysis: {e}")
                    
                    # Stop trading until new analysis is complete
                    self.trading_enabled = False
                    logger.info("Trading disabled - recovery analysis re-triggered")
                    return False
                
                # Normal recovery mode - engine inactive, allow trading to continue for recovery
                else:
                    logger.info("Recovery mode active - allowing trading to continue for loss recovery")
                    return True  # ALLOW TRADING TO CONTINUE IN RECOVERY MODE

        return True

    async def start_new_trade(self):
        """Starts a new trade with the current parameters."""
        try:
            # Check if decision engine has proposed new parameters FIRST
            # This allows recovery mode to re-enable trading when parameters are confirmed
            logger.debug("Checking for proposed parameters from decision engine...")
            proposed_params = self.decision_engine.get_proposed_parameters()
            logger.debug(f"Decision engine returned: {proposed_params}")
            if proposed_params:
                logger.info("Applying parameters from decision engine and resuming trading")
                
                # Check if this is recovery mode BEFORE updating parameters
                is_recovery_mode = proposed_params.get("is_recovery", False)
                recovery_forecast = proposed_params.get("recovery_forecast")
                
                logger.info(f"Parameters received - Recovery mode: {is_recovery_mode}")
                
                # Update parameters
                self.params.update({
                    "index": proposed_params["index"],  # Update to the best selected index
                    "stake": proposed_params["stake"],
                    "growth_rate": proposed_params["growth_rate"],
                    "take_profit": proposed_params["take_profit"]
                })
                
                # Re-enable trading since we have new optimized parameters
                self.trading_enabled = True
                
                # DON'T reset cumulative loss here - this breaks max drawdown tracking!
                # Only reset cumulative loss when:
                # 1. Manually stopping/resetting trading
                # 2. Successfully completing recovery (handled by recovery success handler)
                # 3. Manual stats reset
                # Cumulative loss should persist to track when max drawdown is truly reached
                
                self.save_stats()
                logger.info(f"Trading resumed with new parameters (cumulative loss preserved): {self.params}")
                
                # Send recovery mode activation notification if this is recovery mode
                if is_recovery_mode and self.bot:
                    logger.info("Sending recovery mode activation notification...")
                    recovery_msg = (
                        f"🚨 <b>RECOVERY MODE ACTIVATED</b>\n\n"
                        f"🏆 Starting high-risk recovery with optimized parameters:\n"
                        f"└ Index: <code>{self.params['index']}</code> (Best for recovery)\n"
                        f"└ Stake: <code>{self.params['stake']:.2f}</code> XRP (HIGH RISK)\n"
                        f"└ Take-Profit: <code>{self.params['take_profit']:.0f}%</code>\n"
                        f"└ Growth Rate: <code>{self.params['growth_rate']:.1f}%</code>\n"
                        f"└ Mode: <code>RECOVERY</code> 🚨\n\n"
                    )
                    
                    # Add forecast information if available
                    if recovery_forecast:
                        recovery_msg += (
                            f"📊 <b>Recovery Forecast:</b>\n"
                            f"└ Loss to Recover: <code>{recovery_forecast['loss_to_recover']:.2f} XRP</code>\n"
                            f"└ Estimated Trades: <code>{recovery_forecast['estimated_trades']}</code>\n"
                            f"└ Success Probability: <code>{recovery_forecast['recovery_probability']}</code>\n"
                            f"└ Risk Level: <code>{recovery_forecast['risk_assessment']}</code>\n"
                            f"└ Time Estimate: <code>{recovery_forecast['time_estimate']}</code>\n\n"
                        )
                    
                    recovery_msg += f"⚡ <b>Recovery trading engaged!</b>"
                    
                    try:
                        await utils.send_telegram_message(self.bot, recovery_msg)
                        logger.info("✅ Recovery mode activation notification sent")
                    except Exception as e:
                        logger.error(f"❌ Failed to send recovery mode notification: {e}")
                else:
                    logger.info(f"Not recovery mode or no bot - skipping recovery notification (recovery: {is_recovery_mode}, bot: {bool(self.bot)})")
                
                # Parameters are automatically cleared when retrieved

            # NOW check if trading is enabled after potentially re-enabling it
            if not self.trading_enabled or self.is_stopping:
                logger.info("Trading is disabled or stopping, skipping new trade.")
                return

            # Check trading limits before starting new trade
            if not await self.check_trading_limits():
                logger.info("Trading limits reached, stopping trading.")
                self.trading_enabled = False
                if self.bot:
                    await utils.send_telegram_message(self.bot, "⚠️ Trading stopped: Limits reached.")
                return

            # Validate parameters before proceeding
            if not self.params or not all(key in self.params for key in ["index", "stake", "growth_rate", "take_profit", "currency"]):
                logger.error(f"Invalid or incomplete parameters: {self.params}")
                if self.bot:
                    await utils.send_telegram_message(self.bot, "❌ Error: Trading parameters are incomplete. Please restart trading.")
                self.trading_enabled = False
                return
            
            # Apply recovery risk reduction if in recovery mode with failures
            risk_reduction_message_sent = False
            if (self.decision_engine.get_current_mode().value == "recovery" and 
                self.decision_engine.analysis_data.recovery_failures > 0):
                logger.info("Applying recovery risk reduction to trade parameters")
                try:
                    original_stake = self.params.get("stake", 0.0)
                    reduced_params = self.decision_engine.apply_recovery_risk_reduction(self.params)
                    if reduced_params and reduced_params.get("stake", 0.0) != original_stake:
                        # Risk reduction was actually applied
                        self.params = reduced_params
                        logger.info(f"Risk reduction applied. New params: {self.params}")
                        
                        # Send risk reduction message only when stake actually changed
                        if self.bot:
                            await utils.send_telegram_message(
                                self.bot, 
                                f"🔄 <b>RECOVERY RISK REDUCTION APPLIED</b>\n\n"
                                f"📉 Risk reduced after failure #{self.decision_engine.analysis_data.recovery_failures}\n"
                                f"└ Index: <code>{self.params['index']}</code>\n"
                                f"└ Reduced Stake: <code>{self.params['stake']:.2f}</code> XRP\n"
                                f"└ Take-Profit: <code>{self.params['take_profit']:.0f}%</code>\n"
                                f"└ Risk Factor: <code>{self.decision_engine.analysis_data.recovery_risk_reduction:.2f}</code>\n\n"
                                f"🚨 Continuing recovery with safer parameters..."
                            )
                            risk_reduction_message_sent = True
                    else:
                        logger.debug("No risk reduction needed - stake unchanged")
                except Exception as e:
                    logger.error(f"Error applying recovery risk reduction: {e}")
                    # Continue with original parameters
            
            # Small delay only if a risk reduction message was sent
            if risk_reduction_message_sent:
                await asyncio.sleep(1)

            logger.info(f"Placing trade with params: {self.params}")
            
            # Place the trade
            try:
                trade = await self.api.place_trade(
                    symbol=self.params["index"],
                    amount=self.params["stake"],
                    growth_rate=self.params["growth_rate"],
                    currency=self.params["currency"],
                    take_profit=self.params["take_profit"]
                )
                logger.info(f"Trade placement response: {trade}")
                
            except Exception as e:
                logger.error(f"Exception during trade placement: {e}")
                if self.bot:
                    await utils.send_telegram_message(self.bot, f"❌ Error placing trade: {str(e)}")
                return

            if not trade:
                logger.error("No trade object received from trade placement.")
                if self.bot:
                    await utils.send_telegram_message(self.bot, "❌ Error: Trade placement failed - no response from API.")
                return

            if not isinstance(trade, Trade):
                logger.error(f"Invalid response type: {type(trade)}")
                if self.bot:
                    await utils.send_telegram_message(self.bot, f"❌ Error: Invalid trade response type: {type(trade)}")
                return

            logger.info(f"Trade object created: {trade.__dict__}")

            # Calculate estimated time to take profit
            if trade.take_profit and trade.growth_rate:
                take_profit_decimal = trade.take_profit / 100.0
                growth_rate_per_second = trade.growth_rate
                raw_time = take_profit_decimal / growth_rate_per_second
                trade.estimated_tp_time = raw_time + 1  # Add 1 second buffer
            else:
                trade.estimated_tp_time = 2  # Default duration

            # Store the trade
            self.active_trades[trade.contract_id] = trade

            # Start monitoring the trade
            asyncio.create_task(self.monitor_trade_closure(trade))

        except Exception as e:
            logger.error(f"Error starting new trade: {e}\n{traceback.format_exc()}")
            if self.bot:
                await utils.send_telegram_message(self.bot, f"❌ Error starting new trade: {str(e)}")

    def _get_next_status(self) -> str:
        """Get the next status message in rotation."""
        status = self.status_messages[self.current_status_index]
        self.current_status_index = (self.current_status_index + 1) % len(self.status_messages)
        return status

    def _get_next_comment(self) -> str:
        """Get the next comment in rotation."""
        if not hasattr(self, '_comment_index'):
            self._comment_index = 0
        comment = self.sarcastic_comments[self._comment_index]
        self._comment_index = (self._comment_index + 1) % len(self.sarcastic_comments)
        return comment

    def _get_dots(self, count: int) -> str:
        """Get dots based on count (1-3)."""
        return "." * count

    async def _send_new_progress_message(self, trade: Trade):
        """Helper method to send and pin a new progress message."""
        try:
            # Unpin any existing message first
            if self.progress_message_id:
                try:
                    await self.bot.unpin_chat_message(chat_id=config.GROUP_ID)
                except Exception as e:
                    logger.debug(f"No message to unpin: {e}")

            # Calculate trade count
            trade_count = self.stats['total_trades'] + 1

            initial_msg = await utils.send_telegram_message(self.bot, 
                f"🤖 <b>{self._get_next_status()}</b>\n"
                f"{'=' * 40}\n\n"
                f"📊 <b>Trade Details</b>\n"
                f"└ Contract ID: <code>{trade.contract_id}</code>\n"
                f"└ Symbol: <code>{trade.symbol}</code>\n"
                f"└ Stake: <code>{trade.stake:.2f}</code> {trade.currency}\n"
                f"└ Growth Rate: <code>{trade.growth_rate*100:.1f}%</code>\n"
                f"└ Take Profit: <code>{trade.take_profit}%</code>\n"
                f"└ Estimated Time: <code>{trade.estimated_tp_time:.0f}</code>s\n\n"
                f"⏳ <b>Progress</b>\n"
                f"└ Status: <code>Starting...</code>\n"
                f"└ Time Remaining: <code>{trade.estimated_tp_time:.0f}</code>s\n\n"
                f"{'=' * 40}\n"
                f"📈 <b>Session Stats</b>\n"
                f"└ Wins: <code>{self.stats['wins']}</code> | Losses: <code>{self.stats['losses']}</code>\n"
                f"└ Net P/L: <code>{self.stats['net_pl']:+.2f}</code> {trade.currency}\n\n"
                f"💭 <i>{self._get_next_comment()}</i>"
            )
            if not initial_msg:
                logger.error("Failed to send initial trade notification")
                return
                
            # Pin the progress message
            await self.bot.pin_chat_message(
                chat_id=config.GROUP_ID,
                message_id=initial_msg.message_id,
                disable_notification=True
            )
            self.progress_message_id = initial_msg.message_id

            # Try to delete the 'pinned message' notification
            await asyncio.sleep(0.5)  # Wait for notification to appear
            try:
                updates = await self.bot.get_updates(timeout=5)
                for update in updates[::-1]:
                    msg = update.to_dict().get('message')
                    if msg and msg.get('pinned_message'):
                        await self.bot.delete_message(chat_id=config.GROUP_ID, message_id=msg['message_id'])
                        break
            except Exception as e:
                logger.debug(f"Could not delete pin notification: {e}")
        except Exception as e:
            logger.error(f"Error sending new progress message: {e}")

    async def monitor_trade_closure(self, trade: Trade):
        """Monitor a trade until it closes or hits take profit."""
        try:
            if not self.bot:
                logger.error("No bot instance available for sending notifications")
                return

            if not trade.estimated_tp_time:
                logger.error(f"Cannot monitor trade {trade.contract_id}: no estimated TP time.")
                return

            logger.info(f"Monitoring trade {trade.contract_id} for {trade.estimated_tp_time:.2f} seconds.")

            # Send initial trade notification
            trade_count = self.stats['total_trades'] + 1
            initial_msg = (
                f"🎯 Trade #{trade_count}\n"
                f"{'=' * 40}\n\n"
                f"📊 Trade Details\n"
                f"└ Contract ID: {trade.contract_id}\n"
                f"└ Symbol: {trade.symbol}\n"
                f"└ Stake: {trade.stake:.2f} {trade.currency}\n"
                f"└ Growth Rate: {trade.growth_rate*100:.1f}%\n"
                f"└ Take Profit: {trade.take_profit}%\n"
                f"└ Estimated Time: {trade.estimated_tp_time:.0f}s\n\n"
                f"⏳ Progress\n"
                f"└ Status: Starting...\n"
                f"└ Progress: 0%\n"
                f"└ Time Remaining: {trade.estimated_tp_time:.0f}s\n\n"
                f"{'=' * 40}\n"
                f"📈 Session Stats\n"
                f"└ Wins: {self.stats['wins']} | Losses: {self.stats['losses']}\n"
                f"└ Net P/L: {self.stats['net_pl']:+.2f} {trade.currency}\n\n"
                f"<pre><b>Decter 001</b>\n{self._get_next_comment()}.</pre>"
            )
            
            # Pin the progress message only once (on first trade)
            if not hasattr(self, '_progress_pinned'):
                self._progress_pinned = False
            # Reuse the same progress message for new trades by editing it, unless there is no previous message
            if self.progress_message_id:
                try:
                    await self.bot.edit_message_text(
                        chat_id=config.GROUP_ID,
                        message_id=self.progress_message_id,
                        text=initial_msg,
                        parse_mode='HTML'
                    )
                    # Pin only the first time
                    if not self._progress_pinned:
                        try:
                            await self.bot.pin_chat_message(chat_id=config.GROUP_ID, message_id=self.progress_message_id, disable_notification=True)
                            self._progress_pinned = True
                        except Exception as e:
                            logger.debug(f"Pinning failed: {e}")
                except Exception as e:
                    logger.error(f"Error editing progress message for new trade: {e}")
                    sent_msg = await utils.send_telegram_message(self.bot, initial_msg, parse_mode='HTML')
                    if sent_msg:
                        self.progress_message_id = sent_msg.message_id
                        if not self._progress_pinned:
                            try:
                                await self.bot.pin_chat_message(chat_id=config.GROUP_ID, message_id=sent_msg.message_id, disable_notification=True)
                                self._progress_pinned = True
                            except Exception as e:
                                logger.debug(f"Pinning failed: {e}")
            else:
                sent_msg = await utils.send_telegram_message(self.bot, initial_msg, parse_mode='HTML')
                if sent_msg:
                    self.progress_message_id = sent_msg.message_id
                    if not self._progress_pinned:
                        try:
                            await self.bot.pin_chat_message(chat_id=config.GROUP_ID, message_id=sent_msg.message_id, disable_notification=True)
                            self._progress_pinned = True
                        except Exception as e:
                            logger.debug(f"Pinning failed: {e}")

            # Calculate end time
            end_time = time.time() + trade.estimated_tp_time
            last_update = time.time()
            update_interval = 3  # Update every 3 seconds to avoid flood control
            dot_count = 0
            last_comment_change = time.time()
            comment_change_interval = 3  # Change comment every 3 seconds
            current_remark = self._get_next_comment()

            while time.time() < end_time and trade.contract_id in self.active_trades:
                current_time = time.time()
                elapsed = current_time - (end_time - trade.estimated_tp_time)
                progress = (elapsed / trade.estimated_tp_time) * 100

                if current_time - last_update >= update_interval:
                    remaining_time = int(end_time - current_time)
                    if remaining_time <= 0:
                        break

                    # Animated dots and remark cycling
                    dot_count = (dot_count % 3) + 1
                    if current_time - last_comment_change >= comment_change_interval:
                        current_remark = self._get_next_comment()
                        last_comment_change = current_time

                    # Determine progress status
                    if progress >= 100:
                        progress_status = "Completing..."
                    elif progress >= 75:
                        progress_status = "Almost Done"
                    elif progress >= 50:
                        progress_status = "Halfway"
                    elif progress >= 25:
                        progress_status = "In Progress"
                    else:
                        progress_status = "Starting"

                    # Format the progress message
                    progress_msg = (
                        f"🎯 Trade #{trade_count}\n"
                        f"{'=' * 40}\n\n"
                        f"📊 Trade Details\n"
                        f"└ Contract ID: {trade.contract_id}\n"
                        f"└ Symbol: {trade.symbol}\n"
                        f"└ Stake: {trade.stake:.2f} {trade.currency}\n"
                        f"└ Growth Rate: {trade.growth_rate*100:.1f}%\n"
                        f"└ Take Profit: {trade.take_profit}%\n"
                        f"└ Estimated Time: {trade.estimated_tp_time:.0f}s\n\n"
                        f"⏳ Progress\n"
                        f"└ Status: {progress_status}\n"
                        f"└ Progress: {progress:.0f}%\n"
                        f"└ Time Remaining: {remaining_time}s\n\n"
                        f"{'=' * 40}\n"
                        f"📈 Session Stats\n"
                        f"└ Wins: {self.stats['wins']} | Losses: {self.stats['losses']}\n"
                        f"└ Net P/L: {self.stats['net_pl']:+.2f} {trade.currency}\n\n"
                        f"<pre><b>Decter 001</b>\n{current_remark}{self._get_dots(dot_count)}</pre>"
                    )

                    # Edit the progress message (do not pin)
                    try:
                        await self.bot.edit_message_text(
                            chat_id=config.GROUP_ID,
                            message_id=self.progress_message_id,
                            text=progress_msg,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Error updating progress message: {e}")
                        # If edit fails, send a new message (do not pin)
                        sent_msg = await utils.send_telegram_message(self.bot, progress_msg, parse_mode='HTML')
                        if sent_msg:
                            self.progress_message_id = sent_msg.message_id

                    last_update = current_time

                await asyncio.sleep(0.1)  # Shorter sleep for more responsive updates

            # Add a small buffer to ensure the trade is closed on the backend
            await asyncio.sleep(1)

            # Check if trade is still active
            if trade.contract_id in self.active_trades:
                logger.info(f"Trade {trade.contract_id} reached estimated end time, finalizing...")
                try:
                    await self.finalize_trade(trade)
                    logger.info(f"finalize_trade called for {trade.contract_id}")
                except Exception as e:
                    logger.error(f"Exception in finalize_trade for {trade.contract_id}: {e}")
            else:
                logger.warning(f"Trade {trade.contract_id} not in active_trades at finalize step.")

            # Auto-rebuy if enabled
            if self.trading_enabled and not self.is_stopping:
                logger.info("Auto-rebuy triggered.")
                await asyncio.sleep(1)
                await self.start_new_trade()

        except Exception as e:
            logger.error(f"Error monitoring trade {trade.contract_id}: {e}\n{traceback.format_exc()}")
            if self.bot:
                await utils.send_telegram_message(
                    self.bot,
                    f"❌ Error monitoring trade {trade.contract_id}: {str(e)}"
                )

    async def finalize_trade(self, trade: Trade):
        """Finalize a trade and update stats."""
        try:
            logger.info(f"Starting finalize_trade for {trade.contract_id}")
            # Get the trade outcome
            outcome = await self.api.get_trade_outcome(trade.contract_id)
            logger.info(f"Outcome for {trade.contract_id}: {outcome}")
            if not outcome:
                logger.error(f"Could not get outcome for trade {trade.contract_id}")
                return

            # Update trade details
            trade.close_time = datetime.now()
            trade.status = "closed"
            trade.profit_loss = outcome.get("profit", 0.0)
            trade.post_trade_balance = outcome.get("sell_price", 0.0)

            # Update stats
            await self.update_stats_after_trade(trade)

            # Remove from active trades
            if trade.contract_id in self.active_trades:
                del self.active_trades[trade.contract_id]

            # Delete previous outcome notification if exists
            if self.last_outcome_message_id:
                try:
                    await self.bot.delete_message(chat_id=config.GROUP_ID, message_id=self.last_outcome_message_id)
                except Exception as e:
                    logger.debug(f"Could not delete previous outcome notification: {e}")
                self.last_outcome_message_id = None

            # Send completion message (plain text, no HTML)
            if self.bot:
                try:
                    logger.info(f"Sending completion message for {trade.contract_id}")
                    emoji = '✅' if trade.profit_loss > 0 else '❌'
                    completion_msg = (
                        f"{emoji} Trade #{self.stats['total_trades']} Completed\n"
                        f"{'=' * 40}\n\n"
                        f"📊 Trade Details\n"
                        f"└ Contract ID: {trade.contract_id}\n"
                        f"└ Symbol: {trade.symbol}\n"
                        f"└ Stake: {trade.stake:.2f} {trade.currency}\n"
                        f"└ P/L: {trade.profit_loss:+.2f} {trade.currency}\n"
                        f"└ Result: {'Win' if trade.profit_loss > 0 else 'Loss'}\n\n"
                        f"{'=' * 40}\n"
                        f"📈 Session Stats\n"
                        f"└ Wins: {self.stats['wins']} | Losses: {self.stats['losses']}\n"
                        f"└ Net P/L: {self.stats['net_pl']:+.2f} {trade.currency}"
                    )
                    msg = await utils.send_telegram_message(self.bot, completion_msg)
                    if msg:
                        self.last_outcome_message_id = msg.message_id
                    logger.info(f"Completion message sent for {trade.contract_id}")
                except Exception as e:
                    logger.error(f"Error sending completion message for {trade.contract_id}: {e}")
        except Exception as e:
            logger.error(f"Error finalizing trade {trade.contract_id}: {e}\n{traceback.format_exc()}")
            if self.bot:
                await utils.send_telegram_message(
                    self.bot,
                    f"❌ Error finalizing trade {trade.contract_id}: {str(e)}"
                )
