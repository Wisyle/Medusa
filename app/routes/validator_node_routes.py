#!/usr/bin/env python3
"""
Validator Node Routes - API endpoints for validator node management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from models.validator_node_model import ValidatorNode, ValidatorReward
from app.auth import get_current_user_html, User

router = APIRouter(prefix="/api/validators", tags=["validators"])

@router.get("/nodes", response_model=List[dict])
async def get_validator_nodes(
    request: Request,
    blockchain: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get all validator nodes"""
    query = db.query(ValidatorNode)
    
    if blockchain:
        query = query.filter(ValidatorNode.blockchain == blockchain)
    
    nodes = query.all()
    return [node.to_dict() for node in nodes]

@router.post("/nodes")
async def create_validator_node(
    request: Request,
    node_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
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
            description=node_data.get('description')
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        return {"message": f"Validator node '{node.name}' created successfully", "id": node.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create validator node: {str(e)}")

@router.get("/nodes/{node_id}")
async def get_validator_node(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get specific validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    return node.to_dict()

@router.put("/nodes/{node_id}")
async def update_validator_node(
    request: Request,
    node_id: int,
    node_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Update a validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    try:
        # Update allowed fields
        for field in ['name', 'staking_amount', 'delegated_amount', 'telegram_bot_token', 
                     'telegram_chat_id', 'telegram_topic_id', 'webhook_url', 'description']:
            if field in node_data:
                setattr(node, field, node_data[field])
        
        # Recalculate total stake
        if 'staking_amount' in node_data or 'delegated_amount' in node_data:
            node.total_stake = node.staking_amount + node.delegated_amount
        
        node.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": f"Validator node '{node.name}' updated successfully"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update validator node: {str(e)}")

@router.delete("/nodes/{node_id}")
async def delete_validator_node(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Delete a validator node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    if node.is_active:
        raise HTTPException(status_code=400, detail="Cannot delete an active validator node. Stop it first.")
    
    try:
        db.delete(node)
        db.commit()
        
        return {"message": f"Validator node '{node.name}' deleted successfully"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete validator node: {str(e)}")

@router.post("/nodes/{node_id}/start")
async def start_validator_monitoring(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Start validator monitoring for node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    if node.is_active:
        raise HTTPException(status_code=400, detail="Validator monitoring is already running")
    
    try:
        node.is_active = True
        node.last_activity = datetime.utcnow()
        db.commit()
        
        return {"message": f"Validator monitoring for '{node.name}' started successfully"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start validator monitoring: {str(e)}")

@router.post("/nodes/{node_id}/stop")
async def stop_validator_monitoring(
    request: Request,
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Stop validator monitoring for node"""
    node = db.query(ValidatorNode).filter(ValidatorNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Validator node not found")
    
    if not node.is_active:
        raise HTTPException(status_code=400, detail="Validator monitoring is already stopped")
    
    try:
        node.is_active = False
        db.commit()
        
        return {"message": f"Validator monitoring for '{node.name}' stopped successfully"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop validator monitoring: {str(e)}")

@router.get("/rewards")
async def get_validator_rewards(
    request: Request,
    node_id: int = None,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get validator rewards"""
    since_time = datetime.utcnow() - timedelta(days=days)
    query = db.query(ValidatorReward).filter(ValidatorReward.reward_date >= since_time)
    
    if node_id:
        query = query.filter(ValidatorReward.node_id == node_id)
    
    rewards = query.order_by(ValidatorReward.reward_date.desc()).all()
    return [reward.to_dict() for reward in rewards]

@router.get("/overview")
async def get_validators_overview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get validators overview statistics"""
    try:
        total_nodes = db.query(ValidatorNode).count()
        active_nodes = db.query(ValidatorNode).filter(ValidatorNode.is_active == True).count()
        
        # Calculate total staking amounts
        total_staking = db.query(ValidatorNode).with_entities(
            db.func.sum(ValidatorNode.total_stake)
        ).scalar() or 0.0
        
        # Get recent rewards
        recent_rewards = db.query(ValidatorReward).filter(
            ValidatorReward.reward_date >= datetime.utcnow() - timedelta(days=30)
        ).with_entities(
            db.func.sum(ValidatorReward.amount)
        ).scalar() or 0.0
        
        return {
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "inactive_nodes": total_nodes - active_nodes,
            "total_staking": total_staking,
            "monthly_rewards": recent_rewards,
            "system_status": "healthy" if total_nodes > 0 else "no_nodes"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get validators overview: {str(e)}")

@router.get("/status")
async def get_validators_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get overall validator system status"""
    try:
        total_nodes = db.query(ValidatorNode).count()
        active_nodes = db.query(ValidatorNode).filter(ValidatorNode.is_active == True).count()
        
        return {
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "inactive_nodes": total_nodes - active_nodes,
            "system_status": "healthy" if total_nodes > 0 else "no_nodes"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get validator status: {str(e)}")
