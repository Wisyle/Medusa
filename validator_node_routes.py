#!/usr/bin/env python3
"""
Validator Node Routes - API endpoints for validator node management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from database import get_db
from validator_node_model import ValidatorNode, ValidatorReward
from auth import get_current_active_user, User

router = APIRouter(prefix="/api/validators", tags=["validators"])

@router.get("/nodes", response_model=List[dict])
async def get_validator_nodes(
    blockchain: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all validator nodes"""
    query = db.query(ValidatorNode)
    
    if blockchain:
        query = query.filter(ValidatorNode.blockchain == blockchain)
    
    nodes = query.all()
    return [node.to_dict() for node in nodes]

@router.post("/nodes")
async def create_validator_node(
    node_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new validator node"""
    try:
        node = ValidatorNode(
            name=node_data['name'],
            blockchain=node_data['blockchain'],
            strategy_name=node_data['strategy_name'],
            node_address=node_data['node_address'],
            validator_id=node_data.get('validator_id'),
            staking_amount=node_data['staking_amount'],
            delegated_amount=node_data.get('delegated_amount', 0.0),
            total_stake=node_data['staking_amount'] + node_data.get('delegated_amount', 0.0),
            telegram_bot_token=node_data.get('telegram_bot_token'),
            telegram_chat_id=node_data.get('telegram_chat_id'),
            telegram_topic_id=node_data.get('telegram_topic_id'),
            webhook_url=node_data.get('webhook_url'),
            min_uptime_alert=node_data.get('min_uptime_alert', 95.0),
            max_missed_blocks_alert=node_data.get('max_missed_blocks_alert', 10),
            min_apy_alert=node_data.get('min_apy_alert', 5.0),
            chain_config=node_data.get('chain_config'),
            description=node_data.get('description')
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        return {"message": "Validator node created successfully", "node": node.to_dict()}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create validator node: {str(e)}")

@router.get("/nodes/{node_id}")
async def get_validator_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    return node.to_dict()

@router.put("/nodes/{node_id}")
async def update_validator_node(
    node_id: int,
    node_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    try:
        for field, value in node_data.items():
            if hasattr(node, field):
                setattr(node, field, value)
        
        node.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Validator node updated successfully", "node": node.to_dict()}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update validator node: {str(e)}")

@router.delete("/nodes/{node_id}")
async def delete_validator_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    try:
        db.query(ValidatorReward).filter(ValidatorReward.validator_id == node_id).delete()
        
        db.delete(node)
        db.commit()
        
        return {"message": "Validator node deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to delete validator node: {str(e)}")

@router.get("/nodes/{node_id}/rewards")
async def get_validator_rewards(
    node_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get validator rewards history"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    rewards = db.query(ValidatorReward).filter(
        ValidatorReward.validator_id == node_id,
        ValidatorReward.earned_at >= since
    ).order_by(ValidatorReward.earned_at.desc()).all()
    
    return [reward.to_dict() for reward in rewards]

@router.get("/nodes/{node_id}/stats")
async def get_validator_stats(
    node_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get validator performance statistics"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    rewards = db.query(ValidatorReward).filter(
        ValidatorReward.validator_id == node_id,
        ValidatorReward.earned_at >= since
    ).all()
    
    total_rewards = sum(float(reward.reward_amount) for reward in rewards)
    claimed_rewards = sum(float(reward.reward_amount) for reward in rewards if reward.claimed)
    unclaimed_rewards = total_rewards - claimed_rewards
    
    stats = {
        "node_info": node.to_dict(),
        "period_days": days,
        "total_rewards": total_rewards,
        "claimed_rewards": claimed_rewards,
        "unclaimed_rewards": unclaimed_rewards,
        "reward_count": len(rewards),
        "average_daily_rewards": total_rewards / days if days > 0 else 0,
        "current_apy": float(node.current_apy),
        "uptime_percentage": float(node.uptime_percentage),
        "missed_blocks": node.missed_blocks,
        "node_status": node.node_status
    }
    
    return stats

@router.get("/overview")
async def get_validators_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get overview of all validator nodes"""
    nodes = db.query(ValidatorNode).all()
    
    if not nodes:
        return {
            "total_nodes": 0,
            "active_nodes": 0,
            "total_staked": 0.0,
            "total_rewards": 0.0,
            "average_apy": 0.0,
            "nodes_by_blockchain": {},
            "nodes_by_strategy": {}
        }
    
    active_nodes = [node for node in nodes if node.is_active]
    total_staked = sum(float(node.total_stake) for node in nodes)
    total_rewards = sum(float(node.total_rewards_earned) for node in nodes)
    average_apy = sum(float(node.current_apy) for node in nodes) / len(nodes)
    
    nodes_by_blockchain = {}
    for node in nodes:
        blockchain = node.blockchain
        if blockchain not in nodes_by_blockchain:
            nodes_by_blockchain[blockchain] = []
        nodes_by_blockchain[blockchain].append(node.to_dict())
    
    nodes_by_strategy = {}
    for node in nodes:
        strategy = node.strategy_name
        if strategy not in nodes_by_strategy:
            nodes_by_strategy[strategy] = []
        nodes_by_strategy[strategy].append(node.to_dict())
    
    overview = {
        "total_nodes": len(nodes),
        "active_nodes": len(active_nodes),
        "total_staked": total_staked,
        "total_rewards": total_rewards,
        "average_apy": average_apy,
        "nodes_by_blockchain": nodes_by_blockchain,
        "nodes_by_strategy": nodes_by_strategy
    }
    
    return overview
