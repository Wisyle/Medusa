from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
from api_library_model import ApiCredential
from polling import run_poller
from config import settings
from api_library_routes import add_api_library_routes
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    create_user, generate_totp_secret, generate_totp_qr_code,
    UserCreate, UserLogin, UserResponse, Token, get_current_user
)
from strategy_monitor_model import StrategyMonitor

app = FastAPI(title="TGL MEDUSA - Crypto Bot Monitor", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add API Library routes
add_api_library_routes(app)

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
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with migration status"""
    try:
        # Check if API Library migration completed
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        
        api_library_ready = False
        bot_instances_migrated = False
        
        if 'api_credentials' in tables:
            api_library_ready = True
            
        if 'bot_instances' in tables:
            columns = {col['name']: col for col in inspector.get_columns('bot_instances')}
            if 'api_credential_id' in columns:
                bot_instances_migrated = True
        
        migration_status = "completed" if (api_library_ready and bot_instances_migrated) else "in_progress"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "active_instances": len(active_processes),
            "migration_status": migration_status,
            "api_library_ready": api_library_ready,
            "bot_instances_migrated": bot_instances_migrated
        }
    except Exception as e:
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "active_instances": len(active_processes),
            "migration_status": "error",
            "error": str(e)
        }

@app.get("/api/strategy-monitor-health")
async def strategy_monitor_health(db: Session = Depends(get_db)):
    """Strategy monitor health check endpoint"""
    try:
        monitors = db.query(StrategyMonitor).filter(StrategyMonitor.is_active == True).all()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "active_monitors": len(monitors),
            "monitors": [
                {
                    "strategy_name": m.strategy_name,
                    "last_report": m.last_report.isoformat() if m.last_report else None,
                    "has_error": bool(m.last_error)
                }
                for m in monitors
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
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
    api_source: str = Form("library"),  # "library" or "direct"
    api_credential_id: Optional[int] = Form(None),
    api_key: Optional[str] = Form(None),
    api_secret: Optional[str] = Form(None),
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
        # Handle API credentials based on source
        if api_source == "library":
            if not api_credential_id:
                raise HTTPException(status_code=400, detail="API credential must be selected when using library")
            
            # Check if credential exists and is available
            credential = db.query(ApiCredential).filter(ApiCredential.id == api_credential_id).first()
            if not credential:
                raise HTTPException(status_code=400, detail="Selected API credential not found")
            
            if credential.is_in_use:
                current_instance = db.query(BotInstance).filter(BotInstance.api_credential_id == api_credential_id).first()
                current_name = current_instance.name if current_instance else "Unknown"
                raise HTTPException(status_code=400, detail=f"API credential is already in use by instance '{current_name}'")
            
            if credential.exchange.lower() != exchange.lower():
                raise HTTPException(status_code=400, detail=f"API credential is for {credential.exchange}, but instance is for {exchange}")
            
            # Validation for library mode - just check basic fields
            validation_errors = validate_instance_data(name, exchange, "dummy", "dummy", trading_pair)
        else:
            # Direct API mode - validate API credentials
            if not api_key or not api_secret:
                raise HTTPException(status_code=400, detail="API key and secret are required for direct mode")
            
            validation_errors = validate_instance_data(name, exchange, api_key, api_secret, trading_pair)
        if validation_errors:
            raise HTTPException(status_code=400, detail="; ".join(validation_errors))
        
        strategy_list = [s.strip() for s in strategies.split(",") if s.strip()] if strategies else []
        
        # Create instance based on API source
        if api_source == "library":
            instance = BotInstance(
                name=name.strip(),
                exchange=exchange.strip(),
                market_type=market_type.strip(),
                api_credential_id=api_credential_id,
                api_key=None,  # Will use credential from library
                api_secret=None,  # Will use credential from library
                api_passphrase=None,  # Will use credential from library
                strategies=strategy_list,
                polling_interval=polling_interval,
                webhook_url=webhook_url.strip() if webhook_url else None,
                telegram_bot_token=telegram_bot_token.strip() if telegram_bot_token else None,
                telegram_chat_id=telegram_chat_id.strip() if telegram_chat_id else None,
                telegram_topic_id=telegram_topic_id.strip() if telegram_topic_id else None,
                trading_pair=trading_pair.strip() if trading_pair else None
            )
        else:
            instance = BotInstance(
                name=name.strip(),
                exchange=exchange.strip(),
                market_type=market_type.strip(),
                api_credential_id=None,
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
        
        # If using API library, mark credential as in use
        if api_source == "library" and api_credential_id:
            credential = db.query(ApiCredential).filter(ApiCredential.id == api_credential_id).first()
            if credential:
                credential.is_in_use = True
                credential.current_instance_id = instance.id
                credential.last_used = datetime.utcnow()
                db.commit()
        
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

@app.put("/api/instances/{instance_id}")
async def update_instance(
    instance_id: int,
    name: str = Form(...),
    exchange: str = Form(...),
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
    market_type: str = Form("unified"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update bot instance"""
    instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    # Validate the data
    validation_errors = validate_instance_data(name, exchange, api_key, api_secret, trading_pair)
    if validation_errors:
        raise HTTPException(status_code=400, detail=validation_errors)
    
    # Check if instance is running and stop it if updating critical fields
    was_active = instance.is_active
    if was_active and instance_id in active_processes:
        await stop_instance(instance_id, db, current_user)
    
    # Update the instance
    instance.name = name
    instance.exchange = exchange
    instance.api_key = api_key
    instance.api_secret = api_secret
    instance.api_passphrase = api_passphrase if api_passphrase else None
    instance.strategies = strategies.split(',') if strategies else []
    instance.polling_interval = polling_interval
    instance.webhook_url = webhook_url if webhook_url else None
    instance.telegram_bot_token = telegram_bot_token if telegram_bot_token else None
    instance.telegram_chat_id = telegram_chat_id if telegram_chat_id else None
    instance.telegram_topic_id = telegram_topic_id if telegram_topic_id else None
    instance.trading_pair = trading_pair.strip() if trading_pair else None
    instance.market_type = market_type
    instance.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Restart if it was previously active
    if was_active:
        await start_instance(instance_id, db, current_user)
    
    return {"message": "Instance updated successfully", "instance_id": instance_id}

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

@app.get("/instances/{instance_id}/edit", response_class=HTMLResponse)
async def edit_instance_page(request: Request, instance_id: int):
    """Edit instance form"""
    return templates.TemplateResponse("edit_instance.html", {"request": request, "instance_id": instance_id})

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    """Account settings page - authentication handled by JavaScript"""
    return templates.TemplateResponse("account.html", {"request": request})

# Account Settings API Routes
@app.get("/api/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_active_user)):
    """Get current user profile"""
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "totp_enabled": current_user.totp_enabled,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }

@app.post("/api/user/profile")
async def update_profile(
    full_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user profile"""
    try:
        current_user.full_name = full_name.strip() if full_name else None
        db.commit()
        return {"message": "Profile updated successfully"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

@app.post("/api/user/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Change user password"""
    try:
        from auth import verify_password, get_password_hash
        
        # Verify current password
        if not verify_password(current_password, current_user.hashed_password):
            return {"error": "Current password is incorrect"}
        
        # Validate new password
        if len(new_password) < 8:
            return {"error": "New password must be at least 8 characters long"}
        
        # Update password
        current_user.hashed_password = get_password_hash(new_password)
        db.commit()
        
        return {"message": "Password changed successfully"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

@app.post("/api/user/2fa/setup")
async def setup_2fa_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Setup 2FA - generate secret and QR code"""
    try:
        if current_user.totp_secret and current_user.totp_enabled:
            return {"error": "2FA is already enabled"}
        
        secret = generate_totp_secret()
        qr_url = generate_totp_qr_code(current_user.email, secret)
        
        # Store secret temporarily (not enabled yet)
        current_user.totp_secret = secret
        current_user.totp_enabled = False
        db.commit()
        
        return {
            "secret": secret,
            "qr_url": qr_url
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

@app.post("/api/user/2fa/verify")
async def verify_2fa_setup(
    totp_code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Verify and enable 2FA"""
    try:
        import pyotp
        
        if not current_user.totp_secret:
            return {"error": "2FA setup not initiated"}
        
        totp = pyotp.TOTP(current_user.totp_secret)
        if not totp.verify(totp_code):
            return {"error": "Invalid verification code"}
        
        # Enable 2FA
        current_user.totp_enabled = True
        db.commit()
        
        return {"message": "2FA enabled successfully"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

@app.post("/api/user/2fa/disable")
async def disable_2fa(
    password: str = Form(...),
    totp_code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Disable 2FA"""
    try:
        from auth import verify_password
        import pyotp
        
        # Verify password
        if not verify_password(password, current_user.hashed_password):
            return {"error": "Incorrect password"}
        
        # Verify TOTP code
        if not current_user.totp_secret:
            return {"error": "2FA not enabled"}
        
        totp = pyotp.TOTP(current_user.totp_secret)
        if not totp.verify(totp_code):
            return {"error": "Invalid verification code"}
        
        # Disable 2FA
        current_user.totp_secret = None
        current_user.totp_enabled = False
        db.commit()
        
        return {"message": "2FA disabled successfully"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}

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

# Strategy Monitor Routes

@app.get("/strategy-monitors", response_class=HTMLResponse)
async def strategy_monitors_page(request: Request, db: Session = Depends(get_db)):
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

@app.post("/strategy-monitors")
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
        raise HTTPException(status_code=400, detail=f"Monitor for strategy '{strategy_name}' already exists")
    
    # Validate strategy exists in active instances
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    strategy_exists = False
    for instance in instances:
        if instance.strategies and strategy_name in instance.strategies:
            strategy_exists = True
            break
    
    if not strategy_exists:
        raise HTTPException(status_code=400, detail=f"Strategy '{strategy_name}' not found in any active instances")
    
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
    
    return {"message": f"Strategy monitor created for '{strategy_name}'", "id": monitor.id}

@app.put("/strategy-monitors/{monitor_id}")
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

@app.delete("/strategy-monitors/{monitor_id}")
async def delete_strategy_monitor(monitor_id: int, db: Session = Depends(get_db)):
    """Delete strategy monitor"""
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    strategy_name = monitor.strategy_name
    db.delete(monitor)
    db.commit()
    
    return {"message": f"Strategy monitor deleted for '{strategy_name}'"}

@app.post("/strategy-monitors/{monitor_id}/toggle")
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

@app.post("/strategy-monitors/{monitor_id}/test-report")
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

@app.get("/api/strategy-monitors")
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
