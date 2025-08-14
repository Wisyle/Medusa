"""
Database adapter for Decter Engine to use shared PostgreSQL database
Provides fallback to JSON files if database is not available
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    """Adapter to use shared PostgreSQL database or fallback to JSON files"""
    
    def __init__(self):
        self.use_database = False
        self.db_session = None
        
        # Try to import database dependencies
        try:
            import sys
            sys.path.insert(0, '..')  # Add parent directory to path
            from app.database import SessionLocal, engine
            from sqlalchemy import text
            
            # Test database connection
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                self.db_session = SessionLocal
                self.use_database = True
                logger.info("✅ Decter Engine connected to shared PostgreSQL database")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not connect to shared database, using JSON files: {e}")
            self.use_database = False
    
    def save_trading_stats(self, stats: Dict[str, Any]) -> None:
        """Save trading statistics"""
        if self.use_database:
            try:
                self._save_stats_to_db(stats)
            except Exception as e:
                logger.error(f"Database save failed, falling back to JSON: {e}")
                self._save_stats_to_json(stats)
        else:
            self._save_stats_to_json(stats)
    
    def load_trading_stats(self) -> Dict[str, Any]:
        """Load trading statistics"""
        if self.use_database:
            try:
                return self._load_stats_from_db()
            except Exception as e:
                logger.error(f"Database load failed, falling back to JSON: {e}")
                return self._load_stats_from_json()
        else:
            return self._load_stats_from_json()
    
    def _save_stats_to_db(self, stats: Dict[str, Any]) -> None:
        """Save stats to PostgreSQL database"""
        from sqlalchemy import text
        
        with self.db_session() as session:
            # Create decter_stats table if it doesn't exist
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS decter_stats (
                    id SERIAL PRIMARY KEY,
                    stats_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Insert or update stats
            session.execute(text("""
                INSERT INTO decter_stats (stats_data, updated_at) 
                VALUES (:stats, :timestamp)
                ON CONFLICT (id) DO UPDATE SET 
                    stats_data = :stats, 
                    updated_at = :timestamp
            """), {
                "stats": json.dumps(stats),
                "timestamp": datetime.now()
            })
            session.commit()
    
    def _load_stats_from_db(self) -> Dict[str, Any]:
        """Load stats from PostgreSQL database"""
        from sqlalchemy import text
        
        with self.db_session() as session:
            result = session.execute(text("""
                SELECT stats_data FROM decter_stats 
                ORDER BY updated_at DESC LIMIT 1
            """)).fetchone()
            
            if result:
                return json.loads(result[0])
            return {}
    
    def _save_stats_to_json(self, stats: Dict[str, Any]) -> None:
        """Save stats to JSON file (fallback)"""
        from config import TRADING_STATS_FILE
        try:
            with open(TRADING_STATS_FILE, 'w') as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stats to JSON: {e}")
    
    def _load_stats_from_json(self) -> Dict[str, Any]:
        """Load stats from JSON file (fallback)"""
        from config import TRADING_STATS_FILE
        try:
            if TRADING_STATS_FILE.exists():
                with open(TRADING_STATS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load stats from JSON: {e}")
        return {}
    
    def save_trade_record(self, trade: Dict[str, Any]) -> None:
        """Save individual trade record"""
        if self.use_database:
            try:
                self._save_trade_to_db(trade)
            except Exception as e:
                logger.error(f"Database trade save failed: {e}")
        
        # Always save to JSON as backup
        self._save_trade_to_json(trade)
    
    def _save_trade_to_db(self, trade: Dict[str, Any]) -> None:
        """Save trade record to database"""
        from sqlalchemy import text
        
        with self.db_session() as session:
            # Create decter_trades table if it doesn't exist
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS decter_trades (
                    id SERIAL PRIMARY KEY,
                    trade_data JSONB NOT NULL,
                    trade_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result VARCHAR(10),
                    amount DECIMAL(10,2),
                    index_name VARCHAR(20)
                )
            """))
            
            # Insert trade record
            session.execute(text("""
                INSERT INTO decter_trades (trade_data, result, amount, index_name) 
                VALUES (:trade_data, :result, :amount, :index_name)
            """), {
                "trade_data": json.dumps(trade),
                "result": trade.get("result", "unknown"),
                "amount": trade.get("amount", 0),
                "index_name": trade.get("index", "unknown")
            })
            session.commit()
    
    def _save_trade_to_json(self, trade: Dict[str, Any]) -> None:
        """Save trade record to JSON file"""
        from config import TRADE_RECORDS_FILE
        try:
            trades = []
            if TRADE_RECORDS_FILE.exists():
                with open(TRADE_RECORDS_FILE, 'r') as f:
                    trades = json.load(f)
            
            trades.append(trade)
            
            # Keep only last 1000 trades
            if len(trades) > 1000:
                trades = trades[-1000:]
            
            with open(TRADE_RECORDS_FILE, 'w') as f:
                json.dump(trades, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save trade to JSON: {e}")

# Global instance
db_adapter = DatabaseAdapter()