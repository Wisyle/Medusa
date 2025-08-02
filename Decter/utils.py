import asyncio
import logging
import json
import os
import random
import sys
import csv
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from telegram import Bot
from telegram.error import TelegramError
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# Import configuration constants from your config.py file
import config

# --- Logging Setup ---

# A custom formatter to handle Unicode characters in log messages
class UnicodeFormatter(logging.Formatter):
    """A custom log formatter to clean messages before output."""
    def format(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            # Replace emojis with text descriptions for cleaner logs
            emoji_map = {
                '🎯': '[TARGET]', '💰': '[MONEY]', '📊': '[CHART]', '⚠️': '[WARNING]',
                '❌': '[ERROR]', '✅': '[SUCCESS]', '⏳': '[WAIT]', '📉': '[DOWN]', '📈': '[UP]'
            }
            for emoji, text in emoji_map.items():
                record.msg = record.msg.replace(emoji, text)
        return super().format(record)

def setup_logging() -> logging.Logger:
    """Configures and returns a logger instance."""
    logger = logging.getLogger('TradingBot')
    logger.setLevel(logging.INFO)

    # Prevent adding handlers multiple times if this function is called again
    if logger.hasHandlers():
        return logger

    # Configure logging
    log_formatter = UnicodeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Handler for printing to the console
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)

    # Handler for writing to a file, with UTF-8 encoding
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    
    return logger

# Initialize a global logger instance
logger = setup_logging()

# --- Message Formatting Utilities ---

def fmt_trade(contract_id: str, pnl: float, pre_balance: float, remaining_win: float, remaining_loss: float) -> str:
    """Create a concise trade-closure message with percentage."""
    pnl_pct = (pnl / pre_balance * 100) if pre_balance else 0.0
    emoji = "✅" if pnl >= 0 else "❌"
    return (
        f"{emoji} Trade closed: {contract_id}\n"
        f"PnL: {pnl:+.2f} XRP ({pnl_pct:+.2f}%)\n"
        f"Remaining ➜ Win: {remaining_win:.2f} XRP • Loss: {remaining_loss:.2f} XRP"
    )

def fmt_limit(limit_type: str, cumulative: float, limit_amount: float, initial_balance: float, current_balance: float) -> str:
    """Create a concise limit-reached message with percentage."""
    pct = (cumulative / initial_balance * 100) if initial_balance else 0.0
    return (
        f"⚠️ {limit_type} limit reached!\n"
        f"Cumulative {limit_type}: {cumulative:.2f} XRP ({pct:.2f}%)\n"
        f"Limit: {limit_amount:.2f} XRP\n"
        f"Current Balance: {current_balance:.2f} XRP"
    )

def snark(text: str) -> str:
    """Optionally adds a snarky remark to a given text."""
    if random.random() < 0.3:
        return f"{text.strip()}\n{random.choice(config._SNARKY_REMARKS)}"
    return text.strip()

# --- Telegram Communication ---

async def send_telegram_message(bot: Bot, text: str, **kwargs) -> Optional[Any]:
    """Sends a message to the configured Telegram group and topic."""
    try:
        # Set HTML parse mode by default if not specified
        if 'parse_mode' not in kwargs:
            kwargs['parse_mode'] = 'HTML'
            
        message = await bot.send_message(
            chat_id=config.GROUP_ID,
            text=text,
            message_thread_id=config.TOPIC_ID,
            **kwargs
        )
        return message
    except TelegramError as e:
        logger.error(f"Error sending Telegram message: {e}")
        return None

async def send_telegram_document(bot: Bot, path: Path, caption: str = "") -> None:
    """Sends a document to the configured Telegram group and topic."""
    if not path.exists():
        logger.error(f"Cannot send document: File not found at {path}")
        return
    try:
        with path.open("rb") as doc_file:
            await bot.send_document(
                chat_id=config.GROUP_ID,
                document=doc_file,
                caption=caption,
                message_thread_id=config.TOPIC_ID
            )
    except TelegramError as e:
        logger.error(f"Failed to send Telegram document: {e}")


# --- File I/O and Data Persistence ---

def load_json_file(file_path: Path, default_data: Any = None) -> Any:
    """Loads a JSON file, creating it if it doesn't exist."""
    if not file_path.exists():
        if default_data is not None:
            save_json_file(file_path, default_data)
        return default_data
    try:
        with file_path.open("r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"File {file_path} is corrupted or unreadable ({e}). Re-initializing.")
        if default_data is not None:
            save_json_file(file_path, default_data)
        return default_data

def save_json_file(file_path: Path, data: Any):
    """Saves data to a JSON file atomically."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix('.tmp')
        with tmp_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    except IOError as e:
        logger.error(f"Error saving data to {file_path}: {e}")

# --- Reporting ---

def export_trade_history_pdf(records: List[Dict], summary_data: List, pdf_path: Path, engine_data: Dict = None, mode_data: Dict = None):
    """Generates a comprehensive trading report with dual-mode analysis and decision engine statistics."""
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Decter 001 Trading History Report", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    
    # Enhanced Summary Table
    enhanced_summary = []
    enhanced_summary.extend(summary_data)
    
    # Add mode-specific data if available
    if mode_data:
        enhanced_summary.extend([
            ["Current Trading Mode", mode_data.get('current_mode', 'Unknown').upper()],
            ["Consecutive Wins", str(mode_data.get('consecutive_wins', 0))],
            ["Daily Profit Target", f"{mode_data.get('daily_profit_target', 0):.1f}%"],
            ["Session Start Balance", f"{mode_data.get('session_start_balance', 0):.2f} XRP"],
        ])
    
    # Add engine data if available
    if engine_data:
        enhanced_summary.extend([
            ["Decision Engine State", engine_data.get('state', 'inactive').upper()],
            ["Recovery Failures", str(engine_data.get('recovery_failures', 0))],
            ["Risk Reduction Factor", f"{engine_data.get('recovery_risk_reduction', 1.0):.2f}"],
            ["Engine Switches", str(engine_data.get('total_switches', 0))],
        ])
    
    # Calculate additional statistics
    if records:
        wins = [r for r in records if r.get('win', False)]
        losses = [r for r in records if not r.get('win', False)]
        
        enhanced_summary.extend([
            ["", ""],  # Separator
            ["PERFORMANCE METRICS", ""],
            ["Win Rate", f"{(len(wins)/len(records)*100):.1f}%" if records else "0%"],
            ["Average Win", f"{sum(r.get('profit_loss', 0) for r in wins)/len(wins):.2f} XRP" if wins else "0.00 XRP"],
            ["Average Loss", f"{sum(abs(r.get('profit_loss', 0)) for r in losses)/len(losses):.2f} XRP" if losses else "0.00 XRP"],
            ["Largest Win", f"{max((r.get('profit_loss', 0) for r in wins), default=0):.2f} XRP"],
            ["Largest Loss", f"{min((r.get('profit_loss', 0) for r in records), default=0):.2f} XRP"],
        ])
        
        # Symbol analysis
        symbols = {}
        for r in records:
            symbol = r.get('symbol', 'Unknown')
            if symbol not in symbols:
                symbols[symbol] = {'trades': 0, 'wins': 0, 'total_pl': 0}
            symbols[symbol]['trades'] += 1
            if r.get('win', False):
                symbols[symbol]['wins'] += 1
            symbols[symbol]['total_pl'] += r.get('profit_loss', 0)
        
        enhanced_summary.append(["", ""])  # Separator
        enhanced_summary.append(["SYMBOL ANALYSIS", ""])
        for symbol, data in sorted(symbols.items(), key=lambda x: x[1]['trades'], reverse=True):
            win_rate = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
            enhanced_summary.append([f"{symbol} Performance", f"{data['trades']} trades, {win_rate:.1f}% wins, {data['total_pl']:+.2f} XRP"])

    summary_table = Table(enhanced_summary, colWidths=[2.5 * inch, 2.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    
    # Style section headers
    for i, row in enumerate(enhanced_summary):
        if row[0] in ["PERFORMANCE METRICS", "SYMBOL ANALYSIS"]:
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.darkblue),
                ('TEXTCOLOR', (0, i), (-1, i), colors.white),
                ('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'),
            ]))
        elif row[0] == "" and row[1] == "":  # Separator rows
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.lightgrey),
                ('SPAN', (0, i), (-1, i)),
            ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 24))

    # Decision Engine Analysis (if available)
    if engine_data and engine_data.get('volatility_data'):
        elements.append(Paragraph("Decision Engine Analysis", styles['Heading2']))
        vol_data = engine_data['volatility_data']
        
        engine_analysis = [
            ["Analysis Timestamp", vol_data.get('timestamp', 'Unknown')],
            ["Selected Index", vol_data.get('symbol', 'Unknown')],
            ["Market Volatility", f"{vol_data.get('volatility_percentage', 0):.1f}%"],
            ["Volatility Score", f"{vol_data.get('volatility_score', 0):.0f}/100"],
            ["Data Points Analyzed", str(vol_data.get('data_points', 0))],
        ]
        
        if engine_data.get('proposed_params'):
            params = engine_data['proposed_params']
            engine_analysis.extend([
                ["", ""],  # Separator
                ["PROPOSED PARAMETERS", ""],
                ["Optimized Stake", f"{params.get('stake', 0):.2f} XRP ({params.get('account_percentage', 0):.1f}%)"],
                ["Take Profit Target", f"{params.get('take_profit', 0):.0f}%"],
                ["Growth Rate", f"{params.get('growth_rate', 0):.1f}%"],
                ["Trading Frequency", params.get('frequency', 'Unknown').upper()],
                ["Trading Mode", params.get('trading_mode', 'continuous').upper()],
            ])
            
            if params.get('recovery_forecast'):
                forecast = params['recovery_forecast']
                engine_analysis.extend([
                    ["", ""],  # Separator
                    ["RECOVERY FORECAST", ""],
                    ["Loss to Recover", f"{forecast.get('loss_to_recover', 0):.2f} XRP"],
                    ["Estimated Trades", f"{forecast.get('estimated_trades_min', 0)}-{forecast.get('estimated_trades_max', 0)}"],
                    ["Recovery Probability", f"{forecast.get('recovery_probability', 0)*100:.1f}%"],
                    ["Required Win Rate", f"{forecast.get('required_win_rate', 0)*100:.1f}%"],
                    ["Risk Assessment", forecast.get('risk_assessment', 'Unknown')],
                ])
        
        engine_table = Table(engine_analysis, colWidths=[2.5 * inch, 2.5 * inch])
        engine_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        
        # Style section headers
        for i, row in enumerate(engine_analysis):
            if row[0] in ["PROPOSED PARAMETERS", "RECOVERY FORECAST"]:
                engine_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.darkorange),
                    ('TEXTCOLOR', (0, i), (-1, i), colors.white),
                    ('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'),
                ]))
        
        elements.append(engine_table)
        elements.append(Spacer(1, 24))

    # Trade History Table
    elements.append(Paragraph("Detailed Trade History", styles['Heading2']))
    
    # Enhanced header with more columns
    header = [
        "ID", "Symbol", "Stake", "P/L", "Result", "Mode", "Timestamp", "Balance"
    ]
    trade_data = [header]
    
    for r in records:
        profit = float(r.get('profit_loss', 0))
        is_win = profit > 0
        result_emoji = '✅' if is_win else '❌'
        trading_mode = r.get('trading_mode', 'Unknown')[:4].upper()  # Truncate mode
        
        trade_data.append([
            f"{str(r.get('contract_id', ''))[-6:]}",  # Last 6 chars of ID
            r.get('symbol', ''),
            f"{r.get('stake', 0):.2f}",
            f"{profit:+.2f}",
            result_emoji,
            trading_mode,
            r.get('timestamp', '')[-8:],  # Time only
            f"{r.get('balance', 0):.2f}"
        ])

    # Enhanced table with better column widths
    col_widths = [1.0*inch, 0.8*inch, 0.6*inch, 0.7*inch, 0.5*inch, 0.6*inch, 1.0*inch, 0.8*inch]
    trade_table = Table(trade_data, colWidths=col_widths, hAlign='LEFT')
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    # Alternating row colors and P/L coloring
    for i, row in enumerate(trade_data[1:], start=1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
        else:
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
        
        # P/L color coding
        try:
            pl = float(row[3])
            if pl < 0:
                style.add('TEXTCOLOR', (3, i), (3, i), colors.red)
                style.add('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
            else:
                style.add('TEXTCOLOR', (3, i), (3, i), colors.green)
                style.add('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
        except Exception:
            pass
        
        # Result emoji color
        if row[4] == '✅':
            style.add('TEXTCOLOR', (4, i), (4, i), colors.green)
        else:
            style.add('TEXTCOLOR', (4, i), (4, i), colors.red)
        
        # Mode color coding
        if row[5] == 'RECO':  # Recovery mode
            style.add('TEXTCOLOR', (5, i), (5, i), colors.red)
            style.add('FONTNAME', (5, i), (5, i), 'Helvetica-Bold')
        elif row[5] == 'CONT':  # Continuous mode
            style.add('TEXTCOLOR', (5, i), (5, i), colors.blue)
    
    trade_table.setStyle(style)
    elements.append(trade_table)
    elements.append(Spacer(1, 18))
    
    # Trading Insights
    if records:
        elements.append(Paragraph("Trading Insights", styles['Heading2']))
        
        insights_text = []
        
        # Performance streaks
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        current_is_win = None
        
        for r in reversed(records):  # Start from most recent
            is_win = r.get('win', False)
            if current_is_win is None:
                current_is_win = is_win
                current_streak = 1
            elif current_is_win == is_win:
                current_streak += 1
            else:
                if current_is_win:
                    max_win_streak = max(max_win_streak, current_streak)
                else:
                    max_loss_streak = max(max_loss_streak, current_streak)
                current_is_win = is_win
                current_streak = 1
        
        # Update for the last streak
        if current_is_win:
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)
        
        insights_text.append(f"• Maximum winning streak: {max_win_streak} trades")
        insights_text.append(f"• Maximum losing streak: {max_loss_streak} trades")
        
        # Risk analysis
        total_risk = sum(r.get('stake', 0) for r in records)
        avg_risk_per_trade = total_risk / len(records) if records else 0
        insights_text.append(f"• Average risk per trade: {avg_risk_per_trade:.2f} XRP")
        
        # Time analysis
        if len(records) > 1:
            first_trade = records[0].get('timestamp', '')
            last_trade = records[-1].get('timestamp', '')
            insights_text.append(f"• Trading period: {first_trade[:10]} to {last_trade[:10]}")
        
        for insight in insights_text:
            elements.append(Paragraph(insight, styles['Normal']))
        
        elements.append(Spacer(1, 12))
    
    # Footer with comprehensive export info
    export_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    footer_text = (
        f"<font size=10 color=grey>Report generated: {export_time} | "
        f"Total trades: {len(records)} | "
        f"Decter 001 Trading Bot | "
        f"Dual-Mode Trading System</font>"
    )
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    doc.build(elements)

# --- Versioning ---
def get_git_commit() -> str:
    """Return current short git commit hash or 'unknown' if not available."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

def get_bot_version() -> float:
    """
    Checks the current git commit against the stored version.
    Bumps the version by 0.1 if the commit has changed.
    """
    commit = get_git_commit()
    version_data = load_json_file(config.VERSION_FILE, {"commit": "none", "version": 1.0})
    
    if version_data.get("commit") != commit:
        new_version = round(float(version_data.get("version", 1.0)) + 0.1, 1)
        version_data = {"commit": commit, "version": new_version}
        save_json_file(config.VERSION_FILE, version_data)
        return new_version
        
    return float(version_data.get("version", 1.0))

def bump_bot_version(fix_description: str):
    """
    Bumps the bot version by 0.1 and adds a new fix/feature description to version.json.
    Keeps only the 5 most recent fixes.
    """
    version_data = load_json_file(config.VERSION_FILE, {"commit": "none", "version": 1.0, "recent_fixes": []})
    new_version = round(float(version_data.get("version", 1.0)) + 0.1, 1)
    recent_fixes = version_data.get("recent_fixes", [])
    recent_fixes.insert(0, fix_description)
    recent_fixes = recent_fixes[:5]
    version_data = {
        "commit": get_git_commit(),
        "version": new_version,
        "recent_fixes": recent_fixes
    }
    save_json_file(config.VERSION_FILE, version_data)
    return new_version

def get_recent_fixes():
    """Returns the 5 most recent fixes from version.json."""
    version_data = load_json_file(config.VERSION_FILE, {"recent_fixes": []})
    return version_data.get("recent_fixes", [])