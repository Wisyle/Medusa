#!/usr/bin/env python3

from sqlalchemy.orm import Session
from database import get_db, BotInstance
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class StrategyMonitorAggregator:
    """Aggregates data from all strategy types for unified monitoring"""
    
    def __init__(self):
        self.db = next(get_db())
    
    def get_trading_bots_summary(self) -> Dict[str, Any]:
        """Get aggregated summary of all trading bot instances"""
        try:
            total_instances = self.db.query(BotInstance).count()
            active_instances = self.db.query(BotInstance).filter(BotInstance.is_active == True).count()
            error_instances = self.db.query(BotInstance).filter(BotInstance.last_error.isnot(None)).count()
            
            total_pnl = 0.0
            
            return {
                'total_instances': total_instances,
                'active_instances': active_instances,
                'error_instances': error_instances,
                'total_pnl': total_pnl,
                'last_updated': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting trading bots summary: {e}")
            return {
                'total_instances': 0,
                'active_instances': 0,
                'error_instances': 0,
                'total_pnl': 0.0,
                'last_updated': datetime.utcnow().isoformat()
            }
    
    def get_dex_arbitrage_summary(self) -> Dict[str, Any]:
        """Get aggregated summary of DEX arbitrage operations"""
        try:
            active_arbitrage = 3  # Placeholder: BNB, SOL, USDT pairs
            recent_opportunities = 15  # Placeholder: opportunities in last 24h
            trading_pairs = 3  # BNB, SOL, USDT
            arbitrage_pnl = 125.50  # Placeholder P&L
            
            return {
                'active_arbitrage': active_arbitrage,
                'opportunities': recent_opportunities,
                'trading_pairs': trading_pairs,
                'arbitrage_pnl': arbitrage_pnl,
                'last_updated': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting DEX arbitrage summary: {e}")
            return {
                'active_arbitrage': 0,
                'opportunities': 0,
                'trading_pairs': 0,
                'arbitrage_pnl': 0.0,
                'last_updated': datetime.utcnow().isoformat()
            }
    
    def get_validator_nodes_summary(self) -> Dict[str, Any]:
        """Get aggregated summary of validator nodes"""
        try:
            ton_validators = 1  # TON blockchain validator
            solana_alpha = 1   # Solana Alpha strategy with ILP farming
            ethereum_epsilon = 1  # Ethereum Epsilon validator strategy
            validator_rewards = 89.25  # Placeholder rewards from last 30 days
            
            return {
                'ton_validators': ton_validators,
                'solana_alpha': solana_alpha,
                'ethereum_epsilon': ethereum_epsilon,
                'validator_rewards': validator_rewards,
                'last_updated': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting validator nodes summary: {e}")
            return {
                'ton_validators': 0,
                'solana_alpha': 0,
                'ethereum_epsilon': 0,
                'validator_rewards': 0.0,
                'last_updated': datetime.utcnow().isoformat()
            }
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get overall system health and statistics"""
        try:
            system_health = "healthy"  # Placeholder - would check actual system metrics
            
            from api_library_model import ApiCredential
            api_connections = self.db.query(ApiCredential).filter(
                ApiCredential.is_active == True
            ).count()
            
            from database import User
            active_users = self.db.query(User).filter(User.is_active == True).count()
            
            trading_summary = self.get_trading_bots_summary()
            arbitrage_summary = self.get_dex_arbitrage_summary()
            validator_summary = self.get_validator_nodes_summary()
            
            total_pnl = (
                trading_summary['total_pnl'] + 
                arbitrage_summary['arbitrage_pnl'] + 
                validator_summary['validator_rewards']
            )
            
            return {
                'system_health': system_health,
                'api_connections': api_connections,
                'active_users': active_users,
                'total_pnl': total_pnl,
                'last_updated': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system overview: {e}")
            return {
                'system_health': 'error',
                'api_connections': 0,
                'active_users': 0,
                'total_pnl': 0.0,
                'last_updated': datetime.utcnow().isoformat()
            }
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity across all systems"""
        try:
            activities = []
            
            recent_bots = self.db.query(BotInstance).order_by(
                BotInstance.updated_at.desc()
            ).limit(limit//3).all()
            
            for bot in recent_bots:
                status = 'active' if bot.is_active else 'inactive'
                activities.append({
                    'type': 'bot',
                    'message': f"Bot {bot.name} status: {status}",
                    'timestamp': bot.updated_at.isoformat(),
                    'severity': 'info' if bot.is_active else 'warning'
                })
            
            activities.append({
                'type': 'system',
                'message': 'System health check completed',
                'timestamp': datetime.utcnow().isoformat(),
                'severity': 'info'
            })
            
            activities.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return activities[:limit]
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()

strategy_monitor = StrategyMonitorAggregator()
