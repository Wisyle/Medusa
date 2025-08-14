#!/usr/bin/env python3
"""
Strategy Monitor Management API - Web interface for managing strategy monitors
"""

from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from app.database import get_db, BotInstance
from models.strategy_monitor_model import StrategyMonitor

# Create router for strategy monitor endpoints
router = APIRouter(prefix="/api/strategy-monitors", tags=["Strategy Monitors"])

@router.get("/", response_class=HTMLResponse)
async def strategy_monitors_page(db: Session = Depends(get_db)):
    """Strategy monitors management page"""
    monitors = db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all()
    
    # Get available strategies from instances
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    all_strategies = set()
    for instance in instances:
        if instance.strategies:
            all_strategies.update(instance.strategies)
    
    return templates.TemplateResponse("strategy_monitors.html", {
        "request": request,
        "monitors": monitors,
        "available_strategies": sorted(all_strategies)
    })

@router.post("/")
async def create_strategy_monitor(
    strategy_name: str = Form(...),
    telegram_bot_token: str = Form(...),
    telegram_chat_id: str = Form(...),
    telegram_topic_id: Optional[str] = Form(None),
    report_interval: int = Form(3600),  # Default 1 hour
    include_positions: bool = Form(True),
    include_orders: bool = Form(True),
    include_trades: bool = Form(True),
    include_pnl: bool = Form(True),
    max_recent_positions: int = Form(20),
    db: Session = Depends(get_db)
):
    """Create new strategy monitor"""
    
    # Check if monitor already exists
    existing = db.query(StrategyMonitor).filter(StrategyMonitor.strategy_name == strategy_name).first()
    if existing:
        return templates.TemplateResponse("strategy_monitors.html", {
            "request": request,
            "monitors": db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all(),
            "available_strategies": sorted(set(s for instance in db.query(BotInstance).filter(BotInstance.is_active == True).all() for s in (instance.strategies or []))),
            "error": f"Monitor for strategy '{strategy_name}' already exists"
        })
    
    # Validate strategy exists in active instances
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    strategy_exists = False
    for instance in instances:
        if instance.strategies and strategy_name in instance.strategies:
            strategy_exists = True
            break
    
    if not strategy_exists:
        return templates.TemplateResponse("strategy_monitors.html", {
            "request": request,
            "monitors": db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all(),
            "available_strategies": sorted(set(s for instance in db.query(BotInstance).filter(BotInstance.is_active == True).all() for s in (instance.strategies or []))),
            "error": f"Strategy '{strategy_name}' not found in any active instances"
        })
    
    try:
        monitor = StrategyMonitor(
            strategy_name=strategy_name,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id if telegram_topic_id else None,
            report_interval=report_interval,
            include_positions=include_positions,
            include_orders=include_orders,
            include_trades=include_trades,
            include_pnl=include_pnl,
            max_recent_positions=max_recent_positions,
            is_active=True
        )
        
        db.add(monitor)
        db.commit()
        db.refresh(monitor)
        
        # Redirect to strategy monitors page with success message
        return RedirectResponse(url="/strategy-monitors?success=created", status_code=303)
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("strategy_monitors.html", {
            "request": request,
            "monitors": db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all(),
            "available_strategies": sorted(set(s for instance in db.query(BotInstance).filter(BotInstance.is_active == True).all() for s in (instance.strategies or []))),
            "error": f"Failed to create monitor: {str(e)}"
        })

@router.put("/{monitor_id}")
async def update_strategy_monitor(
    monitor_id: int,
    telegram_bot_token: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    telegram_topic_id: Optional[str] = Form(None),
    report_interval: Optional[int] = Form(None),
    include_positions: Optional[bool] = Form(None),
    include_orders: Optional[bool] = Form(None),
    include_trades: Optional[bool] = Form(None),
    include_pnl: Optional[bool] = Form(None),
    max_recent_positions: Optional[int] = Form(None),
    is_active: Optional[bool] = Form(None),
    db: Session = Depends(get_db)
):
    """Update strategy monitor configuration"""
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    # Update fields if provided
    if telegram_bot_token is not None:
        monitor.telegram_bot_token = telegram_bot_token
    if telegram_chat_id is not None:
        monitor.telegram_chat_id = telegram_chat_id
    if telegram_topic_id is not None:
        monitor.telegram_topic_id = telegram_topic_id if telegram_topic_id else None
    if report_interval is not None:
        monitor.report_interval = report_interval
    if include_positions is not None:
        monitor.include_positions = include_positions
    if include_orders is not None:
        monitor.include_orders = include_orders
    if include_trades is not None:
        monitor.include_trades = include_trades
    if include_pnl is not None:
        monitor.include_pnl = include_pnl
    if max_recent_positions is not None:
        monitor.max_recent_positions = max_recent_positions
    if is_active is not None:
        monitor.is_active = is_active
    
    monitor.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"Strategy monitor updated for '{monitor.strategy_name}'"}

@router.delete("/{monitor_id}")
async def delete_strategy_monitor(monitor_id: int, db: Session = Depends(get_db)):
    """Delete strategy monitor"""
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    strategy_name = monitor.strategy_name
    db.delete(monitor)
    db.commit()
    
    return {"message": f"Strategy monitor deleted for '{strategy_name}'"}

@router.post("/{monitor_id}/toggle")
async def toggle_strategy_monitor(monitor_id: int, db: Session = Depends(get_db)):
    """Toggle strategy monitor active status"""
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    monitor.is_active = not monitor.is_active
    monitor.updated_at = datetime.utcnow()
    db.commit()
    
    status = "activated" if monitor.is_active else "deactivated"
    return {"message": f"Strategy monitor {status} for '{monitor.strategy_name}'"}

@router.post("/{monitor_id}/test-report")
async def send_test_report(monitor_id: int, db: Session = Depends(get_db)):
    """Send a test report for strategy monitor"""
    from strategy_monitor import StrategyMonitorService
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    if not monitor.is_active:
        raise HTTPException(status_code=400, detail="Strategy monitor is not active")
    
    try:
        service = StrategyMonitorService(monitor.strategy_name)
        await service.send_report()
        service.close()
        
        return {"message": f"Test report sent for strategy '{monitor.strategy_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test report: {str(e)}")

@router.get("/list")
async def get_strategy_monitors(db: Session = Depends(get_db)):
    """Get all strategy monitors"""
    monitors = db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all()
    
    result = []
    for monitor in monitors:
        result.append({
            "id": monitor.id,
            "strategy_name": monitor.strategy_name,
            "is_active": monitor.is_active,
            "report_interval": monitor.report_interval,
            "include_positions": monitor.include_positions,
            "include_orders": monitor.include_orders,
            "include_trades": monitor.include_trades,
            "include_pnl": monitor.include_pnl,
            "max_recent_positions": monitor.max_recent_positions,
            "last_report": monitor.last_report.isoformat() if monitor.last_report else None,
            "last_error": monitor.last_error,
            "created_at": monitor.created_at.isoformat(),
            "updated_at": monitor.updated_at.isoformat() if monitor.updated_at else None
        })
    
    return result
