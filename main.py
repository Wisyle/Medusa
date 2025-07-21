from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
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

app = FastAPI(title="TGL Medusa Loggers - Advanced Crypto Bot Monitor", version="2.0.0")

templates = Jinja2Templates(directory="templates")

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

@app.post("/api/instances")
async def create_instance(
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create new bot instance"""
    
    strategy_list = [s.strip() for s in strategies.split(",") if s.strip()] if strategies else []
    
    instance = BotInstance(
        name=name,
        exchange=exchange,
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase if api_passphrase else None,
        strategies=strategy_list,
        polling_interval=polling_interval,
        webhook_url=webhook_url if webhook_url else None,
        telegram_bot_token=telegram_bot_token if telegram_bot_token else None,
        telegram_chat_id=telegram_chat_id if telegram_chat_id else None,
        telegram_topic_id=telegram_topic_id if telegram_topic_id else None
    )
    
    db.add(instance)
    db.commit()
    db.refresh(instance)
    
    return {"id": instance.id, "message": "Instance created successfully"}

@app.post("/api/instances/{instance_id}/start")
async def start_instance(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Start bot instance"""
    instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if instance_id in active_processes:
        raise HTTPException(status_code=400, detail="Instance already running")
    
    process = multiprocessing.Process(target=asyncio.run, args=(run_poller(instance_id),))
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
async def setup_2fa_page(request: Request, current_user: User = Depends(get_current_active_user)):
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

@app.on_event("startup")
async def startup_event():
    """Initialize database and start monitoring"""
    from migration import migrate_database
    migrate_database()
    init_db()
    
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
                        process = multiprocessing.Process(target=asyncio.run, args=(run_poller(instance.id),))
                        process.start()
                        active_processes[instance.id] = process
                    except Exception as e:
                        print(f"Failed to restart instance {instance.id}: {e}")
                
                elif not active_processes[instance.id].is_alive():
                    try:
                        del active_processes[instance.id]
                        process = multiprocessing.Process(target=asyncio.run, args=(run_poller(instance.id),))
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
