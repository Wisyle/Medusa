"""
Trade History Module for Decter Trading System
Provides comprehensive trade tracking, filtering, and export functionality
"""

import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import tempfile

logger = logging.getLogger(__name__)

class TradeResult(Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"

class ExportFormat(Enum):
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"

@dataclass
class TradeRecord:
    """Individual trade record with comprehensive data"""
    trade_id: str
    timestamp: datetime
    asset_pair: str
    direction: str  # Long/Short
    entry_price: float
    exit_price: float
    stake: float
    pnl: float
    result: TradeResult
    duration_seconds: int
    engine: str  # continuous, decision
    volatility: float
    take_profit: float
    reason: str
    currency: str

@dataclass
class TradeFilter:
    """Filter criteria for trade queries"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    currency: Optional[str] = None
    engine: Optional[str] = None
    result: Optional[TradeResult] = None
    asset_pair: Optional[str] = None
    min_pnl: Optional[float] = None
    max_pnl: Optional[float] = None

@dataclass
class TradeSummary:
    """Summary statistics for filtered trades"""
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    avg_pnl_per_trade: float
    best_trade: float
    worst_trade: float
    avg_duration_minutes: float
    total_volume: float
    sharpe_ratio: float

class TradeHistory:
    """
    Comprehensive trade history management with filtering, export, and analytics
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.trades_file = data_dir / "trade_history.json"
        self.summary_file = data_dir / "trade_summary.json"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("📊 Trade History module initialized")
    
    def add_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new trade record"""
        try:
            # Convert to TradeRecord
            trade_record = TradeRecord(
                trade_id=trade_data.get("trade_id", f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                timestamp=datetime.fromisoformat(trade_data["timestamp"]) if isinstance(trade_data["timestamp"], str) else trade_data["timestamp"],
                asset_pair=trade_data.get("asset_pair", "R_10"),
                direction=trade_data.get("direction", "Long"),
                entry_price=float(trade_data.get("entry_price", 0.0)),
                exit_price=float(trade_data.get("exit_price", 0.0)),
                stake=float(trade_data.get("stake", 0.0)),
                pnl=float(trade_data.get("pnl", 0.0)),
                result=TradeResult(trade_data.get("result", "win")),
                duration_seconds=int(trade_data.get("duration_seconds", 0)),
                engine=trade_data.get("engine", "continuous"),
                volatility=float(trade_data.get("volatility", 0.0)),
                take_profit=float(trade_data.get("take_profit", 0.0)),
                reason=trade_data.get("reason", ""),
                currency=trade_data.get("currency", "XRP")
            )
            
            # Load existing trades
            trades = self._load_trades()
            
            # Add new trade
            trades.append(asdict(trade_record))
            
            # Save updated trades
            self._save_trades(trades)
            
            # Update summary statistics
            self._update_summary_stats()
            
            logger.info(f"📈 Trade added: {trade_record.trade_id} - {trade_record.result.value} - ${trade_record.pnl:.2f}")
            
            return {
                "success": True,
                "message": "Trade added successfully",
                "trade_id": trade_record.trade_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error adding trade: {e}")
            return {
                "success": False,
                "message": f"Error adding trade: {str(e)}"
            }
    
    def get_trades(self, filter_criteria: TradeFilter = None, limit: int = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Get filtered trade records"""
        try:
            trades = self._load_trades()
            
            # Apply filters
            if filter_criteria:
                trades = self._apply_filters(trades, filter_criteria)
            
            # Sort by timestamp (most recent first)
            trades.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Apply pagination
            if limit:
                trades = trades[offset:offset + limit]
            
            return trades
            
        except Exception as e:
            logger.error(f"❌ Error getting trades: {e}")
            return []
    
    def get_summary_stats(self, filter_criteria: TradeFilter = None) -> TradeSummary:
        """Get summary statistics for filtered trades"""
        try:
            trades = self.get_trades(filter_criteria)
            
            if not trades:
                return TradeSummary(
                    total_trades=0, wins=0, losses=0, breakeven=0,
                    win_rate=0.0, profit_factor=0.0, total_pnl=0.0,
                    avg_pnl_per_trade=0.0, best_trade=0.0, worst_trade=0.0,
                    avg_duration_minutes=0.0, total_volume=0.0, sharpe_ratio=0.0
                )
            
            # Calculate statistics
            total_trades = len(trades)
            wins = len([t for t in trades if t["result"] == "win"])
            losses = len([t for t in trades if t["result"] == "loss"])
            breakeven = len([t for t in trades if t["result"] == "breakeven"])
            
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            total_pnl = sum(t["pnl"] for t in trades)
            winning_trades_pnl = sum(t["pnl"] for t in trades if t["pnl"] > 0)
            losing_trades_pnl = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
            
            profit_factor = (winning_trades_pnl / losing_trades_pnl) if losing_trades_pnl > 0 else float('inf')
            
            avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0.0
            best_trade = max((t["pnl"] for t in trades), default=0.0)
            worst_trade = min((t["pnl"] for t in trades), default=0.0)
            
            avg_duration_minutes = sum(t["duration_seconds"] for t in trades) / (total_trades * 60) if total_trades > 0 else 0.0
            total_volume = sum(t["stake"] for t in trades)
            
            # Simple Sharpe ratio calculation (assuming risk-free rate of 0)
            if total_trades > 1:
                pnl_values = [t["pnl"] for t in trades]
                mean_return = sum(pnl_values) / len(pnl_values)
                variance = sum((x - mean_return) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
                std_dev = variance ** 0.5
                sharpe_ratio = mean_return / std_dev if std_dev > 0 else 0.0
            else:
                sharpe_ratio = 0.0
            
            return TradeSummary(
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                breakeven=breakeven,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_pnl=total_pnl,
                avg_pnl_per_trade=avg_pnl_per_trade,
                best_trade=best_trade,
                worst_trade=worst_trade,
                avg_duration_minutes=avg_duration_minutes,
                total_volume=total_volume,
                sharpe_ratio=sharpe_ratio
            )
            
        except Exception as e:
            logger.error(f"❌ Error calculating summary stats: {e}")
            return TradeSummary(
                total_trades=0, wins=0, losses=0, breakeven=0,
                win_rate=0.0, profit_factor=0.0, total_pnl=0.0,
                avg_pnl_per_trade=0.0, best_trade=0.0, worst_trade=0.0,
                avg_duration_minutes=0.0, total_volume=0.0, sharpe_ratio=0.0
            )
    
    def export_trades(self, filter_criteria: TradeFilter = None, export_format: ExportFormat = ExportFormat.CSV) -> Dict[str, Any]:
        """Export filtered trades to specified format"""
        try:
            trades = self.get_trades(filter_criteria)
            
            if not trades:
                return {
                    "success": False,
                    "message": "No trades found for export"
                }
            
            # Create temporary file
            temp_dir = Path(tempfile.gettempdir())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if export_format == ExportFormat.CSV:
                filename = f"decter_trades_{timestamp}.csv"
                filepath = temp_dir / filename
                
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    if trades:
                        fieldnames = trades[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(trades)
                
            elif export_format == ExportFormat.JSON:
                filename = f"decter_trades_{timestamp}.json"
                filepath = temp_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as jsonfile:
                    json.dump(trades, jsonfile, indent=2, default=str)
            
            elif export_format == ExportFormat.PDF:
                filename = f"decter_trades_{timestamp}.pdf"
                filepath = temp_dir / filename
                
                # Create PDF report
                self._create_pdf_report(trades, filepath, filter_criteria)
            
            logger.info(f"📄 Trades exported to {filepath}")
            
            return {
                "success": True,
                "message": f"Trades exported successfully",
                "filename": filename,
                "filepath": str(filepath),
                "record_count": len(trades)
            }
            
        except Exception as e:
            logger.error(f"❌ Error exporting trades: {e}")
            return {
                "success": False,
                "message": f"Error exporting trades: {str(e)}"
            }
    
    def _create_pdf_report(self, trades: List[Dict], filepath: Path, filter_criteria: TradeFilter = None):
        """Create PDF report of trades"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=30)
            story.append(Paragraph("Decter Trading System - Trade Report", title_style))
            
            # Report info
            report_info = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
            report_info += f"Total Records: {len(trades)}<br/>"
            if filter_criteria:
                if filter_criteria.start_date:
                    report_info += f"From: {filter_criteria.start_date.strftime('%Y-%m-%d')}<br/>"
                if filter_criteria.end_date:
                    report_info += f"To: {filter_criteria.end_date.strftime('%Y-%m-%d')}<br/>"
                if filter_criteria.currency:
                    report_info += f"Currency: {filter_criteria.currency}<br/>"
                if filter_criteria.engine:
                    report_info += f"Engine: {filter_criteria.engine}<br/>"
            
            story.append(Paragraph(report_info, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Summary statistics
            summary = self.get_summary_stats(filter_criteria)
            summary_data = [
                ['Metric', 'Value'],
                ['Total Trades', str(summary.total_trades)],
                ['Win Rate', f"{summary.win_rate:.1f}%"],
                ['Total PnL', f"${summary.total_pnl:.2f}"],
                ['Profit Factor', f"{summary.profit_factor:.2f}"],
                ['Best Trade', f"${summary.best_trade:.2f}"],
                ['Worst Trade', f"${summary.worst_trade:.2f}"],
                ['Avg PnL/Trade', f"${summary.avg_pnl_per_trade:.2f}"]
            ]
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(Paragraph("Summary Statistics", styles['Heading2']))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Trade details (first 50 trades to keep PDF manageable)
            if trades:
                story.append(Paragraph("Trade Details (Recent 50)", styles['Heading2']))
                
                trade_data = [['Date', 'Asset', 'Result', 'PnL', 'Engine']]
                for trade in trades[:50]:
                    timestamp = datetime.fromisoformat(trade['timestamp']) if isinstance(trade['timestamp'], str) else trade['timestamp']
                    trade_data.append([
                        timestamp.strftime('%Y-%m-%d %H:%M'),
                        trade['asset_pair'],
                        trade['result'].title(),
                        f"${trade['pnl']:.2f}",
                        trade['engine'].title()
                    ])
                
                trade_table = Table(trade_data)
                trade_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(trade_table)
            
            doc.build(story)
            
        except ImportError:
            logger.warning("⚠️ ReportLab not available, cannot create PDF report")
            raise Exception("PDF generation requires ReportLab library")
        except Exception as e:
            logger.error(f"❌ Error creating PDF report: {e}")
            raise
    
    def _load_trades(self) -> List[Dict[str, Any]]:
        """Load trades from file"""
        try:
            if self.trades_file.exists():
                with open(self.trades_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"❌ Error loading trades: {e}")
            return []
    
    def _save_trades(self, trades: List[Dict[str, Any]]) -> None:
        """Save trades to file"""
        try:
            with open(self.trades_file, 'w') as f:
                json.dump(trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Error saving trades: {e}")
    
    def _apply_filters(self, trades: List[Dict[str, Any]], filter_criteria: TradeFilter) -> List[Dict[str, Any]]:
        """Apply filter criteria to trades"""
        filtered_trades = trades.copy()
        
        if filter_criteria.start_date:
            filtered_trades = [t for t in filtered_trades if 
                             datetime.fromisoformat(t['timestamp']) >= filter_criteria.start_date]
        
        if filter_criteria.end_date:
            filtered_trades = [t for t in filtered_trades if 
                             datetime.fromisoformat(t['timestamp']) <= filter_criteria.end_date]
        
        if filter_criteria.currency:
            filtered_trades = [t for t in filtered_trades if t['currency'] == filter_criteria.currency]
        
        if filter_criteria.engine:
            filtered_trades = [t for t in filtered_trades if t['engine'] == filter_criteria.engine]
        
        if filter_criteria.result:
            filtered_trades = [t for t in filtered_trades if t['result'] == filter_criteria.result.value]
        
        if filter_criteria.asset_pair:
            filtered_trades = [t for t in filtered_trades if t['asset_pair'] == filter_criteria.asset_pair]
        
        if filter_criteria.min_pnl is not None:
            filtered_trades = [t for t in filtered_trades if t['pnl'] >= filter_criteria.min_pnl]
        
        if filter_criteria.max_pnl is not None:
            filtered_trades = [t for t in filtered_trades if t['pnl'] <= filter_criteria.max_pnl]
        
        return filtered_trades
    
    def _update_summary_stats(self) -> None:
        """Update summary statistics cache"""
        try:
            summary = self.get_summary_stats()
            summary_data = {
                "last_updated": datetime.now().isoformat(),
                "summary": asdict(summary)
            }
            
            with open(self.summary_file, 'w') as f:
                json.dump(summary_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error updating summary stats: {e}")
    
    def get_daily_breakdown(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily breakdown of trading performance"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            filter_criteria = TradeFilter(start_date=start_date, end_date=end_date)
            trades = self.get_trades(filter_criteria)
            
            # Group trades by date
            daily_data = {}
            for trade in trades:
                trade_date = datetime.fromisoformat(trade['timestamp']).date()
                date_str = trade_date.isoformat()
                
                if date_str not in daily_data:
                    daily_data[date_str] = {
                        "date": date_str,
                        "trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "pnl": 0.0,
                        "volume": 0.0
                    }
                
                daily_data[date_str]["trades"] += 1
                daily_data[date_str]["pnl"] += trade["pnl"]
                daily_data[date_str]["volume"] += trade["stake"]
                
                if trade["result"] == "win":
                    daily_data[date_str]["wins"] += 1
                elif trade["result"] == "loss":
                    daily_data[date_str]["losses"] += 1
            
            # Convert to list and sort by date
            daily_breakdown = list(daily_data.values())
            daily_breakdown.sort(key=lambda x: x["date"], reverse=True)
            
            return daily_breakdown
            
        except Exception as e:
            logger.error(f"❌ Error getting daily breakdown: {e}")
            return []

# Global instance
trade_history: Optional[TradeHistory] = None

def get_trade_history(data_dir: Path) -> TradeHistory:
    """Get or create trade history instance"""
    global trade_history
    if trade_history is None:
        trade_history = TradeHistory(data_dir)
    return trade_history