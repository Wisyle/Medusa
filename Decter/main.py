import asyncio
import csv
import os
import signal
import sys
import traceback
import re
from datetime import datetime
from typing import Optional
from collections import deque
from pathlib import Path
import random
import json

from telegram import Bot
from telegram.error import TelegramError

# Import the refactored modules
import config
import utils
from deriv_api import DerivAPI
from trading_state import TradingState

# --- Global Instances ---
# Initialize early so they are available throughout the script
logger = utils.setup_logging()
bot: Optional[Bot] = None
state: Optional[TradingState] = None
BOT_VERSION: float = utils.get_bot_version()

# Track sent and user messages for deletion
message_queue = deque(maxlen=500)  # (message_id, timestamp, is_bot_message)

# Professional, emotionless trading quotes
TRADING_QUOTES = [
    "Discipline is the bridge between goals and accomplishment.",
    "The market is neither your friend nor your enemy.",
    "Consistency is more important than intensity.",
    "Risk comes from not knowing what you are doing.",
    "Let your system, not your emotions, drive your trades.",
    "Losses are simply the cost of doing business.",
    "Trade the plan, not the hope.",
    "Every trade is just one of many.",
    "Focus on process, not outcome.",
    "Capital preservation is the first rule of trading."
]

# To bump version after a fix, call:
# utils.bump_bot_version('Describe your fix or feature here')

# Unicode progress bar helper
def make_progress_bar(current, total, length=18, color_emoji=None):
    pct = 0 if total == 0 else min(max(current / total, 0), 1)
    filled = int(length * pct)
    empty = length - filled
    bar = '█' * filled + '░' * empty
    if color_emoji:
        return f"{bar} {color_emoji} <code>{current:.2f}/{total:.2f}</code>"
    return f"{bar} <code>{current:.2f}/{total:.2f}</code>"

# --- Command Router ---
awaiting_fix_description = False
fix_prompt_message_id = None

async def handle_command(update: dict):
    """Processes incoming commands from Telegram."""
    global state, bot, message_queue, awaiting_fix_description, fix_prompt_message_id
    if not update.get("message") or not update["message"].get("text"):
        return

    # Basic filtering for group and topic ID
    if int(update["message"]["chat"]["id"]) != int(config.GROUP_ID) or \
       int(update["message"].get("message_thread_id", 0)) != int(config.TOPIC_ID):
        return

    txt = update["message"]["text"].strip().lower()
    logger.info(f"Processing command: '{txt}'")
    
    # Delete user message immediately after reading
    try:
        await bot.delete_message(chat_id=config.GROUP_ID, message_id=update["message"]["message_id"])
    except Exception as e:
        logger.error(f"Failed to delete user message: {e}")

    # Handle fix description prompt
    if awaiting_fix_description:
        user_fix = update["message"]["text"].strip()
        if user_fix.lower() == "nothing":
            await send_and_track_message(bot, "Noted. No fix recorded. You'll be asked again next time.")
            awaiting_fix_description = False
            # Optionally delete the prompt message
            if fix_prompt_message_id:
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=fix_prompt_message_id)
                except Exception as e:
                    logger.error(f"Failed to delete fix prompt message: {e}")
                fix_prompt_message_id = None
            return
        # Update the most recent fix in version.json
        version_data = utils.load_json_file(config.VERSION_FILE, {"commit": "none", "version": 1.0, "recent_fixes": []})
        recent_fixes = version_data.get("recent_fixes", [])
        if recent_fixes:
            recent_fixes[0] = user_fix
            version_data["recent_fixes"] = recent_fixes[:5]
            utils.save_json_file(config.VERSION_FILE, version_data)
            await send_and_track_message(bot, f"Thanks! Noted your fix: <code>{recent_fixes[0]}</code>")
        else:
            await send_and_track_message(bot, "No version record found to update.")
        awaiting_fix_description = False
        # Delete the prompt message
        if fix_prompt_message_id:
            try:
                await bot.delete_message(chat_id=config.GROUP_ID, message_id=fix_prompt_message_id)
            except Exception as e:
                logger.error(f"Failed to delete fix prompt message: {e}")
            fix_prompt_message_id = None
        return

    # Track user message for deletion (no longer needed, since we delete immediately)
    # message_queue.append((update["message"]["message_id"], datetime.now(), False))
    
    try:
        # --- Command Handling ---

        if txt == "start 001":
            # Initializes the bot and gets it ready for trading commands
            if state.trading_enabled:
                await send_and_track_message(bot, "Bot is already running! 🏃‍♂️")
                return
            
            balance_data = await state.api.fetch_balance()
            balance = balance_data.get('balance', 0.0) if balance_data else 0.0
            currency = balance_data.get('currency', 'N/A') if balance_data else ''

            startup_msg = (
                f"{utils.snark(config._STARTUP_LINES[0])} 🚀\n"
                f"Balance: <code>{balance:.6f}</code> {currency} 💰\n"
                f"Version: <code>{BOT_VERSION:.1f}</code>"
            )
            await send_and_track_message(bot, startup_msg)
            return

        elif txt == "start trading":
            if state.trading_enabled:
                await send_and_track_message(bot, "Trading is already active! 🎯")
                return
            
            # Check if saved parameters exist
            if state.saved_params:
                params_str = "\n".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in state.saved_params.items()])
                msg = await send_and_track_message(bot, f"Found saved parameters:\n<pre>{params_str}</pre>\n\nUse saved parameters? (yes/no)")
                state.awaiting_input = "use_saved"
                if msg:
                    state.last_saved_params_prompt_id = msg.message_id
            else:
                await send_and_track_message(bot, "Enter stake amount (minimum <code>0.4</code>):")
                state.awaiting_input = "stake"
            return
            
        elif txt == "stop trading":
            state.trading_enabled = False
            state.is_stopping = True
            active_count = len(state.active_trades)
            if active_count > 0:
                 await send_and_track_message(bot, f"Stopping trading and closing {active_count} active position(s)...")
                 # In a real app, you would loop through and sell each active contract
                 # for trade in list(state.active_trades.values()):
                 #     await state.api.sell_contract(trade.contract_id)
                 state.active_trades.clear()
            
            # Reset cumulative stats for a fresh start next time
            state.cumulative_loss = 0.0
            state.cumulative_win = 0.0
            state.save_stats()
            
            await send_and_track_message(bot, "Trading stopped. All limits and stats have been reset.")
            state.is_stopping = False
            return

        elif txt == "reset stats":
            if state.trading_enabled:
                await send_and_track_message(bot, "⚠️ Cannot reset stats while trading is active. Please stop trading first.")
                return
                
            # Reset only parameters and cumulative values
            state.cumulative_loss = 0.0
            state.cumulative_win = 0.0
            state.saved_params = {}
            state.params = {}
            state.max_loss_amount = 0.0
            state.max_win_amount = 0.0
            
            # Save the reset state
            state.save_params()
            state.save_stats()
            
            await send_and_track_message(bot, "✅ Parameters and cumulative values have been reset successfully!")
            return

        # --- Multi-step command handling ---
        if state.awaiting_input:
            await handle_input_flow(txt)
            return

        # --- Informational Commands ---
        elif txt == "status":
            await handle_status_command()
            return
        elif txt == "history":
            await handle_history_command()
            return
        elif txt == "export":
            await handle_export_command()
            return
        elif txt == "engine status":
            await handle_engine_status_command()
            return
        elif txt == "resume halt":
            await handle_resume_halt_command()
            return
        elif txt == "bot thinking":
            await handle_bot_thinking_command()
            return
        elif txt == "fetch manual":
            await handle_fetch_manual_command()
            return
        elif txt == "mode status":
            await handle_mode_status_command()
            return
        elif txt == "force continuous":
            await handle_force_continuous_command()
            return
        elif txt == "debug limits":
            await handle_debug_limits_command()
            return
        elif txt == "reset engine":
            await handle_reset_engine_command()
            return
        elif txt == "force confirm":
            await handle_force_confirm_command()
            return
        elif txt == "restart engine":
            await handle_restart_engine_command()
            return
        elif txt == "/stats":
            await handle_stats_with_growth()
        elif txt == "/profit":
            await handle_profit_update()
        elif txt == "/reset engine":
            # Reset decision engine state
            await handle_reset_decision_engine()
        elif txt == "/help":
            await handle_help_command()
        else:
            # Check if this is a decision engine confirmation response
            if txt in ["yes", "no"] and state.decision_engine.analysis_data.state.value == "awaiting_confirmation":
                response_info = await state.decision_engine.handle_confirmation_response(txt)
                
                if response_info["executed"]:
                    # Parameters were confirmed - the decision engine will trigger trading resumption automatically
                    # Don't need to manually trigger here as _trigger_trading_resumption() handles it
                    pass
                elif response_info["message"]:
                    await send_and_track_message(bot, f"ℹ️ {response_info['message']}")
                    
                return
            
            await send_and_track_message(bot, f"Unknown command: <code>{txt}</code>. Try sending 'start 001'.")

    except Exception as e:
        logger.error(f"Error in command router for '{txt}': {e}\n{traceback.format_exc()}")
        await send_and_track_message(bot, "An error occurred while processing your command. Please check the logs.")

async def handle_input_flow(txt: str):
    """Manages the conversation flow for setting up trading parameters."""
    global state, bot, message_queue
    current_step = state.awaiting_input
    
    try:
        if current_step == "use_saved":
            if txt == "yes":
                state.params = state.saved_params.copy()
                # Reset stats for the new session
                state.load_stats(reset=True)
                state.trading_enabled = True
                await send_and_track_message(bot, "Starting trading with saved parameters...")
                await state.start_new_trade()
                state.awaiting_input = None
            else:
                state.awaiting_input = "stake"
                await send_and_track_message(bot, "Enter stake amount (minimum <code>0.4</code>):")
            # Delete the saved params prompt message if it exists
            if hasattr(state, "last_saved_params_prompt_id") and state.last_saved_params_prompt_id:
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=state.last_saved_params_prompt_id)
                except Exception as e:
                    logger.error(f"Failed to delete saved params prompt: {e}")
                state.last_saved_params_prompt_id = None
        
        elif current_step == "stake":
            stake = float(txt)
            if stake < config.MINIMUM_STAKE:
                raise ValueError(f"Stake must be at least {config.MINIMUM_STAKE}.")
            state.params["stake"] = stake
            # Delete the stake prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete stake prompt message: {e}")
            state.awaiting_input = "growth_rate"
            await send_and_track_message(bot, "Enter growth rate - <b>MUST BE</b> <code>1</code>, <code>2</code>, <code>3</code>, <code>4</code>, or <code>5</code> (for 1%, 2%, 3%, 4%, or 5%):")
            
        elif current_step == "growth_rate":
            growth_rate = float(txt)
            # Validate growth rate against Deriv API requirements
            valid_rates = [1.0, 2.0, 3.0, 4.0, 5.0]
            if growth_rate not in valid_rates:
                valid_rates_str = ", ".join([f"{rate:.0f}%" for rate in valid_rates])
                raise ValueError(f"❌ Invalid growth rate. Deriv API only accepts: {valid_rates_str}")
            
            state.params["growth_rate"] = growth_rate
            # Delete the growth rate prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete growth rate prompt message: {e}")
            state.awaiting_input = "take_profit"
            await send_and_track_message(bot, "Enter take-profit percentage (e.g., <code>15</code> for 15%):")
            
        elif current_step == "take_profit":
            state.params["take_profit"] = float(txt)
            # Delete the take profit prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete take profit prompt message: {e}")
            state.awaiting_input = "index"
            indices_list = "\n".join([f"• <code>{idx}</code>" for idx in sorted(config.VALID_INDICES)])
            await send_and_track_message(bot, f"📊 <b>Available Indices</b>\n\n{indices_list}\n\nPlease enter your choice:")
            
        elif current_step == "index":
            if txt.upper() not in config.VALID_INDICES:
                indices_list = "\n".join([f"• <code>{idx}</code>" for idx in sorted(config.VALID_INDICES)])
                raise ValueError(f"❌ Invalid index. Please choose from:\n\n{indices_list}")
            state.params["index"] = txt.upper()
            # Delete the index prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete index prompt message: {e}")
            state.awaiting_input = "currency"
            currencies_list = "\n".join([f"• <code>{curr}</code>" for curr in sorted(config.CURRENCY_API_TOKENS.keys())])
            await send_and_track_message(bot, f"💰 <b>Available Currencies</b>\n\n{currencies_list}\n\nPlease enter your choice:")
            
        elif current_step == "currency":
            if txt.upper() not in config.CURRENCY_API_TOKENS:
                currencies_list = "\n".join([f"• <code>{curr}</code>" for curr in sorted(config.CURRENCY_API_TOKENS.keys())])
                raise ValueError(f"❌ Invalid currency. Please choose from:\n\n{currencies_list}")
            state.params["currency"] = txt.upper()
            # Delete the currency prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete currency prompt message: {e}")
            state.awaiting_input = "max_loss"
            await send_and_track_message(bot, "Enter maximum loss amount (e.g., <code>100</code>):")
            
        elif current_step == "max_loss":
            state.max_loss_amount = float(txt)
            # Delete the max loss prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete max loss prompt message: {e}")
            state.awaiting_input = "max_win"
            await send_and_track_message(bot, "Enter maximum win amount (e.g., <code>200</code>):")
            
        elif current_step == "max_win":
            state.max_win_amount = float(txt)
            # Delete the max win prompt message after processing the input
            if message_queue:
                last_msg_id = message_queue[-1][0]
                try:
                    await bot.delete_message(chat_id=config.GROUP_ID, message_id=last_msg_id)
                    message_queue.pop()
                except Exception as e:
                    logger.error(f"Failed to delete max win prompt message: {e}")
            state.awaiting_input = None
            state.save_params()
            state.load_stats(reset=True) # Reset stats for the new session
            state.trading_enabled = True
            await send_and_track_message(bot, "Parameters set! Starting first trade...")
            await state.start_new_trade()

        elif current_step == "confirm_reset":
            if txt.lower() == "confirm reset":
                # Perform engine reset
                try:
                    logger.info("Performing decision engine reset")
                    
                    # Reset the decision engine
                    state.decision_engine.reset_engine()
                    
                    # Also reset consecutive wins for a fresh start
                    state.consecutive_wins = 0
                    
                    # Save the reset state
                    state.save_stats()
                    
                    await send_and_track_message(
                        bot,
                        f"✅ <b>ENGINE RESET COMPLETED</b>\n\n"
                        f"🔄 Decision engine reset to continuous mode\n"
                        f"🧹 All recovery failures cleared\n"
                        f"🎯 Consecutive wins reset to 0\n"
                        f"📊 Trading parameters and stats preserved\n\n"
                        f"🎮 Bot is ready for trading with fresh engine state!"
                    )
                    
                    logger.info("Decision engine reset completed successfully")
                    
                except Exception as e:
                    logger.error(f"Error during engine reset: {e}")
                    await send_and_track_message(bot, f"❌ Error during engine reset: {str(e)}")
            else:
                await send_and_track_message(bot, "❌ Engine reset cancelled. Type 'reset engine' again if needed.")
            
            state.awaiting_input = None

        elif current_step == "confirm_force":
            if txt.lower() == "confirm force":
                # Perform forced confirmation
                try:
                    logger.info("Performing forced confirmation of pending parameters")
                    
                    # Force confirmation with the decision engine
                    await state.decision_engine._execute_confirmation(True, auto_confirmed=False)
                    
                    await send_and_track_message(
                        bot,
                        f"✅ <b>FORCED CONFIRMATION COMPLETED</b>\n\n"
                        f"🔄 Parameters have been applied\n"
                        f"🚨 Mode should switch to recovery if applicable\n"
                        f"🎮 Trading will resume with new parameters\n\n"
                        f"⏭️ <b>Next: Engine will apply parameters on next trade</b>"
                    )
                    
                    logger.info("Forced confirmation completed successfully")
                    
                except Exception as e:
                    logger.error(f"Error during forced confirmation: {e}")
                    await send_and_track_message(bot, f"❌ Error during forced confirmation: {str(e)}")
            else:
                await send_and_track_message(bot, "❌ Force confirmation cancelled. Type 'force confirm' again if needed.")
            
            state.awaiting_input = None

        elif current_step == "confirm_restart":
            if txt.lower() == "restart engine":
                # Perform engine restart
                try:
                    logger.info("Performing engine restart to force recovery mode")
                    
                    # Get current balance for recovery trigger
                    balance_data = await state.api.fetch_balance()
                    current_balance = balance_data.get("balance", 0.0) if balance_data else 0.0
                    
                    # Reset the decision engine first
                    state.decision_engine.reset_engine()
                    
                    # Force trigger recovery analysis if max loss reached
                    if state.max_loss_amount > 0 and state.cumulative_loss >= state.max_loss_amount:
                        await state.decision_engine.trigger_drawdown_analysis(
                            current_balance=current_balance,
                            max_drawdown=state.max_loss_amount,
                            trading_pair=state.params.get("index", "R_10"),
                            trade_history=state.trade_history
                        )
                        
                        await send_and_track_message(
                            bot,
                            f"🔄 <b>ENGINE RESTART COMPLETED</b>\n\n"
                            f"✅ Engine reset and recovery mode triggered\n"
                            f"📉 Max loss detected: <code>{state.cumulative_loss:.2f}</code> / <code>{state.max_loss_amount:.2f} XRP</code>\n"
                            f"🧠 Recovery analysis started\n\n"
                            f"⏳ <b>Wait for recovery confirmation or reply 'yes'</b>"
                        )
                    else:
                        await send_and_track_message(
                            bot,
                            f"✅ <b>ENGINE RESTART COMPLETED</b>\n\n"
                            f"🔄 Decision engine reset successfully\n"
                            f"📊 Trading can resume normally\n\n"
                            f"🎮 Bot is ready for trading with fresh engine state!"
                        )
                    
                    logger.info("Engine restart completed successfully")
                    
                except Exception as e:
                    logger.error(f"Error during engine restart: {e}")
                    await send_and_track_message(bot, f"❌ Error during engine restart: {str(e)}")
            else:
                await send_and_track_message(bot, "❌ Engine restart cancelled. Type 'restart engine' again if needed.")
            
            state.awaiting_input = None

    except ValueError as e:
        await send_and_track_message(bot, f"Invalid input: {e}. Please try again.")
    except Exception as e:
        logger.error(f"Error in input flow at step {current_step}: {e}")
        await send_and_track_message(bot, "An error occurred. Please start over.")
        state.awaiting_input = None

async def handle_status_command():
    """Sends a detailed, visually impressive status message."""
    uptime = datetime.now() - state._start_time
    balance_data = await state.api.fetch_balance()
    balance = balance_data.get('balance', 0.0) if balance_data else 0.0
    currency = balance_data.get('currency', 'N/A') if balance_data else ''
    # Progress bars
    win_bar = make_progress_bar(state.cumulative_win, state.max_win_amount or 1, color_emoji='🟢')
    loss_bar = make_progress_bar(state.cumulative_loss, state.max_loss_amount or 1, color_emoji='🔴')
    # Net P/L progress as growth vs initial balance
    growth_pct = (state.stats['net_pl'] / state.initial_balance * 100) if state.initial_balance else 0
    pl_bar = make_progress_bar(state.stats['net_pl'], state.initial_balance or 1, color_emoji='💸' if state.stats['net_pl'] >= 0 else '📉')
    pl_bar = f"{pl_bar} <b>{growth_pct:+.2f}%</b>"
    # Recent fixes (load from version.json)
    fixes_list = utils.get_recent_fixes()
    fixes = '\n'.join(f"• {fix}" for fix in fixes_list) if fixes_list else 'No recent fixes.'
    # Quote
    quote = random.choice(TRADING_QUOTES)
    # Animated status (rotating dots)
    dots = random.choice(['', '.', '..', '...'])
    status_text = (
        f"<b>🤖 Decter 001 Status Panel</b>\n"
        f"<b>Version:</b> <code>{BOT_VERSION:.1f}</code>\n"
        f"<b>Uptime:</b> <code>{str(uptime).split('.')[0]}</code>\n"
        f"<b>Trading:</b> {'✅ Active' if state.trading_enabled else '❌ Inactive'}\n"
        f"<b>Balance:</b> <code>{balance:.4f} {currency}</code>\n"
        f"<b>Initial Balance:</b> <code>{state.initial_balance:.2f}</code>\n"
        f"<b>Net P/L:</b> <code>{state.stats['net_pl']:+.2f} {currency}</code>\n"
        f"<b>Growth:</b> <code>{state.stats['growth']:+.2f}%</code>\n"
        f"<b>Total Trades:</b> <code>{state.stats['total_trades']}</code> | <b>Wins:</b> <code>{state.stats['wins']}</code> | <b>Losses:</b> <code>{state.stats['losses']}</code>\n"
        f"\n<b>Session Win Progress</b>\n{win_bar}\n"
        f"<b>Session Loss Progress</b>\n{loss_bar}\n"
        f"<b>Net P/L Progress</b>\n{pl_bar}\n"
        f"\n<b>Recent Fixes & Updates</b>\n{fixes}\n"
        f"\n<pre>Decter 001\n{quote} {dots}</pre>"
    )
    await send_and_track_message(bot, status_text)

async def handle_history_command():
    """Sends a concise, professional trade history summary."""
    # Load full trade history from persistent storage
    with open(config.TRADING_STATS_FILE, 'r', encoding='utf-8') as f:
        stats_data = json.load(f)
    all_records = stats_data.get('trade_history', [])
    records = all_records[-10:]  # Last 10 trades

    if not records:
        await send_and_track_message(bot, "No trade history available.")
        return
    header = f"<b>📜 Trade History (Last {len(records)})</b>\n"
    table = "<pre>ID      Sym   Stake   P/L    Result   Time\n" + "-"*48 + "\n"
    for r in records:
        cid = str(r.get('contract_id', ''))[-5:]
        sym = r.get('symbol', '')[:6].ljust(6)
        stake = f"{r.get('stake', 0):.2f}".rjust(6)
        pl = f"{r.get('profit_loss', 0):+.2f}".rjust(7)
        res = '✅' if r.get('win', False) else '❌'
        t = r.get('timestamp', '')[-5:]
        table += f"{cid}  {sym} {stake} {pl}   {res}   {t}\n"
    table += "</pre>"
    stats = state.stats
    summary = (
        f"<b>Total Trades:</b> <code>{stats['total_trades']}</code> | "
        f"<b>Wins:</b> <code>{stats['wins']}</code> | "
        f"<b>Losses:</b> <code>{stats['losses']}</code>\n"
        f"<b>Net P/L:</b> <code>{stats['net_pl']:+.2f}</code> | "
        f"<b>Growth:</b> <code>{stats['growth']:+.2f}%</code>\n"
    )
    footer = "<i>History is not a guarantee of future results.</i>"
    await send_and_track_message(bot, header + table + summary + footer)

async def handle_export_command():
    """Exports comprehensive trade history to CSV and PDF with dual-mode analysis."""
    await send_and_track_message(bot, "📊 Generating comprehensive trading report...")
    records = state.trade_history
    if not records:
        await send_and_track_message(bot, "No trade records to export.")
        return

    # Enhance trade records with trading mode information
    enhanced_records = []
    for record in records:
        enhanced_record = record.copy()
        # Add trading mode to each record if not present
        if 'trading_mode' not in enhanced_record:
            enhanced_record['trading_mode'] = 'continuous'  # Default to continuous for historical records
        
        # Add additional calculated fields
        enhanced_record['win_percentage'] = 100 if enhanced_record.get('win', False) else 0
        enhanced_record['risk_percentage'] = (enhanced_record.get('stake', 0) / state.initial_balance * 100) if state.initial_balance > 0 else 0
        
        enhanced_records.append(enhanced_record)

    # Generate enhanced CSV with more columns
    csv_path = config.DATA_DIR / "trading_history_detailed.csv"
    
    # Define comprehensive CSV headers
    csv_headers = [
        'timestamp', 'contract_id', 'symbol', 'stake', 'profit_loss', 'win', 
        'balance', 'trading_mode', 'win_percentage', 'risk_percentage',
        'cumulative_pl', 'growth_percentage'
    ]
    
    # Calculate cumulative data for CSV
    cumulative_pl = 0
    for i, record in enumerate(enhanced_records):
        cumulative_pl += record.get('profit_loss', 0)
        enhanced_records[i]['cumulative_pl'] = cumulative_pl
        enhanced_records[i]['growth_percentage'] = (cumulative_pl / state.initial_balance * 100) if state.initial_balance > 0 else 0
    
    with csv_path.open("w", newline="", encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(enhanced_records)

    # Gather comprehensive data for PDF export
    try:
        # Get current balance
        balance_data = await state.api.fetch_balance()
        current_balance = balance_data.get("balance", 0.0) if balance_data else 0.0
        
        # Enhanced summary data
        summary = [
            ["Report Date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ["Total Trades", state.stats['total_trades']],
            ["Wins", state.stats['wins']],
            ["Losses", state.stats['losses']],
            ["Net Profit/Loss", f"{state.stats['net_pl']:+.2f} XRP"],
            ["Growth Percentage", f"{state.stats['growth']:+.2f}%"],
            ["Initial Balance", f"{state.initial_balance:.2f} XRP"],
            ["Current Balance", f"{current_balance:.2f} XRP"],
            ["Total Risk Taken", f"{sum(r.get('stake', 0) for r in records):.2f} XRP"],
        ]
        
        # Mode data
        mode_data = {
            'current_mode': state.decision_engine.get_current_mode().value,
            'consecutive_wins': state.consecutive_wins,
            'daily_profit_target': state.decision_engine.analysis_data.daily_profit_target,
            'session_start_balance': state.session_start_balance or state.initial_balance,
        }
        
        # Decision engine data
        engine_data = {
            'state': state.decision_engine.analysis_data.state.value,
            'recovery_failures': state.decision_engine.analysis_data.recovery_failures,
            'recovery_risk_reduction': state.decision_engine.analysis_data.recovery_risk_reduction,
            'total_switches': getattr(state.decision_engine.analysis_data, 'total_switches', 0),
        }
        
        # Add volatility data if available
        if state.decision_engine.analysis_data.volatility_data:
            vol_data = state.decision_engine.analysis_data.volatility_data
            engine_data['volatility_data'] = {
                'timestamp': vol_data.timestamp.isoformat(),
                'symbol': vol_data.symbol,
                'volatility_percentage': vol_data.volatility_percentage,
                'volatility_score': vol_data.volatility_score,
                'data_points': vol_data.data_points,
            }
        
        # Add proposed parameters if available
        if state.decision_engine.analysis_data.proposed_params:
            params = state.decision_engine.analysis_data.proposed_params
            engine_data['proposed_params'] = {
                'stake': params.stake,
                'take_profit': params.take_profit,
                'growth_rate': params.growth_rate,
                'frequency': params.frequency,
                'account_percentage': params.account_percentage,
                'trading_mode': params.trading_mode.value,
            }
            
            # Add recovery forecast if available
            if params.recovery_forecast:
                engine_data['proposed_params']['recovery_forecast'] = {
                    'loss_to_recover': params.recovery_forecast.loss_to_recover,
                    'estimated_trades_min': params.recovery_forecast.estimated_trades_min,
                    'estimated_trades_max': params.recovery_forecast.estimated_trades_max,
                    'recovery_probability': params.recovery_forecast.recovery_probability,
                    'required_win_rate': params.recovery_forecast.required_win_rate,
                    'risk_assessment': params.recovery_forecast.risk_assessment,
                }
        
        # Generate comprehensive PDF
        pdf_path = config.DATA_DIR / "trading_history_comprehensive.pdf"
        utils.export_trade_history_pdf(enhanced_records, summary, pdf_path, engine_data, mode_data)
        
    except Exception as e:
        logger.error(f"Error gathering comprehensive export data: {e}")
        # Fallback to basic export
        pdf_path = config.DATA_DIR / "trading_history_basic.pdf"
        summary = [
            ["Total Trades", state.stats['total_trades']],
            ["Net Profit/Loss", f"{state.stats['net_pl']:+.2f} XRP"]
        ]
        utils.export_trade_history_pdf(enhanced_records, summary, pdf_path)
    
    # Send files as documents and track for deletion
    files_to_send = [
        (csv_path, "📈 Detailed Trade History (CSV)"),
        (pdf_path, "📊 Comprehensive Trading Report (PDF)")
    ]
    
    for path, caption in files_to_send:
        if path.exists():
            with path.open("rb") as doc_file:
                try:
                    msg = await bot.send_document(
                        chat_id=config.GROUP_ID,
                        document=doc_file,
                        caption=caption,
                        message_thread_id=config.TOPIC_ID
                    )
                    if msg:
                        message_queue.append((msg.message_id, datetime.now(), True))
                except Exception as e:
                    logger.error(f"Error sending document {path}: {e}")
    
    # Clean up local files
    try:
        if csv_path.exists():
            os.remove(csv_path)
        if pdf_path.exists():
            os.remove(pdf_path)
    except Exception as e:
        logger.error(f"Error cleaning up export files: {e}")
    
    await send_and_track_message(bot, "✅ Comprehensive trading report generated and sent!")

async def handle_engine_status_command():
    """Sends detailed decision engine status."""
    try:
        engine = state.decision_engine
        analysis_data = engine.analysis_data
        
        status_text = (
            f"🧠 <b>Refined Decision Engine Status</b>\n\n"
            f"📊 <b>Engine State</b>\n"
            f"└ Status: <code>{analysis_data.state.value}</code>\n"
            f"└ Active: <code>{'Yes' if engine.is_active() else 'No'}</code>\n\n"
        )
        
        if analysis_data.volatility_data:
            vol = analysis_data.volatility_data
            status_text += (
                f"📈 <b>Volatility Analysis</b>\n"
                f"└ Symbol: <code>{vol.symbol}</code>\n"
                f"└ Volatility: <code>{vol.volatility_percentage:.1f}%</code>\n"
                f"└ Score: <code>{vol.volatility_score:.0f}/100</code>\n"
                f"└ Data Points: <code>{vol.data_points}</code>\n\n"
            )
        
        if analysis_data.proposed_params:
            params = analysis_data.proposed_params
            status_text += (
                f"🎯 <b>Proposed Parameters</b>\n"
                f"└ Stake: <code>{params.stake:.2f} XRP</code> ({params.account_percentage:.1f}%)\n"
                f"└ Take Profit: <code>{params.take_profit:.0f}%</code>\n"
                f"└ Growth Rate: <code>{params.growth_rate:.1f}%</code>\n"
                f"└ Frequency: <code>{params.frequency.upper()}</code>\n\n"
            )
            
            if analysis_data.countdown_seconds > 0:
                status_text += f"⏰ <b>Confirmation Timeout:</b> <code>{analysis_data.countdown_seconds}s</code>\n"
        
        if analysis_data.current_step:
            status_text += f"🔧 <b>Current Step:</b> <code>{analysis_data.current_step}</code>\n"
        
        await send_and_track_message(bot, status_text)
        
    except Exception as e:
        logger.error(f"Error in engine status command: {e}")
        await send_and_track_message(bot, "Error retrieving engine status.")

async def handle_resume_halt_command():
    """Resume from emergency halt - not used in refined engine."""
    await send_and_track_message(bot, "ℹ️ The refined decision engine doesn't use emergency halts. Use 'start trading' to resume trading.")

async def handle_bot_thinking_command():
    """Display the current bot thinking status in JSON format."""
    try:
        status_json = state.decision_engine.get_status_json()
        await send_and_track_message(bot, f"<pre>{status_json}</pre>")
    except Exception as e:
        logger.error(f"Error in bot thinking command: {e}")
        await send_and_track_message(bot, "Error retrieving bot thinking status.")

async def handle_fetch_manual_command():
    """Generate and send the bot manual as a PDF."""
    try:
        await send_and_track_message(bot, "📖 Generating Bot Manual PDF...")
        
        # Read the BOT_MANUAL.md file
        manual_path = Path("BOT_MANUAL.md")
        if not manual_path.exists():
            await send_and_track_message(bot, "❌ Bot manual file not found.")
            return
        
        with manual_path.open("r", encoding="utf-8") as f:
            manual_content = f.read()
        
        # Generate PDF from markdown content
        pdf_path = config.DATA_DIR / "bot_manual.pdf"
        await generate_manual_pdf(manual_content, pdf_path)
        
        # Send the PDF as a document
        try:
            with pdf_path.open("rb") as pdf_file:
                msg = await bot.send_document(
                    chat_id=config.GROUP_ID,
                    document=pdf_file,
                    caption="📖 Decter 001 Bot Manual - Complete User Guide",
                    filename="Decter_001_Bot_Manual.pdf",
                    message_thread_id=config.TOPIC_ID
                )
                if msg:
                    message_queue.append((msg.message_id, datetime.now(), True))
                    
            await send_and_track_message(bot, "✅ Bot manual sent successfully!")
            
        except Exception as e:
            logger.error(f"Error sending manual PDF: {e}")
            await send_and_track_message(bot, "❌ Failed to send manual PDF.")
        
        # Clean up the temporary PDF file
        try:
            pdf_path.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up manual PDF: {e}")
            
    except Exception as e:
        logger.error(f"Error in fetch manual command: {e}")
        await send_and_track_message(bot, "❌ Error generating bot manual.")

async def handle_mode_status_command():
    """Display current trading mode and status."""
    try:
        current_mode = state.decision_engine.get_current_mode().value
        consecutive_wins = state.consecutive_wins
        
        # Get balance info
        balance_data = await state.api.fetch_balance()
        current_balance = balance_data.get("balance", 0.0) if balance_data else 0.0
        session_start = state.session_start_balance or state.initial_balance
        
        daily_profit_pct = ((current_balance - session_start) / session_start * 100) if session_start > 0 else 0.0
        
        status_text = (
            f"🎯 <b>Trading Mode Status</b>\n\n"
            f"📊 <b>Current Mode:</b> <code>{current_mode.upper()}</code>\n"
            f"🏆 <b>Consecutive Wins:</b> <code>{consecutive_wins}</code>\n"
            f"💰 <b>Current Balance:</b> <code>{current_balance:.2f} XRP</code>\n"
            f"📈 <b>Daily Profit:</b> <code>{daily_profit_pct:+.2f}%</code>\n"
            f"🎮 <b>Trading Enabled:</b> <code>{'Yes' if state.trading_enabled else 'No'}</code>\n\n"
        )
        
        if current_mode == "recovery":
            analysis_data = state.decision_engine.analysis_data
            status_text += (
                f"🚨 <b>Recovery Mode Details:</b>\n"
                f"└ Recovery Failures: <code>{analysis_data.recovery_failures}</code>\n"
                f"└ Risk Reduction: <code>{(1-analysis_data.recovery_risk_reduction)*100:.1f}%</code>\n"
                f"└ Current Risk Factor: <code>{analysis_data.recovery_risk_reduction:.2f}</code>\n"
            )
            
            if analysis_data.proposed_params and analysis_data.proposed_params.recovery_forecast:
                forecast = analysis_data.proposed_params.recovery_forecast
                status_text += (
                    f"└ Loss to Recover: <code>{forecast.loss_to_recover:.2f} XRP</code>\n"
                    f"└ Estimated Trades: <code>{forecast.estimated_trades_min}-{forecast.estimated_trades_max}</code>\n"
                    f"└ Success Probability: <code>{forecast.recovery_probability*100:.1f}%</code>\n"
                    f"└ Risk Level: <code>{forecast.risk_assessment}</code>\n"
                )
        else:
            daily_target = state.decision_engine.analysis_data.daily_profit_target
            if daily_target > 0:
                final_target = daily_target + config.ADDITIONAL_PROFIT_BUFFER
                status_text += (
                    f"🎯 <b>Continuous Mode Targets:</b>\n"
                    f"└ Daily Target: <code>{daily_target:.1f}%</code>\n"
                    f"└ Final Stop Target: <code>{final_target:.1f}%</code>\n"
                    f"└ Risk Reduction at: <code>{config.CONSECUTIVE_WIN_THRESHOLD} wins</code>\n"
                )
        
        await send_and_track_message(bot, status_text)
        
    except Exception as e:
        logger.error(f"Error in mode status command: {e}")
        await send_and_track_message(bot, "❌ Error retrieving mode status.")

async def handle_force_continuous_command():
    """Force switch to continuous mode."""
    try:
        current_mode = state.decision_engine.get_current_mode().value
        
        if current_mode == "continuous":
            await send_and_track_message(bot, "ℹ️ Already in continuous mode.")
            return
        
        # Force switch to continuous mode
        state.decision_engine.switch_to_continuous_mode("Manually forced to continuous mode")
        state.consecutive_wins = 0  # Reset consecutive wins
        
        await send_and_track_message(
            bot,
            f"🔄 <b>MODE SWITCH COMPLETED</b>\n\n"
            f"✅ Switched from <code>{current_mode.upper()}</code> to <code>CONTINUOUS</code>\n"
            f"🎯 Trading will now use continuous mode logic\n"
            f"📉 Risk reduction will apply after 10 consecutive wins\n"
            f"🎪 Daily profit targets will be set automatically"
        )
        
    except Exception as e:
        logger.error(f"Error in force continuous command: {e}")
        await send_and_track_message(bot, "❌ Error switching to continuous mode.")

async def handle_debug_limits_command():
    """Debug trading limits and decision engine state."""
    try:
        # Get current balance
        balance_data = await state.api.fetch_balance()
        current_balance = balance_data.get("balance", 0.0) if balance_data else 0.0
        
        # Get decision engine state
        engine = state.decision_engine
        analysis_data = engine.analysis_data
        current_mode = engine.get_current_mode().value
        
        debug_text = (
            f"🔍 <b>TRADING LIMITS DEBUG</b>\n\n"
            f"💰 <b>Balance Information:</b>\n"
            f"└ Current Balance: <code>{current_balance:.2f} XRP</code>\n"
            f"└ Initial Balance: <code>{state.initial_balance:.2f} XRP</code>\n\n"
            f"📊 <b>Cumulative Stats:</b>\n"
            f"└ Cumulative Loss: <code>{state.cumulative_loss:.2f} XRP</code>\n"
            f"└ Max Loss Limit: <code>{state.max_loss_amount:.2f} XRP</code>\n"
            f"└ Loss Limit Reached: <code>{'YES' if state.cumulative_loss >= state.max_loss_amount else 'NO'}</code>\n"
            f"└ Cumulative Win: <code>{state.cumulative_win:.2f} XRP</code>\n"
            f"└ Max Win Limit: <code>{state.max_win_amount:.2f} XRP</code>\n"
            f"└ Net P/L: <code>{state.stats.get('net_pl', 0.0):.2f} XRP</code>\n\n"
            f"🎯 <b>Trading State:</b>\n"
            f"└ Trading Enabled: <code>{'YES' if state.trading_enabled else 'NO'}</code>\n"
            f"└ Is Stopping: <code>{'YES' if state.is_stopping else 'NO'}</code>\n"
            f"└ Current Mode: <code>{current_mode.upper()}</code>\n"
            f"└ Consecutive Wins: <code>{state.consecutive_wins}</code>\n\n"
            f"🧠 <b>Decision Engine:</b>\n"
            f"└ Engine Active: <code>{'YES' if engine.is_active() else 'NO'}</code>\n"
            f"└ Engine State: <code>{analysis_data.state.value}</code>\n"
            f"└ Recovery Failures: <code>{analysis_data.recovery_failures}</code>\n"
            f"└ Risk Reduction: <code>{analysis_data.recovery_risk_reduction:.2f}</code>\n"
            f"└ Has Proposed Params: <code>{'YES' if analysis_data.proposed_params else 'NO'}</code>\n"
            f"└ Params Confirmed: <code>{'YES' if analysis_data.params_confirmed else 'NO'}</code>\n\n"
            f"⚙️ <b>Current Parameters:</b>\n"
            f"└ Index: <code>{state.params.get('index', 'Not Set')}</code>\n"
            f"└ Stake: <code>{state.params.get('stake', 0.0):.2f} XRP</code>\n"
            f"└ Growth Rate: <code>{state.params.get('growth_rate', 0.0):.1f}%</code>\n"
            f"└ Take Profit: <code>{state.params.get('take_profit', 0.0):.0f}%</code>\n\n"
            f"💡 <b>Diagnosis:</b>\n"
        )
        
        # Add diagnosis
        if state.cumulative_loss >= state.max_loss_amount and current_mode != "recovery":
            debug_text += f"❌ Max loss reached but not in recovery mode!\n"
        elif current_mode == "recovery" and not engine.is_active() and analysis_data.recovery_failures > 5:
            debug_text += f"⚠️ Stuck in recovery mode with many failures!\n"
        elif state.max_loss_amount <= 0:
            debug_text += f"⚠️ Max loss limit not set!\n"
        else:
            debug_text += f"✅ Trading limits appear to be working normally\n"
        
        await send_and_track_message(bot, debug_text)
        
    except Exception as e:
        logger.error(f"Error in debug limits command: {e}")
        await send_and_track_message(bot, f"❌ Error debugging limits: {str(e)}")

async def handle_reset_engine_command():
    """Reset the decision engine to fix stuck states."""
    try:
        current_mode = state.decision_engine.get_current_mode().value
        engine_active = state.decision_engine.is_active()
        recovery_failures = state.decision_engine.analysis_data.recovery_failures
        
        # Confirm reset
        await send_and_track_message(
            bot,
            f"⚠️ <b>ENGINE RESET CONFIRMATION</b>\n\n"
            f"Current State:\n"
            f"└ Mode: <code>{current_mode.upper()}</code>\n"
            f"└ Engine Active: <code>{'YES' if engine_active else 'NO'}</code>\n"
            f"└ Recovery Failures: <code>{recovery_failures}</code>\n\n"
            f"This will:\n"
            f"• Reset engine to continuous mode\n"
            f"• Clear recovery failures\n"
            f"• Reset all engine state\n"
            f"• Keep trading parameters and stats\n\n"
            f"Type 'confirm reset' to proceed"
        )
        
        # Set awaiting input for confirmation
        state.awaiting_input = "confirm_reset"
        
    except Exception as e:
        logger.error(f"Error in reset engine command: {e}")
        await send_and_track_message(bot, f"❌ Error resetting engine: {str(e)}")

async def handle_force_confirm_command():
    """Force confirmation of pending decision engine parameters."""
    try:
        engine_state = state.decision_engine.analysis_data.state.value
        current_mode = state.decision_engine.get_current_mode().value
        
        if engine_state != "awaiting_confirmation":
            await send_and_track_message(
                bot,
                f"ℹ️ <b>NO CONFIRMATION PENDING</b>\n\n"
                f"Engine State: <code>{engine_state}</code>\n"
                f"Current Mode: <code>{current_mode.upper()}</code>\n\n"
                f"There are no parameters waiting for confirmation."
            )
            return
        
        # Show what will be confirmed
        proposed_params = state.decision_engine.analysis_data.proposed_params
        if not proposed_params:
            await send_and_track_message(
                bot,
                f"❌ <b>CONFIRMATION ERROR</b>\n\n"
                f"Engine is awaiting confirmation but no parameters found.\n"
                f"Use 'reset engine' to fix this stuck state."
            )
            return
        
        confirmation_deadline = state.decision_engine.analysis_data.confirmation_deadline
        deadline_str = confirmation_deadline.strftime("%H:%M:%S") if confirmation_deadline else "Unknown"
        
        # Get recovery forecast info if available
        forecast_info = ""
        if (proposed_params.trading_mode.value == "recovery" and 
            proposed_params.recovery_forecast):
            forecast = proposed_params.recovery_forecast
            forecast_info = (
                f"\n📊 <b>Recovery Forecast:</b>\n"
                f"└ Loss to Recover: <code>{forecast.loss_to_recover:.2f} XRP</code>\n"
                f"└ Success Probability: <code>{forecast.recovery_probability*100:.1f}%</code>\n"
                f"└ Risk Assessment: <code>{forecast.risk_assessment}</code>\n"
            )
        
        await send_and_track_message(
            bot,
            f"🔧 <b>FORCE CONFIRMATION</b>\n\n"
            f"⚠️ <b>PENDING PARAMETERS:</b>\n"
            f"└ Index: <code>{state.decision_engine.analysis_data.volatility_data.symbol if state.decision_engine.analysis_data.volatility_data else 'Unknown'}</code>\n"
            f"└ Stake: <code>{proposed_params.stake:.2f} XRP</code>\n"
            f"└ Take Profit: <code>{proposed_params.take_profit:.0f}%</code>\n"
            f"└ Growth Rate: <code>{proposed_params.growth_rate:.1f}%</code>\n"
            f"└ Mode: <code>{proposed_params.trading_mode.value.upper()}</code>\n"
            f"{forecast_info}\n"
            f"🕐 <b>Original Deadline:</b> {deadline_str}\n\n"
            f"Type 'confirm force' to apply these parameters now"
        )
        
        # Set awaiting input for confirmation
        state.awaiting_input = "confirm_force"
        
    except Exception as e:
        logger.error(f"Error in force confirm command: {e}")
        await send_and_track_message(bot, f"❌ Error in force confirm: {str(e)}")

async def handle_restart_engine_command():
    """Force recovery mode when max loss is reached but engine is stuck."""
    try:
        current_mode = state.decision_engine.get_current_mode().value
        engine_active = state.decision_engine.is_active()
        recovery_failures = state.decision_engine.analysis_data.recovery_failures
        
        # Confirm restart
        await send_and_track_message(
            bot,
            f"⚠️ <b>RESTART ENGINE CONFIRMATION</b>\n\n"
            f"Current State:\n"
            f"└ Mode: <code>{current_mode.upper()}</code>\n"
            f"└ Engine Active: <code>{'YES' if engine_active else 'NO'}</code>\n"
            f"└ Recovery Failures: <code>{recovery_failures}</code>\n\n"
            f"This will:\n"
            f"• Force recovery mode\n"
            f"• Reset all engine state\n"
            f"• Keep trading parameters and stats\n\n"
            f"Type 'restart engine' to proceed"
        )
        
        # Set awaiting input for confirmation
        state.awaiting_input = "confirm_restart"
        
    except Exception as e:
        logger.error(f"Error in restart engine command: {e}")
        await send_and_track_message(bot, f"❌ Error restarting engine: {str(e)}")

async def generate_manual_pdf(content: str, output_path: Path):
    """Generate a PDF from markdown content using reportlab with dark theme."""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    
    # Create the PDF document with black background
    doc = SimpleDocTemplate(
        str(output_path), 
        pagesize=A4, 
        topMargin=1*inch, 
        bottomMargin=1*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    styles = getSampleStyleSheet()
    elements = []
    
    # Define dark theme custom styles
    title_style = ParagraphStyle(
        'DarkTitle',
        parent=styles['Heading1'],
        fontSize=26,
        spaceAfter=40,
        spaceBefore=20,
        textColor=colors.white,
        alignment=1,  # Center alignment
        backColor=colors.black,
        borderWidth=2,
        borderColor=colors.red,
        borderPadding=15
    )
    
    heading_style = ParagraphStyle(
        'DarkHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=20,
        spaceBefore=30,
        textColor=colors.lime,
        backColor=colors.black,
        borderWidth=1,
        borderColor=colors.lime,
        borderPadding=10,
        leftIndent=10,
        rightIndent=10
    )
    
    subheading_style = ParagraphStyle(
        'DarkSubheading',
        parent=styles['Heading3'],
        fontSize=15,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.orange,
        backColor=colors.black,
        borderWidth=1,
        borderColor=colors.orange,
        borderPadding=8,
        leftIndent=5,
        rightIndent=5
    )
    
    # Dark paragraph style
    dark_paragraph_style = ParagraphStyle(
        'DarkParagraph',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        spaceBefore=5,
        textColor=colors.white,
        backColor=colors.black,
        leftIndent=15,
        rightIndent=15,
        borderPadding=5
    )
    
    code_style = ParagraphStyle(
        'DarkCode',
        parent=styles['Code'],
        fontSize=10,
        fontName='Courier',
        textColor=colors.cyan,
        backColor=colors.HexColor('#1A1A1A'),
        borderWidth=2,
        borderColor=colors.cyan,
        borderPadding=12,
        leftIndent=25,
        rightIndent=25,
        spaceAfter=15,
        spaceBefore=10
    )
    
    # List item style
    list_style = ParagraphStyle(
        'DarkList',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=5,
        textColor=colors.lightgrey,
        backColor=colors.black,
        leftIndent=30,
        rightIndent=15,
        borderPadding=3
    )
    
    # Process the markdown content
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines but add minimal spacing
        if not line:
            elements.append(Spacer(1, 8))
            i += 1
            continue
        
        # Main title (# )
        if line.startswith('# '):
            title = line[2:].strip()
            # Remove emojis for PDF
            title = re.sub(r'[^\w\s-]', '', title).strip()
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 30))
            
        # Major headings (## )
        elif line.startswith('## '):
            heading = line[3:].strip()
            heading = re.sub(r'[^\w\s-]', '', heading).strip()
            # Add extra space before major headings
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(heading, heading_style))
            elements.append(Spacer(1, 15))
            
        # Sub headings (### )
        elif line.startswith('### '):
            subheading = line[4:].strip()
            subheading = re.sub(r'[^\w\s-]', '', subheading).strip()
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(subheading, subheading_style))
            elements.append(Spacer(1, 10))
            
        # List items (- or *)
        elif line.startswith(('- ', '* ')):
            list_item = line[2:].strip()
            # Clean special characters first
            list_item = re.sub(r'[^\w\s<>/\-\.\(\):\[\],=""\*`]', '', list_item)
            # Process formatting for list items
            list_item = re.sub(r'\*\*(.*?)\*\*', r'<font color="yellow"><b>\1</b></font>', list_item)
            list_item = re.sub(r'\*(.*?)\*', r'<font color="lightblue"><i>\1</i></font>', list_item)
            list_item = re.sub(r'`(.*?)`', r'<font color="cyan" face="Courier">\1</font>', list_item)
            elements.append(Paragraph(f"• {list_item}", list_style))
            
        # Code blocks (```)
        elif line.startswith('```'):
            code_content = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_content.append(lines[i])
                i += 1
            
            if code_content:
                code_text = '\n'.join(code_content)
                # Clean up code for PDF (remove problematic characters)
                code_text = re.sub(r'[^\w\s<>/\-\.\(\):\[\],=""]', ' ', code_text)  # Replace with space instead of removing
                elements.append(Spacer(1, 10))
                elements.append(Paragraph(code_text, code_style))
                elements.append(Spacer(1, 15))
                
        # Regular paragraphs
        else:
            # Process markdown formatting with colors
            text = line
            
            # Clean up special characters FIRST, before adding font tags
            text = re.sub(r'[^\w\s<>/\-\.\(\):\[\],=""\*`]', '', text)
            
            # Enhanced markdown formatting with colors
            text = re.sub(r'\*\*(.*?)\*\*', r'<font color="yellow"><b>\1</b></font>', text)  # Bold - Yellow
            text = re.sub(r'\*(.*?)\*', r'<font color="lightblue"><i>\1</i></font>', text)      # Italic - Light Blue
            text = re.sub(r'`(.*?)`', r'<font color="cyan" face="Courier">\1</font>', text)  # Inline code - Cyan
            
            # Skip lines that are just dashes or equals (markdown formatting)
            if not re.match(r'^[-=]+$', text.strip()) and text.strip() and len(text.strip()) > 1:
                elements.append(Paragraph(text, dark_paragraph_style))
                elements.append(Spacer(1, 8))
        
        i += 1
    
    # Add page break before footer
    elements.append(PageBreak())
    
    # Footer with dark theme
    footer_style = ParagraphStyle(
        'DarkFooter',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.lightgrey,
        backColor=colors.black,
        alignment=1,
        borderWidth=1,
        borderColor=colors.darkgrey,
        borderPadding=10
    )
    
    footer_text = (
        f"<font color='cyan'>Generated:</font> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        f"<font color='lime'>Decter 001 Trading Bot</font> <font color='yellow'>v{BOT_VERSION}</font><br/>"
        f"<font color='orange'>Professional Automated Trading System</font>"
    )
    elements.append(Paragraph(footer_text, footer_style))
    
    # Custom page template with black background
    from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
    from reportlab.platypus.frames import Frame
    from reportlab.pdfgen import canvas
    
    class DarkPageTemplate(PageTemplate):
        def __init__(self, id, frames, pagesize):
            PageTemplate.__init__(self, id, frames, pagesize=pagesize)
            
        def beforeDrawPage(self, canv, doc):
            # Fill the entire page with black
            canv.setFillColor(colors.black)
            canv.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    
    # Create custom document with dark background
    class DarkDocTemplate(BaseDocTemplate):
        def __init__(self, filename, **kwargs):
            BaseDocTemplate.__init__(self, filename, **kwargs)
            frame = Frame(
                self.leftMargin, self.bottomMargin,
                self.width, self.height,
                id='normal'
            )
            template = DarkPageTemplate('dark', [frame], self.pagesize)
            self.addPageTemplates(template)
    
    # Build the dark-themed PDF
    dark_doc = DarkDocTemplate(str(output_path), pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
    dark_doc.build(elements)

async def delete_old_messages():
    """Deletes messages older than MESSAGE_RETENTION_LIMIT minutes."""
    global bot, message_queue
    while True:
        try:
            now = datetime.now()
            messages_to_delete = []
            
            # Check all messages in queue
            for msg_id, timestamp, is_bot_message in message_queue:
                if (now - timestamp).total_seconds() > config.MESSAGE_RETENTION_LIMIT * 60:
                    messages_to_delete.append((msg_id, is_bot_message))
            
            # Delete old messages
            for msg_id, is_bot_message in messages_to_delete:
                try:
                    if is_bot_message:  # Only bot can delete its own messages
                        await bot.delete_message(chat_id=config.GROUP_ID, message_id=msg_id)
                        logger.debug(f"Deleted bot message {msg_id}")
                    # Remove from queue regardless of deletion success
                    message_queue = deque([m for m in message_queue if m[0] != msg_id], maxlen=500)
                except Exception as e:
                    logger.error(f"Failed to delete message {msg_id}: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in message deletion loop: {e}")
            await asyncio.sleep(60)

# Patch send_telegram_message to track sent messages
async def send_and_track_message(bot, text, **kwargs):
    """Sends a message and tracks it for deletion."""
    try:
        msg = await bot.send_message(
            chat_id=kwargs.get('chat_id', config.GROUP_ID),
            message_thread_id=kwargs.get('message_thread_id', config.TOPIC_ID),
            text=text,
            parse_mode=kwargs.get('parse_mode', 'HTML')
        )
        if msg:
            message_queue.append((msg.message_id, datetime.now(), True))
        return msg
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

async def handle_service_messages(update):
    """
    Deletes service messages like 'pinned message' notifications.
    """
    msg = update.get("message")
    if msg and msg.get("pinned_message"):
        try:
            if int(msg["chat"]["id"]) == int(config.GROUP_ID):
                await bot.delete_message(chat_id=config.GROUP_ID, message_id=msg["message_id"])
        except Exception as e:
            logger.error(f"Failed to delete pinned message notification: {e}")

# --- Main Application Logic ---

async def fetch_updates():
    """The main loop to fetch and handle updates from Telegram."""
    global bot, state
    offset = 0
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                update_dict = update.to_dict()
                # Handle service messages first
                await handle_service_messages(update_dict)
                # Then handle commands as usual
                await handle_command(update_dict)
                offset = update.update_id + 1
        except TelegramError as e:
            logger.error(f"Telegram API error while fetching updates: {e}")
            await asyncio.sleep(5) # Avoid rapid-fire errors
        except Exception as e:
            logger.error(f"An unexpected error occurred in the update loop: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(10)

async def shutdown(sig):
    """Graceful shutdown procedure."""
    logger.warning(f"Received signal {sig}. Shutting down...")
    state.trading_enabled = False
    
    if state and state.api:
        await state.api.disconnect()

    # Bump version with empty fix (to be filled on next startup)
    utils.bump_bot_version("")

    # Cancel all other running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Shutdown complete.")
    sys.exit(0)

async def main():
    """Initializes and runs the bot."""
    global bot, state, awaiting_fix_description, fix_prompt_message_id, BOT_VERSION
    # --- Initialization ---
    try:
        # Bump version on every startup
        import utils
        utils.bump_bot_version("")
        # Reload the version for display
        BOT_VERSION = utils.get_bot_version()
        config.validate_env_vars()
        logger.info(f"--- Bot Version {BOT_VERSION} Starting ---")
        
        bot = Bot(token=config.BOT_TOKEN)
        api = DerivAPI()
        
        reset_stats = "--reset" in sys.argv
        state = TradingState(api, bot=bot, reset_stats=reset_stats)

        # Connect to Deriv API
        if not await api.connect():
             logger.critical("Could not connect to Deriv API. Exiting.")
             await send_and_track_message(bot, "Fatal: Could not connect to Deriv API. Bot is shutting down.")
             sys.exit(1)

        # Check if the most recent fix is empty and prompt for it
        recent_fixes = utils.get_recent_fixes()
        if recent_fixes and (recent_fixes[0] == "" or recent_fixes[0].strip() == ""):
            awaiting_fix_description = True
            msg = await send_and_track_message(
                bot,
                "Hey genius, what did you 'fix' this time? Type your fix/feature in one message (make it good, or I'll make something up).",
                chat_id=config.GROUP_ID,
                message_thread_id=config.TOPIC_ID
            )
            if msg:
                fix_prompt_message_id = msg.message_id

        # Send initial connection message
        await send_and_track_message(
            bot,
            "Bot is online and connected.",
            chat_id=config.GROUP_ID,
            message_thread_id=config.TOPIC_ID
        )

        # Start the message deletion task
        asyncio.create_task(delete_old_messages())

        logger.info("Bot initialization complete - ready for trading commands")

    except (EnvironmentError, ValueError) as e:
        logger.critical(f"Initialization failed: {e}")
        sys.exit(1)
        
    # --- Main Loop ---
    await fetch_updates()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
        loop.run_until_complete(shutdown(signal.SIGINT))
    except asyncio.CancelledError:
        logger.info("Main task was cancelled.")
    finally:
        loop.close()

