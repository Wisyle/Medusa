#!/usr/bin/env python3
"""
DEX Arbitrage Routes - API endpoints for DEX arbitrage management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from database import get_db
from dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
from auth import get_current_user_html, User

router = APIRouter(prefix="/api/dex-arbitrage", tags=["dex-arbitrage"])

@router.get("/instances", response_model=List[dict])
async def get_dex_arbitrage_instances(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get all DEX arbitrage instances"""
    instances = db.query(DEXArbitrageInstance).all()
    return [instance.to_dict() for instance in instances]

@router.post("/instances")
async def create_dex_arbitrage_instance(
    request: Request,
    instance_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Create a new DEX arbitrage instance"""
    try:
        instance = DEXArbitrageInstance(
            name=instance_data['name'],
            chain=instance_data['chain'],
            dex_pair=instance_data['dex_pair'],
            primary_dex=instance_data['primary_dex'],
            secondary_dex=instance_data['secondary_dex'],
            min_profit_threshold=instance_data.get('min_profit_threshold', 0.5),
            max_trade_amount=instance_data.get('max_trade_amount', 1000.0),
            gas_limit=instance_data.get('gas_limit', 300000),
            api_credential_id=instance_data.get('api_credential_id'),
            telegram_bot_token=instance_data.get('telegram_bot_token'),
            telegram_chat_id=instance_data.get('telegram_chat_id'),
            telegram_topic_id=instance_data.get('telegram_topic_id'),
            webhook_url=instance_data.get('webhook_url'),
            auto_execute=instance_data.get('auto_execute', False),
            description=instance_data.get('description')
        )
        
        db.add(instance)
        db.commit()
        db.refresh(instance)
        
        return {"message": f"DEX arbitrage instance '{instance.name}' created successfully", "id": instance.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create DEX arbitrage instance: {str(e)}")

@router.get("/instances/{instance_id}")
async def get_dex_arbitrage_instance(
    request: Request,
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get specific DEX arbitrage instance"""
    instance = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    return instance.to_dict()

@router.put("/instances/{instance_id}")
async def update_dex_arbitrage_instance(
    request: Request,
    instance_id: int,
    instance_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Update DEX arbitrage instance"""
    instance = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    try:
        for field, value in instance_data.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        
        instance.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Instance updated successfully", "instance": instance.to_dict()}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update DEX arbitrage instance: {str(e)}")

@router.delete("/instances/{instance_id}")
async def delete_dex_arbitrage_instance(
    request: Request,
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Delete DEX arbitrage instance"""
    instance = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    try:
        db.query(DEXOpportunity).filter(DEXOpportunity.instance_id == instance_id).delete()
        
        db.delete(instance)
        db.commit()
        
        return {"message": "Instance deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete DEX arbitrage instance: {str(e)}")

@router.post("/instances/{instance_id}/start")
async def start_dex_arbitrage_monitoring(
    request: Request,
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Start DEX arbitrage monitoring for instance"""
    instance = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if instance.is_active:
        raise HTTPException(status_code=400, detail="Instance is already running")
    
    try:
        instance.is_active = True
        instance.last_activity = datetime.utcnow()
        db.commit()
        
        
        return {"message": f"DEX arbitrage monitoring started for {instance.name}"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@router.post("/instances/{instance_id}/stop")
async def stop_dex_arbitrage_monitoring(
    request: Request,
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Stop DEX arbitrage monitoring for instance"""
    instance = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if not instance.is_active:
        raise HTTPException(status_code=400, detail="Instance is already stopped")
    
    try:
        instance.is_active = False
        db.commit()
        
        
        return {"message": f"DEX arbitrage monitoring stopped for {instance.name}"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")

@router.get("/opportunities")
async def get_arbitrage_opportunities(
    request: Request,
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get recent arbitrage opportunities"""
    since_time = datetime.utcnow() - timedelta(hours=hours)
    opportunities = db.query(DEXOpportunity).filter(
        DEXOpportunity.detected_at >= since_time
    ).order_by(DEXOpportunity.detected_at.desc()).limit(100).all()
    
    return [opportunity.to_dict() for opportunity in opportunities]

@router.get("/opportunities/stats")
async def get_arbitrage_stats(
    request: Request,
    instance_id: int = None,
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get arbitrage opportunity statistics"""
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = db.query(DEXOpportunity).filter(DEXOpportunity.detected_at >= since)
    
    if instance_id:
        query = query.filter(DEXOpportunity.instance_id == instance_id)
    
    opportunities = query.all()
    
    if not opportunities:
        return {
            "total_opportunities": 0,
            "executed_opportunities": 0,
            "total_potential_profit": 0.0,
            "total_executed_profit": 0.0,
            "average_profit_percentage": 0.0,
            "best_opportunity": None
        }
    
    executed_opps = [opp for opp in opportunities if opp.was_executed]
    
    stats = {
        "total_opportunities": len(opportunities),
        "executed_opportunities": len(executed_opps),
        "total_potential_profit": sum(float(opp.potential_profit_usd) for opp in opportunities),
        "total_executed_profit": sum(float(opp.net_profit_usd or 0) for opp in executed_opps),
        "average_profit_percentage": sum(float(opp.profit_percentage) for opp in opportunities) / len(opportunities),
        "best_opportunity": max(opportunities, key=lambda x: x.profit_percentage).to_dict()
    }
    
    return stats

@router.get("/status")
async def get_dex_arbitrage_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_html)
):
    """Get overall DEX arbitrage system status"""
    try:
        total_instances = db.query(DEXArbitrageInstance).count()
        active_instances = db.query(DEXArbitrageInstance).filter(DEXArbitrageInstance.is_active == True).count()
        
        # Get recent opportunities
        recent_opportunities = db.query(DEXOpportunity).filter(
            DEXOpportunity.detected_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        return {
            "total_instances": total_instances,
            "active_instances": active_instances,
            "inactive_instances": total_instances - active_instances,
            "recent_opportunities_24h": recent_opportunities,
            "system_status": "healthy" if total_instances > 0 else "no_instances"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get DEX arbitrage status: {str(e)}")
