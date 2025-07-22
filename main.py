from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
import os
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
import multiprocessing
from datetime import datetime, timedelta
import uvicorn

from database import get_db, init_db, BotInstance, ActivityLog, ErrorLog, User
from polling import run_poller
from config import settings
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    create_user, generate_totp_secret, generate_totp_qr_code,
    UserCreate, UserLogin, UserResponse, Token
)

app = FastAPI(title="TGL MEDUSA - Crypto Bot Monitor", version="2.0.0")

templates = Jinja2Templates(directory="templates")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

active_processes = {}

@app.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Login with email, password, and optional TOTP"""
    user = authenticate_user(db, user_login.email, user_login.password, user_login.totp_code)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/register", response_model=UserResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """Register new user"""
    return create_user(db, user_create)

@app.post("/auth/setup-2fa")
async def setup_2fa(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Setup Google Authenticator 2FA"""
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")
    
    secret = generate_totp_secret()
    qr_code = generate_totp_qr_code(current_user.email, secret)
    
    current_user.totp_secret = secret
    db.commit()
    
    return {"qr_code": qr_code, "secret": secret}

@app.post("/auth/enable-2fa")
async def enable_2fa(totp_code: str = Form(...), current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Enable 2FA after verifying TOTP code"""
    import pyotp
    
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not set up")
    
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    
    current_user.totp_enabled = True
    db.commit()
    
    return {"message": "2FA enabled successfully"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_instances": len(active_processes)
    }

@app.get("/api/instances")
async def get_instances(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get all bot instances"""
    instances = db.query(BotInstance).all()
    return [
        {
            "id": instance.id,
            "name": instance.name,
            "exchange": instance.exchange,
            "strategies": instance.strategies,
            "is_active": instance.is_active,
            "last_poll": instance.last_poll.isoformat() if instance.last_poll else None,
            "last_error": instance.last_error,
            "polling_interval": instance.polling_interval
        }
        for instance in instances
    ]

def validate_instance_data(name: str, exchange: str, api_key: str, api_secret: str, trading_pair: Optional[str] = None):
    """Validate instance creation data"""
    errors = []
    
    if not name or not name.strip():
        errors.append("Instance name is required")
    elif len(name.strip()) > 100:
        errors.append("Instance name must be 100 characters or less")
        
    if not exchange or not exchange.strip():
        errors.append("Exchange is required")
    elif exchange.strip().lower() not in ['bybit', 'binance', 'okx', 'kucoin', 'mexc', 'gate', 'coinbase', 'bitfinex']:
        errors.append("Invalid exchange")
        
    if not api_key or not api_key.strip():
        errors.append("API key is required")
    elif len(api_key.strip()) > 255:
        errors.append("API key too long")
        
    if not api_secret or not api_secret.strip():
        errors.append("API secret is required")
    elif len(api_secret.strip()) > 255:
        errors.append("API secret too long")
    elif any(keyword in api_secret.lower() for keyword in ['error', 'ssl', 'failed', 'connection']):
        errors.append("API secret contains invalid content - please check your input")
    
    if trading_pair and not trading_pair.strip():
        errors.append("Trading pair cannot be empty if provided")
    
    # Accept both formats: BTC/USDT and BTCUSDT
    if trading_pair and trading_pair.strip():
        pair = trading_pair.strip().upper()
        # Check if it's in BASE/QUOTE format
        if '/' in pair:
            parts = pair.split('/')
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append("Trading pair format with slash must be BASE/QUOTE (e.g., BTC/USDT)")
        # Check if it's in BASEUSDT format (no slash)
        elif not pair.endswith(('USDT', 'BUSD', 'BTC', 'ETH', 'USD', 'EUR')):
            errors.append("Trading pair must end with a valid quote currency (USDT, BUSD, BTC, ETH, USD, EUR) or use BASE/QUOTE format")
        elif len(pair) < 4:
            errors.append("Trading pair too short - use format like BTC/USDT or BTCUSDT")
        
    return errors

@app.post("/api/instances")
async def create_instance(
    name: str = Form(...),
    exchange: str = Form(...),
    market_type: str = Form("unified"),
    api_key: str = Form(...),
    api_secret: str = Form(...),
    api_passphrase: str = Form(""),
    strategies: str = Form(""),
    polling_interval: int = Form(60),
    webhook_url: str = Form(""),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    telegram_topic_id: str = Form(""),
    trading_pair: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create new bot instance"""
    try:
        validation_errors = validate_instance_data(name, exchange, api_key, api_secret, trading_pair)
        if validation_errors:
            raise HTTPException(status_code=400, detail="; ".join(validation_errors))
        
        strategy_list = [s.strip() for s in strategies.split(",") if s.strip()] if strategies else []
        
        instance = BotInstance(
            name=name.strip(),
            exchange=exchange.strip(),
            market_type=market_type.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            api_passphrase=api_passphrase.strip() if api_passphrase else None,
            strategies=strategy_list,
            polling_interval=polling_interval,
            webhook_url=webhook_url.strip() if webhook_url else None,
            telegram_bot_token=telegram_bot_token.strip() if telegram_bot_token else None,
            telegram_chat_id=telegram_chat_id.strip() if telegram_chat_id else None,
            telegram_topic_id=telegram_topic_id.strip() if telegram_topic_id else None,
            trading_pair=trading_pair.strip() if trading_pair else None
        )
        
        db.add(instance)
        db.commit()
        db.refresh(instance)
        
        return {"id": instance.id, "message": "Instance created successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Database error creating instance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create instance: {str(e)}")

def _run_poller_sync(instance_id: int):
    """Synchronous wrapper for running async poller"""
    asyncio.run(run_poller(instance_id))

@app.post("/api/instances/{instance_id}/start")
async def start_instance(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Start bot instance"""
    instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if instance_id in active_processes:
        raise HTTPException(status_code=400, detail="Instance already running")
    
    process = multiprocessing.Process(target=_run_poller_sync, args=(instance_id,))
    process.start()
    
    active_processes[instance_id] = process
    
    instance.is_active = True
    db.commit()
    
    return {"message": "Instance started successfully"}

@app.post("/api/instances/{instance_id}/stop")
async def stop_instance(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Stop bot instance"""
    instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if instance_id in active_processes:
        process = active_processes[instance_id]
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
        del active_processes[instance_id]
    
    instance.is_active = False
    db.commit()
    
    return {"message": "Instance stopped successfully"}

@app.delete("/api/instances/{instance_id}")
async def delete_instance(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Delete bot instance"""
    instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if instance_id in active_processes:
        await stop_instance(instance_id, db, current_user)
    
    db.delete(instance)
    db.commit()
    
    return {"message": "Instance deleted successfully"}

@app.get("/api/instances/{instance_id}/logs")
async def get_instance_logs(
    instance_id: int,
    log_type: str = "activity",
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get logs for instance"""
    if log_type == "activity":
        logs = db.query(ActivityLog).filter(
            ActivityLog.instance_id == instance_id
        ).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "event_type": log.event_type,
                "symbol": log.symbol,
                "message": log.message,
                "timestamp": log.timestamp.isoformat()
            }
            for log in logs
        ]
    
    elif log_type == "error":
        logs = db.query(ErrorLog).filter(
            ErrorLog.instance_id == instance_id
        ).order_by(ErrorLog.timestamp.desc()).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "error_type": log.error_type,
                "error_message": log.error_message,
                "timestamp": log.timestamp.isoformat()
            }
            for log in logs
        ]
    
    else:
        raise HTTPException(status_code=400, detail="Invalid log type")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/setup-2fa", response_class=HTMLResponse)
async def setup_2fa_page(request: Request):
    """2FA setup page"""
    return templates.TemplateResponse("setup_2fa.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/instances", response_class=HTMLResponse)
async def instances_page(request: Request):
    """Instances management page"""
    return templates.TemplateResponse("instances.html", {"request": request})

@app.get("/instances/new", response_class=HTMLResponse)
async def new_instance_page(request: Request):
    """New instance form"""
    return templates.TemplateResponse("new_instance.html", {"request": request})

@app.get("/instances/{instance_id}", response_class=HTMLResponse)
async def instance_detail(request: Request, instance_id: int):
    """Instance detail page"""
    return templates.TemplateResponse("instance_detail.html", {"request": request, "instance_id": instance_id})

@app.get("/system-logs", response_class=HTMLResponse)
async def system_logs_page(request: Request):
    """System logs dashboard"""
    return templates.TemplateResponse("system_logs.html", {"request": request})

@app.get("/api/system-logs")
async def get_system_logs(
    service: str = "all",
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """Get system logs from all services"""
    db = next(get_db())
    
    logs = []
    
    activity_logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    for log in activity_logs:
        logs.append({
            "timestamp": log.timestamp.isoformat(),
            "service": "polling",
            "level": "INFO",
            "message": f"[Instance {log.instance_id}] {log.event_type}: {log.message}",
            "instance_id": log.instance_id
        })
    
    error_logs = db.query(ErrorLog).order_by(ErrorLog.timestamp.desc()).limit(limit).all()
    for log in error_logs:
        logs.append({
            "timestamp": log.timestamp.isoformat(),
            "service": "polling",
            "level": "ERROR",
            "message": f"[Instance {log.instance_id}] {log.error_type}: {log.error_message}",
            "instance_id": log.instance_id
        })
    
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    db.close()
    return {"logs": logs[:limit]}

@app.get("/api/signals/{instance_id}")
async def get_instance_signals(
    instance_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get critical action signals for external systems"""
    critical_events = ["order_filled", "order_cancelled", "new_order", "position_update", "position_closed"]
    
    logs = db.query(ActivityLog).filter(
        ActivityLog.instance_id == instance_id,
        ActivityLog.event_type.in_(critical_events)
    ).order_by(ActivityLog.timestamp.desc()).limit(limit).all()
    
    signals = []
    for log in logs:
        signal = {
            "instance_id": instance_id,
            "exchange": None,
            "pair": log.symbol,
            "event": log.event_type,
            "timestamp": log.timestamp.isoformat()
        }
        
        instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
        if instance:
            signal["exchange"] = instance.exchange
        
        if log.data and isinstance(log.data, dict):
            if log.event_type in ["order_filled", "order_cancelled", "new_order"]:
                signal["order"] = {
                    "id": log.data.get("order_id"),
                    "side": log.data.get("side"),
                    "price": log.data.get("entry_price"),
                    "amount": log.data.get("quantity"),
                    "status": log.data.get("status"),
                    "pnl": log.data.get("unrealized_pnl")
                }
            elif log.event_type == "position_update":
                signal["position"] = {
                    "side": log.data.get("side"),
                    "entry_price": log.data.get("entry_price"),
                    "quantity": log.data.get("quantity"),
                    "unrealized_pnl": log.data.get("unrealized_pnl")
                }
        
        signals.append(signal)
    
    return {"signals": signals}

@app.on_event("startup")
async def startup_event():
    """Initialize database and start monitoring"""
    # Create tables first
    init_db()
    
    # Then run migrations for any new columns
    from migration import migrate_database
    migrate_database()
    
    asyncio.create_task(monitor_instances())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up processes"""
    for process in active_processes.values():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()

async def monitor_instances():
    """Monitor and restart failed instances"""
    while True:
        try:
            db = next(get_db())
            
            active_instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
            
            for instance in active_instances:
                if instance.id not in active_processes:
                    try:
                        process = multiprocessing.Process(target=_run_poller_sync, args=(instance.id,))
                        process.start()
                        active_processes[instance.id] = process
                    except Exception as e:
                        print(f"Failed to restart instance {instance.id}: {e}")
                
                elif not active_processes[instance.id].is_alive():
                    try:
                        del active_processes[instance.id]
                        process = multiprocessing.Process(target=_run_poller_sync, args=(instance.id,))
                        process.start()
                        active_processes[instance.id] = process
                    except Exception as e:
                        print(f"Failed to restart dead instance {instance.id}: {e}")
            
            db.close()
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        await asyncio.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
