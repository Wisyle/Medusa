#!/usr/bin/env python3
"""
DEX Arbitrage Model - Database models for DEX arbitrage monitoring
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class DEXArbitrageInstance(Base):
    __tablename__ = "dex_arbitrage_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    chain = Column(String(50), nullable=False)  # 'bnb', 'solana', 'ethereum'
    dex_pair = Column(String(100), nullable=False)  # 'BNB/USDT', 'SOL/USDT'
    primary_dex = Column(String(50), nullable=False)  # 'pancakeswap', 'uniswap', 'raydium'
    secondary_dex = Column(String(50), nullable=False)  # comparison DEX
    
    min_profit_threshold = Column(DECIMAL(10, 4), default=0.5)  # Minimum profit % to trigger
    max_trade_amount = Column(DECIMAL(18, 8), default=1000.0)  # Max amount per trade
    gas_limit = Column(Integer, default=300000)  # Gas limit for transactions
    
    api_credential_id = Column(Integer, ForeignKey('api_credentials.id'), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_topic_id = Column(String(100), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True)
    auto_execute = Column(Boolean, default=False)  # Auto-execute profitable trades
    
    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check = Column(DateTime, nullable=True)
    last_opportunity = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<DEXArbitrageInstance(name='{self.name}', chain='{self.chain}', pair='{self.dex_pair}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'chain': self.chain,
            'dex_pair': self.dex_pair,
            'primary_dex': self.primary_dex,
            'secondary_dex': self.secondary_dex,
            'min_profit_threshold': float(self.min_profit_threshold),
            'max_trade_amount': float(self.max_trade_amount),
            'gas_limit': self.gas_limit,
            'is_active': self.is_active,
            'auto_execute': self.auto_execute,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_check': self.last_check,
            'last_opportunity': self.last_opportunity
        }

class DEXOpportunity(Base):
    __tablename__ = "dex_opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey('dex_arbitrage_instances.id'), nullable=False)
    
    chain = Column(String(50), nullable=False)
    pair = Column(String(100), nullable=False)
    primary_dex = Column(String(50), nullable=False)
    secondary_dex = Column(String(50), nullable=False)
    
    primary_price = Column(DECIMAL(18, 8), nullable=False)
    secondary_price = Column(DECIMAL(18, 8), nullable=False)
    profit_percentage = Column(DECIMAL(10, 4), nullable=False)
    potential_profit_usd = Column(DECIMAL(18, 8), nullable=False)
    
    optimal_amount = Column(DECIMAL(18, 8), nullable=False)
    estimated_gas_cost = Column(DECIMAL(18, 8), nullable=True)
    net_profit_usd = Column(DECIMAL(18, 8), nullable=True)
    
    was_executed = Column(Boolean, default=False)
    execution_tx_hash = Column(String(100), nullable=True)
    execution_status = Column(String(50), nullable=True)  # 'pending', 'success', 'failed'
    
    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<DEXOpportunity(pair='{self.pair}', profit={self.profit_percentage}%, executed={self.was_executed})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'instance_id': self.instance_id,
            'chain': self.chain,
            'pair': self.pair,
            'primary_dex': self.primary_dex,
            'secondary_dex': self.secondary_dex,
            'primary_price': float(self.primary_price),
            'secondary_price': float(self.secondary_price),
            'profit_percentage': float(self.profit_percentage),
            'potential_profit_usd': float(self.potential_profit_usd),
            'optimal_amount': float(self.optimal_amount),
            'estimated_gas_cost': float(self.estimated_gas_cost) if self.estimated_gas_cost else None,
            'net_profit_usd': float(self.net_profit_usd) if self.net_profit_usd else None,
            'was_executed': self.was_executed,
            'execution_tx_hash': self.execution_tx_hash,
            'execution_status': self.execution_status,
            'detected_at': self.detected_at,
            'executed_at': self.executed_at
        }
