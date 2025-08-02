#!/usr/bin/env python3
"""
Validator Node Model - Database models for blockchain validator monitoring
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, DECIMAL, JSON
from datetime import datetime
from database import Base

class ValidatorNode(Base):
    __tablename__ = "validator_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    blockchain = Column(String(50), nullable=False)  # 'ton', 'solana', 'ethereum'
    strategy_name = Column(String(100), nullable=False)  # 'Alpha', 'Epsilon', etc.
    
    node_address = Column(String(255), nullable=False)
    validator_id = Column(String(255), nullable=True)  # Some chains use separate validator IDs
    
    staking_amount = Column(DECIMAL(18, 8), nullable=False)
    delegated_amount = Column(DECIMAL(18, 8), default=0.0)
    total_stake = Column(DECIMAL(18, 8), nullable=False)
    
    current_rewards = Column(DECIMAL(18, 8), default=0.0)
    total_rewards_earned = Column(DECIMAL(18, 8), default=0.0)
    uptime_percentage = Column(DECIMAL(5, 2), default=0.0)
    missed_blocks = Column(Integer, default=0)
    total_blocks = Column(Integer, default=0)
    
    current_apy = Column(DECIMAL(8, 4), default=0.0)
    average_apy_30d = Column(DECIMAL(8, 4), default=0.0)
    
    is_active = Column(Boolean, default=True)
    node_status = Column(String(50), default='unknown')  # 'active', 'inactive', 'jailed', 'slashed'
    last_block_signed = Column(DateTime, nullable=True)
    
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_topic_id = Column(String(100), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    
    min_uptime_alert = Column(DECIMAL(5, 2), default=95.0)  # Alert if uptime drops below %
    max_missed_blocks_alert = Column(Integer, default=10)  # Alert if missed blocks exceed
    min_apy_alert = Column(DECIMAL(8, 4), default=5.0)  # Alert if APY drops below %
    
    chain_config = Column(JSON, nullable=True)  # Store chain-specific settings
    
    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check = Column(DateTime, nullable=True)
    last_reward_claim = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ValidatorNode(name='{self.name}', blockchain='{self.blockchain}', strategy='{self.strategy_name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'blockchain': self.blockchain,
            'strategy_name': self.strategy_name,
            'node_address': self.node_address,
            'validator_id': self.validator_id,
            'staking_amount': float(self.staking_amount),
            'delegated_amount': float(self.delegated_amount),
            'total_stake': float(self.total_stake),
            'current_rewards': float(self.current_rewards),
            'total_rewards_earned': float(self.total_rewards_earned),
            'uptime_percentage': float(self.uptime_percentage),
            'missed_blocks': self.missed_blocks,
            'total_blocks': self.total_blocks,
            'current_apy': float(self.current_apy),
            'average_apy_30d': float(self.average_apy_30d),
            'is_active': self.is_active,
            'node_status': self.node_status,
            'last_block_signed': self.last_block_signed,
            'min_uptime_alert': float(self.min_uptime_alert),
            'max_missed_blocks_alert': self.max_missed_blocks_alert,
            'min_apy_alert': float(self.min_apy_alert),
            'chain_config': self.chain_config,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_check': self.last_check,
            'last_reward_claim': self.last_reward_claim
        }

class ValidatorReward(Base):
    __tablename__ = "validator_rewards"
    
    id = Column(Integer, primary_key=True, index=True)
    validator_id = Column(Integer, nullable=False)  # References validator_nodes.id
    
    epoch = Column(String(50), nullable=True)  # Epoch number (for chains that use epochs)
    block_height = Column(Integer, nullable=True)  # Block height when reward was earned
    reward_amount = Column(DECIMAL(18, 8), nullable=False)
    reward_type = Column(String(50), nullable=False)  # 'block_reward', 'delegation_reward', 'commission'
    
    tx_hash = Column(String(100), nullable=True)
    claimed = Column(Boolean, default=False)
    claim_tx_hash = Column(String(100), nullable=True)
    
    # Timestamps
    earned_at = Column(DateTime, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ValidatorReward(validator_id={self.validator_id}, amount={self.reward_amount}, type='{self.reward_type}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'validator_id': self.validator_id,
            'epoch': self.epoch,
            'block_height': self.block_height,
            'reward_amount': float(self.reward_amount),
            'reward_type': self.reward_type,
            'tx_hash': self.tx_hash,
            'claimed': self.claimed,
            'claim_tx_hash': self.claim_tx_hash,
            'earned_at': self.earned_at,
            'claimed_at': self.claimed_at,
            'created_at': self.created_at
        }
