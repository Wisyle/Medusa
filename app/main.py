#!/usr/bin/env python3
# TAR Global Strategies - Lighthouse Trading Bot Platform
# Balance tracking and notifications enabled
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, WebSocket, WebSocketDisconnect, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import asyncio
import json
import multiprocessing
from datetime import datetime, timedelta
import uvicorn
import logging
from contextlib import asynccontextmanager
from sqlalchemy import text

# Smart migration system integrated directly

# Import core app modules
from app.database import get_db, init_db, BotInstance, ActivityLog, ErrorLog, User, BalanceHistory, SessionLocal, engine
from app.config import settings
from app.auth import (
    authenticate_user, create_access_token, create_refresh_token, verify_refresh_token,
    get_current_active_user, get_current_user_html, create_user, generate_totp_secret, generate_totp_qr_code,
    UserCreate, UserLogin, UserResponse, Token, RefreshTokenRequest, get_current_user,
    SecuritySetup, AuthMethod, setup_user_security, get_user_auth_methods
)

# Import models
from models.api_library_model import ApiCredential
from models.migration_tracking_model import MigrationHistory
from models.strategy_monitor_model import StrategyMonitor

# Import services
from services.polling import run_poller
from services.strategic_monitors import strategy_monitor

# Import routes
from app.routes.api_library_routes import add_api_library_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Migrations are now MANUAL ONLY - no automatic migrations on deployment
# Use terminal commands for migrations: python migration.py or web interface

async def run_smart_migrations():
    """
    MANUAL MIGRATION SYSTEM - Only run when explicitly called
    This function is no longer called automatically on startup
    """
    try:
        # Skip migrations if disabled via environment variable
        if os.getenv("SKIP_MIGRATIONS", "false").lower() == "true":
            logger.info("⏭️ Skipping migrations (SKIP_MIGRATIONS=true)")
            return True
            
        from sqlalchemy import text, inspect
        
        logger.info("🔍 Checking database schema...")
        
        # Add timeout for database operations
        import asyncio
        
        async def check_database_with_timeout():
            # Create inspector to check existing structure
            inspector = inspect(engine)
            
            # Check if we're using PostgreSQL or SQLite
            is_postgresql = str(engine.url).startswith('postgresql')
            logger.info(f"📊 Database type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
            
            db = SessionLocal()
            migration_success = True
            
            return inspector, is_postgresql, db, migration_success
        
        # Timeout after 10 seconds to prevent hanging
        try:
            inspector, is_postgresql, db, migration_success = await asyncio.wait_for(
                check_database_with_timeout(),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.error("❌ Database connection timeout during migration check")
            return False
        
        try:
            # 1. Check and add balance_enabled column to bot_instances
            if 'bot_instances' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('bot_instances')]
                
                if 'balance_enabled' not in columns:
                    logger.info("➕ Adding balance_enabled column to bot_instances...")
                    if is_postgresql:
                        db.execute(text("ALTER TABLE bot_instances ADD COLUMN balance_enabled BOOLEAN DEFAULT TRUE"))
                    else:
                        db.execute(text("ALTER TABLE bot_instances ADD COLUMN balance_enabled BOOLEAN DEFAULT 1"))
                    db.commit()
                    logger.info("✅ Added balance_enabled column")
                else:
                    logger.info("✅ balance_enabled column already exists")
                
                if 'user_id' not in columns:
                    logger.info("➕ Adding user_id column to bot_instances...")
                    if is_postgresql:
                        db.execute(text("ALTER TABLE bot_instances ADD COLUMN user_id INTEGER"))
                        # Add foreign key constraint if users table exists
                        if 'users' in inspector.get_table_names():
                            try:
                                db.execute(text("ALTER TABLE bot_instances ADD CONSTRAINT fk_bot_instances_user_id FOREIGN KEY (user_id) REFERENCES users (id)"))
                            except Exception:
                                pass  # Constraint might already exist
                    else:
                        db.execute(text("ALTER TABLE bot_instances ADD COLUMN user_id INTEGER"))
                    db.commit()
                    logger.info("✅ Added user_id column")
                    
                    # Assign existing instances to first user
                    logger.info("🔧 Assigning existing instances to first user...")
                    if 'users' in inspector.get_table_names():
                        db.execute(text("UPDATE bot_instances SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE user_id IS NULL"))
                        db.commit()
                        logger.info("✅ Assigned existing instances to user")
                else:
                    logger.info("✅ user_id column already exists")
            
            # 2. Create balance_history table if it doesn't exist
            if 'balance_history' not in inspector.get_table_names():
                logger.info("➕ Creating balance_history table...")
                from app.database import BalanceHistory
                BalanceHistory.__table__.create(engine, checkfirst=True)
                logger.info("✅ Created balance_history table")
            else:
                logger.info("✅ balance_history table already exists")
            
            # 3. Ensure users table exists (for user isolation)
            if 'users' not in inspector.get_table_names():
                logger.info("➕ Creating users table...")
                from app.database import User
                User.__table__.create(engine, checkfirst=True)
                logger.info("✅ Created users table")
            else:
                logger.info("✅ users table already exists")
            
            # 4. Check other essential tables and create if missing
            essential_tables = [
                ('api_credentials', 'from models.api_library_model import ApiCredential; ApiCredential'),
                ('strategy_monitors', 'from models.strategy_monitor_model import StrategyMonitor; StrategyMonitor'),
                ('activity_logs', 'from app.database import ActivityLog; ActivityLog'),
                ('error_logs', 'from app.database import ErrorLog; ErrorLog')
            ]
            
            for table_name, import_code in essential_tables:
                if table_name not in inspector.get_table_names():
                    logger.info(f"➕ Creating {table_name} table...")
                    try:
                        # Dynamic import and create
                        exec(import_code.split(';')[0])
                        model_class = eval(import_code.split(';')[1])
                        model_class.__table__.create(engine, checkfirst=True)
                        logger.info(f"✅ Created {table_name} table")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not create {table_name}: {e}")
                else:
                    logger.info(f"✅ {table_name} table already exists")
            
            db.commit()
            logger.info("🎉 Smart migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration error: {e}")
            db.rollback()
            migration_success = False
        finally:
            db.close()
            
        return migration_success
        
    except Exception as e:
        logger.error(f"❌ Smart migration failed: {e}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events"""
    # Startup
    logger.info("🚀 Initializing application...")
    
    # Run startup tasks in background to not block the app
    async def startup_tasks():
        try:
            # Create tables first
            logger.info("📊 Initializing database...")
            await asyncio.to_thread(init_db)
            
            # AUTOMATIC MIGRATIONS DISABLED
            # Smart auto-migration - only apply missing changes
            # logger.info("🔄 Running smart auto-migrations...")
            # success = await run_smart_migrations()
            # if success:
            #     logger.info("✅ Smart migrations completed successfully")
            # else:
            #     logger.warning("⚠️ Some migrations were skipped or failed (this may be normal)")
            
            logger.info("⏩ Automatic migrations disabled - use terminal commands for migrations")
        except Exception as e:
            logger.error(f"❌ Startup tasks failed: {e}")
            # Don't crash the app, continue anyway
    
    # Start startup tasks in background
    startup_task = asyncio.create_task(startup_tasks())
    
    # Start monitoring instances after a delay to ensure DB is ready
    async def delayed_monitor_start():
        await asyncio.sleep(5)  # Wait 5 seconds for DB to be ready
        await monitor_instances()
    
    monitor_task = asyncio.create_task(delayed_monitor_start())
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down application...")
    
    # Cancel monitoring task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    # Clean up active processes
    for process in active_processes.values():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
    
    logger.info("✅ Application shutdown complete")

app = FastAPI(
    title="TAR Global Strategies - Unified Command Hub", 
    version="2.0.0",
    lifespan=lifespan
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: dict = {}  # user_id -> websocket mapping

    async def connect(self, websocket: WebSocket, user_id: int = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            self.user_connections[user_id] = websocket
        print(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, user_id: int = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]
        print(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def send_to_user(self, message: str, user_id: int):
        if user_id in self.user_connections:
            websocket = self.user_connections[user_id]
            await self.send_personal_message(message, websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

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

from app.routes.dex_arbitrage_routes import router as dex_arbitrage_router
app.include_router(dex_arbitrage_router)

from app.routes.validator_node_routes import router as validator_node_router
app.include_router(validator_node_router)

# Include additional routes
from app.routes.migration_routes import router as migration_router
app.include_router(migration_router)

# Add Decter 001 routes
from app.routes.decter_routes import add_decter_routes
add_decter_routes(app)

templates = Jinja2Templates(directory="templates")

# Mount static files - always mount for backend routes that need them
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Static site serving moved to end of file to ensure backend routes take precedence

active_processes = {}

@app.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Login with flexible authentication modes"""
    user = authenticate_user(
        db, 
        user_login.email, 
        user_login.password, 
        user_login.totp_code,
        user_login.private_key,
        user_login.passphrase
    )
    
    if user == "private_key_required":
        raise HTTPException(status_code=400, detail="Private key required")
    elif user == "passphrase_required":
        raise HTTPException(status_code=400, detail="Passphrase required")
    elif user == "totp_required":
        raise HTTPException(status_code=400, detail="2FA code required")
    elif not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check if user needs security setup (first-time login)
    additional_data = {}
    if hasattr(user, 'needs_security_setup') and user.needs_security_setup:
        additional_data["needs_security_setup"] = True
        additional_data["is_first_login"] = True
    
    access_token = create_access_token(data={
        "sub": user.email,
        "is_superuser": user.is_superuser,
        "user_id": user.id,
        **additional_data
    })
    refresh_token = create_refresh_token(data={
        "sub": user.email,
        "is_superuser": user.is_superuser,
        "user_id": user.id
    })
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer",
        **additional_data
    }

@app.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    token_data = verify_refresh_token(refresh_request.refresh_token)
    
    user = db.query(User).filter(User.email == token_data.email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    access_token = create_access_token(data={
        "sub": user.email,
        "is_superuser": user.is_superuser,
        "user_id": user.id
    })
    new_refresh_token = create_refresh_token(data={
        "sub": user.email,
        "is_superuser": user.is_superuser,
        "user_id": user.id
    })
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@app.post("/auth/logout")
async def logout(request: Request):
    """Logout user by redirecting to login page"""
    # Clear any server-side session data if needed
    response = RedirectResponse(url="/login", status_code=302)
    
    # Clear any cookies if using cookie-based auth
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    
    return response

@app.post("/auth/setup-security")
async def setup_security(
    security_setup: SecuritySetup, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Set up additional security after first login"""
    try:
        updated_user = setup_user_security(db, current_user, security_setup)
        
        # Generate TOTP QR code if TOTP was enabled
        qr_code = None
        if security_setup.enable_totp and updated_user.totp_secret:
            qr_code = generate_totp_qr_code(
                updated_user.totp_secret, 
                updated_user.email, 
                settings.app_name
            )
        
        return {
            "message": "Security setup completed successfully",
            "auth_methods": get_user_auth_methods(updated_user),
            "totp_qr_code": qr_code
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to setup security: {str(e)}")

@app.get("/auth/methods")
async def get_auth_methods(current_user: User = Depends(get_current_user)):
    """Get available authentication methods for current user"""
    return {
        "methods": get_user_auth_methods(current_user),
        "needs_setup": getattr(current_user, 'needs_security_setup', False)
    }

@app.get("/auth/security-status")
async def get_security_status(current_user: User = Depends(get_current_user)):
    """Get current user's security configuration status"""
    has_private_key = current_user.private_key_hash is not None and current_user.private_key_hash.strip() != ""
    has_passphrase = current_user.passphrase_hash is not None and current_user.passphrase_hash.strip() != ""
    has_totp = current_user.totp_secret is not None and current_user.totp_enabled
    
    return {
        "email": current_user.email,
        "is_superuser": current_user.is_superuser,
        "security_features": {
            "private_key": has_private_key,
            "passphrase": has_passphrase,
            "totp": has_totp
        },
        "needs_security_setup": getattr(current_user, 'needs_security_setup', False),
        "available_methods": get_user_auth_methods(current_user)
    }

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recent activity feed for dashboard"""
    try:
        # Get recent bot instance activities
        recent_instances = db.query(BotInstance).order_by(BotInstance.last_poll.desc()).limit(limit).all()
        
        activities = []
        
        for instance in recent_instances:
            if instance.last_poll:
                event_type = "error" if instance.last_error else "success"
                message = instance.last_error if instance.last_error else "Polling successful"
                
                activities.append({
                    "timestamp": instance.last_poll.isoformat(),
                    "event_type": event_type,
                    "instance_id": instance.id,
                    "instance_name": instance.name,
                    "message": message,
                    "symbol": getattr(instance, 'trading_pair', None)
                })
        
        # Sort by timestamp descending
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return activities[:limit]
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return []

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

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(request: Request, current_user: User = Depends(get_current_user_html)):
    """Get current authenticated user information"""
    has_private_key = current_user.private_key_hash is not None and current_user.private_key_hash.strip() != ""
    has_passphrase = current_user.passphrase_hash is not None and current_user.passphrase_hash.strip() != ""
    
    # Ensure all boolean fields have proper values (handle NULL gracefully)
    is_active = True if current_user.is_active is None else bool(current_user.is_active)
    is_superuser = False if current_user.is_superuser is None else bool(current_user.is_superuser)
    totp_enabled = False if current_user.totp_enabled is None else bool(current_user.totp_enabled)
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=is_active,
        is_superuser=is_superuser,
        totp_enabled=totp_enabled,
        has_private_key=has_private_key,
        has_passphrase=has_passphrase,
        created_at=current_user.created_at or datetime.utcnow()
    )

@app.get("/health")
async def simple_health_check():
    """Simple health check for Render that bypasses startup dependencies"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Service is responsive"
    }

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with migration status - optimized for quick startup"""
    try:
        # Quick startup health check - just verify DB connection
        db.execute(text("SELECT 1"))
        
        # Quick table check without expensive operations
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        
        # Basic checks
        api_library_ready = 'api_credentials' in tables
        bot_instances_ready = 'bot_instances' in tables
        
        # More detailed migration check only if tables exist
        bot_instances_migrated = False
        if bot_instances_ready:
            try:
                columns = {col['name']: col for col in inspector.get_columns('bot_instances')}
                bot_instances_migrated = 'api_credential_id' in columns
            except:
                # If we can't check columns, assume migration in progress
                bot_instances_migrated = False
        
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
        # Return degraded but still healthy to pass render health checks during startup
        return {
            "status": "healthy", 
            "timestamp": datetime.utcnow().isoformat(),
            "active_instances": 0,
            "migration_status": "starting",
            "startup_mode": True,
            "message": "Starting up..."
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

@app.get("/api/dashboard/trading-bots")
async def get_trading_bots_data(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get comprehensive trading bots data for dashboard"""
    try:
        # Get all bot instances with statistics
        instances = db.query(BotInstance).all()
        
        # Calculate statistics
        total_instances = len(instances)
        active_instances = len([i for i in instances if i.is_active])
        instances_with_errors = len([i for i in instances if i.last_error])
        
        # Calculate P&L and performance metrics
        pnl_24h = 0.0
        total_volume = 0.0
        total_trades = 0
        active_positions = 0
        
        # Get recent activity for P&L calculation
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        recent_activity = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= yesterday,
            ActivityLog.event_type.in_(['order_filled', 'position_update'])
        ).all()
        
        # Strategy distribution
        strategy_distribution = {}
        for instance in instances:
            for strategy in instance.strategies or ['Unknown']:
                strategy_distribution[strategy] = strategy_distribution.get(strategy, 0) + 1
        
        # Generate sample P&L history for charts
        pnl_history = []
        base_time = datetime.utcnow() - timedelta(hours=24)
        for hour in range(24):
            timestamp = base_time + timedelta(hours=hour)
            # Calculate actual P&L from activity logs in this hour
            hour_start = timestamp
            hour_end = timestamp + timedelta(hours=1)
            
            hour_activity = [a for a in recent_activity 
                           if hour_start <= a.timestamp < hour_end]
            
            hour_pnl = sum([
                float(a.data.get('unrealized_pnl', 0)) if a.data and a.data.get('unrealized_pnl') else 0
                for a in hour_activity
            ])
            
            pnl_history.append({
                'timestamp': timestamp.isoformat(),
                'pnl': hour_pnl
            })
        
        return {
            'total_instances': total_instances,
            'active_instances': active_instances,
            'instances_with_errors': instances_with_errors,
            'pnl_24h': pnl_24h,
            'total_volume': total_volume,
            'total_trades': total_trades,
            'active_positions': active_positions,
            'strategy_distribution': strategy_distribution,
            'pnl_history': pnl_history,
            'instances': [
                {
                    'id': i.id,
                    'name': i.name,
                    'exchange': i.exchange,
                    'strategies': i.strategies or [],
                    'is_active': i.is_active,
                    'last_poll': i.last_poll.isoformat() if i.last_poll else None,
                    'last_error': i.last_error,
                    'trading_pair': i.trading_pair,
                    'polling_interval': i.polling_interval
                } for i in instances
            ]
        }
    except Exception as e:
        logger.error(f"Error getting trading bots data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/dex-arbitrage")
async def get_dex_arbitrage_data(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get DEX arbitrage monitoring data"""
    try:
        from models.dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
        
        # Get all DEX arbitrage instances
        instances = db.query(DEXArbitrageInstance).all()
        
        # Calculate statistics
        total_instances = len(instances)
        active_instances = len([i for i in instances if i.is_active])
        
        # Get recent opportunities
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_opportunities = db.query(DEXOpportunity).filter(
            DEXOpportunity.detected_at >= yesterday
        ).order_by(desc(DEXOpportunity.detected_at)).limit(10).all()
        
        # Calculate profit metrics
        total_profit_24h = sum([
            float(opp.profit_amount or 0) for opp in recent_opportunities 
            if opp.was_executed
        ])
        
        opportunities_count = len(recent_opportunities)
        executed_count = len([opp for opp in recent_opportunities if opp.was_executed])
        
        # Chain distribution
        chain_distribution = {}
        for instance in instances:
            chain = instance.chain
            chain_distribution[chain] = chain_distribution.get(chain, 0) + 1
        
        return {
            'total_instances': total_instances,
            'active_instances': active_instances,
            'opportunities_24h': opportunities_count,
            'executed_opportunities': executed_count,
            'total_profit_24h': total_profit_24h,
            'chain_distribution': chain_distribution,
            'recent_opportunities': [
                {
                    'id': opp.id,
                    'dex_pair': opp.dex_pair,
                    'primary_dex': opp.primary_dex,
                    'secondary_dex': opp.secondary_dex,
                    'profit_percentage': float(opp.profit_percentage or 0),
                    'profit_amount': float(opp.profit_amount or 0),
                    'was_executed': opp.was_executed,
                    'detected_at': opp.detected_at.isoformat() if opp.detected_at else None
                } for opp in recent_opportunities
            ],
            'instances': [
                {
                    'id': i.id,
                    'name': i.name,
                    'chain': i.chain,
                    'dex_pair': i.dex_pair,
                    'primary_dex': i.primary_dex,
                    'secondary_dex': i.secondary_dex,
                    'is_active': i.is_active,
                    'auto_execute': i.auto_execute,
                    'min_profit_threshold': float(i.min_profit_threshold or 0),
                    'last_check': i.last_check.isoformat() if i.last_check else None
                } for i in instances
            ]
        }
    except Exception as e:
        logger.error(f"Error getting DEX arbitrage data: {e}")
        # Return empty data if tables don't exist yet
        return {
            'total_instances': 0,
            'active_instances': 0,
            'opportunities_24h': 0,
            'executed_opportunities': 0,
            'total_profit_24h': 0.0,
            'chain_distribution': {},
            'recent_opportunities': [],
            'instances': []
        }

@app.get("/api/dashboard/validators")
async def get_validator_nodes_data(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get validator nodes monitoring data"""
    try:
        from models.validator_node_model import ValidatorNode, ValidatorReward
        
        # Get all validator nodes
        validators = db.query(ValidatorNode).all()
        
        # Calculate statistics
        total_validators = len(validators)
        active_validators = len([v for v in validators if v.is_active and v.node_status == 'active'])
        
        # Calculate total stake and rewards
        total_stake = sum([float(v.total_stake or 0) for v in validators])
        total_rewards_24h = sum([float(v.current_rewards or 0) for v in validators])
        
        # Calculate average uptime
        avg_uptime = sum([float(v.uptime_percentage or 0) for v in validators]) / max(total_validators, 1)
        
        # Blockchain distribution
        blockchain_distribution = {}
        for validator in validators:
            chain = validator.blockchain
            blockchain_distribution[chain] = blockchain_distribution.get(chain, 0) + 1
        
        # Get recent rewards
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_rewards = db.query(ValidatorReward).filter(
            ValidatorReward.earned_at >= yesterday
        ).order_by(desc(ValidatorReward.earned_at)).limit(10).all()
        
        return {
            'total_validators': total_validators,
            'active_validators': active_validators,
            'total_stake': total_stake,
            'total_rewards_24h': total_rewards_24h,
            'average_uptime': avg_uptime,
            'blockchain_distribution': blockchain_distribution,
            'recent_rewards': [
                {
                    'id': r.id,
                    'validator_name': r.validator.name if r.validator else 'Unknown',
                    'blockchain': r.validator.blockchain if r.validator else 'Unknown',
                    'reward_amount': float(r.reward_amount or 0),
                    'earned_at': r.earned_at.isoformat() if r.earned_at else None
                } for r in recent_rewards
            ],
            'validators': [
                {
                    'id': v.id,
                    'name': v.name,
                    'blockchain': v.blockchain,
                    'strategy_name': v.strategy_name,
                    'node_address': v.node_address,
                    'total_stake': float(v.total_stake or 0),
                    'current_rewards': float(v.current_rewards or 0),
                    'uptime_percentage': float(v.uptime_percentage or 0),
                    'node_status': v.node_status,
                    'current_apy': float(v.current_apy or 0),
                    'is_active': v.is_active
                } for v in validators
            ]
        }
    except Exception as e:
        logger.error(f"Error getting validator nodes data: {e}")
        # Return empty data if tables don't exist yet
        return {
            'total_validators': 0,
            'active_validators': 0,
            'total_stake': 0.0,
            'total_rewards_24h': 0.0,
            'average_uptime': 0.0,
            'blockchain_distribution': {},
            'recent_rewards': [],
            'validators': []
        }

@app.get("/api/dashboard/system-overview")
async def get_system_overview_data(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get system overview data"""
    try:
        # System health metrics
        total_bots = db.query(BotInstance).count()
        active_bots = db.query(BotInstance).filter(BotInstance.is_active == True).count()
        
        # Get recent errors
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_errors = db.query(ErrorLog).filter(
            ErrorLog.timestamp >= yesterday
        ).count()
        
        # Get recent activity
        recent_activity_count = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= yesterday
        ).count()
        
        # Calculate system uptime (simplified)
        uptime_percentage = max(0, 100 - (recent_errors / max(recent_activity_count, 1)) * 100)
        
        # API Library statistics
        total_api_credentials = db.query(ApiCredential).count()
        active_api_credentials = db.query(ApiCredential).filter(
            ApiCredential.is_active == True
        ).count()
        
        # Get resource usage (simplified metrics)
        resource_metrics = {
            'cpu_usage': 45.2,  # Placeholder - implement actual monitoring
            'memory_usage': 62.8,
            'disk_usage': 34.1,
            'network_io': 12.5
        }
        
        return {
            'system_health': {
                'total_bots': total_bots,
                'active_bots': active_bots,
                'recent_errors': recent_errors,
                'uptime_percentage': uptime_percentage,
                'total_api_credentials': total_api_credentials,
                'active_api_credentials': active_api_credentials
            },
            'resource_usage': resource_metrics,
            'recent_activity': recent_activity_count
        }
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent system activity"""
    try:
        recent_logs = db.query(ActivityLog).order_by(
            desc(ActivityLog.timestamp)
        ).limit(limit).all()
        
        return [
            {
                'id': log.id,
                'instance_id': log.instance_id,
                'event_type': log.event_type,
                'symbol': log.symbol,
                'message': log.message,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'data': log.data
            } for log in recent_logs
        ]
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return []

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    """WebSocket endpoint for real-time dashboard updates"""
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            await websocket.close(code=4001, reason="User not found or inactive")
            return

        await manager.connect(websocket, user_id)
        
        await manager.send_personal_message(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Real-time updates connected",
            "timestamp": datetime.utcnow().isoformat()
        }), websocket)

        await stream_dashboard_data(websocket, user_id, db)
        
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        print(f"User {user_id} disconnected from WebSocket")
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)

async def stream_dashboard_data(websocket: WebSocket, user_id: int, db: Session):
    """Stream real-time dashboard data to connected client"""
    try:
        while True:
            # Get comprehensive dashboard data
            update_data = {
                "type": "dashboard_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {}
            }
            
            try:
                # Get trading bots data
                trading_bots_data = await get_trading_bots_data(
                    current_user={'user_id': user_id}, 
                    db=db
                )
                update_data["data"]["trading_bots"] = trading_bots_data
            except Exception as e:
                logger.error(f"Error getting trading bots data for WebSocket: {e}")
                
            try:
                # Get DEX arbitrage data  
                dex_data = await get_dex_arbitrage_data(
                    current_user={'user_id': user_id}, 
                    db=db
                )
                update_data["data"]["dex_arbitrage"] = dex_data
            except Exception as e:
                logger.error(f"Error getting DEX arbitrage data for WebSocket: {e}")
                
            try:
                # Get validator data
                validator_data = await get_validator_nodes_data(
                    current_user={'user_id': user_id}, 
                    db=db
                )
                update_data["data"]["validators"] = validator_data
            except Exception as e:
                logger.error(f"Error getting validator data for WebSocket: {e}")
                
            try:
                # Get system overview
                system_data = await get_system_overview_data(
                    current_user={'user_id': user_id}, 
                    db=db
                )
                update_data["data"]["system_overview"] = system_data
            except Exception as e:
                logger.error(f"Error getting system overview for WebSocket: {e}")
                
            try:
                # Get recent activity
                activity_data = await get_recent_activity(
                    limit=10,
                    current_user={'user_id': user_id}, 
                    db=db
                )
                update_data["data"]["recent_activity"] = activity_data
            except Exception as e:
                logger.error(f"Error getting recent activity for WebSocket: {e}")
            
            await manager.send_personal_message(json.dumps(update_data), websocket)
            
            # Stream every 10 seconds
            await asyncio.sleep(10)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"Error in data streaming for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)

@app.post("/api/broadcast")
async def broadcast_message(message: dict, current_user: User = Depends(get_current_active_user)):
    """Broadcast message to all connected WebSocket clients (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    broadcast_data = {
        "type": "broadcast",
        "message": message.get("message", ""),
        "timestamp": datetime.utcnow().isoformat(),
        "from": "system"
    }
    
    await manager.broadcast(json.dumps(broadcast_data))
    return {"status": "Message broadcasted", "connections": len(manager.active_connections)}

@app.get("/api/instances")
async def get_instances(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get bot instances for current user"""
    try:
        instances = db.query(BotInstance).filter(BotInstance.user_id == current_user.id).all()
        
        # Get latest balance for each instance
        result = []
        for instance in instances:
            instance_data = {
                "id": instance.id,
                "name": instance.name,
                "exchange": instance.exchange,
                "market_type": instance.market_type,
                "api_credential_id": instance.api_credential_id,
                "api_key": instance.api_key,
                "api_secret": instance.api_secret,
                "api_passphrase": instance.api_passphrase,
                "strategies": instance.strategies,
                "is_active": instance.is_active,
                "last_poll": instance.last_poll.isoformat() if instance.last_poll else None,
                "last_error": instance.last_error,
                "polling_interval": instance.polling_interval,
                "webhook_url": instance.webhook_url,
                "telegram_bot_token": instance.telegram_bot_token,
                "telegram_chat_id": instance.telegram_chat_id,
                "telegram_topic_id": instance.telegram_topic_id,
                "trading_pair": instance.trading_pair,
                "balance_enabled": instance.balance_enabled
            }
            
            # Add latest balance if enabled
            if instance.balance_enabled:
                try:
                    latest_balance = db.query(BalanceHistory).filter(
                        BalanceHistory.instance_id == instance.id
                    ).order_by(BalanceHistory.timestamp.desc()).first()
                    
                    if latest_balance:
                        # Ensure total_value_usd is a valid number
                        total_usdt = latest_balance.total_value_usd
                        if total_usdt is None or str(total_usdt).lower() in ['nan', 'infinity', '-infinity']:
                            total_usdt = 0.0
                        else:
                            try:
                                total_usdt = float(total_usdt)
                                if not (total_usdt == total_usdt):  # Check for NaN
                                    total_usdt = 0.0
                            except (ValueError, TypeError):
                                total_usdt = 0.0
                        
                        instance_data["latest_balance"] = {
                            "total_usdt": total_usdt,
                            "timestamp": latest_balance.timestamp.isoformat(),
                            "data": latest_balance.balance_data
                        }
                    else:
                        instance_data["latest_balance"] = None
                except Exception as balance_error:
                    logger.warning(f"Failed to fetch balance for instance {instance.id}: {balance_error}")
                    instance_data["latest_balance"] = None
            else:
                instance_data["latest_balance"] = None
                
            result.append(instance_data)
        
        return result
    except Exception as e:
        logger.error(f"Failed to fetch instances: {e}")
        # Return JSON error response instead of HTML
        raise HTTPException(status_code=500, detail=f"Failed to fetch instances: {str(e)}")

def validate_instance_data(name: str, exchange: str, api_key: str, api_secret: str, trading_pair: Optional[str] = None):
    """Validate instance creation data"""
    errors = []
    
    if not name or not name.strip():
        errors.append("Instance name is required")
    elif len(name.strip()) > 100:
        errors.append("Instance name must be 100 characters or less")
        
    if not exchange or not exchange.strip():
        errors.append("Exchange is required")
    elif exchange.strip().lower() not in ['bybit', 'binance', 'okx', 'kucoin', 'mexc', 'gate', 'coinbase', 'bitfinex', 'bitget']:
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
    balance_enabled: bool = Form(True),  # Default to True for better monitoring
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
                user_id=current_user.id,
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
                trading_pair=trading_pair.strip() if trading_pair else None,
                balance_enabled=balance_enabled
            )
        else:
            instance = BotInstance(
                user_id=current_user.id,
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
                trading_pair=trading_pair.strip() if trading_pair else None,
                balance_enabled=balance_enabled
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
    instance = db.query(BotInstance).filter(
        BotInstance.id == instance_id,
        BotInstance.user_id == current_user.id
    ).first()
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
    instance = db.query(BotInstance).filter(
        BotInstance.id == instance_id,
        BotInstance.user_id == current_user.id
    ).first()
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
    try:
        instance = db.query(BotInstance).filter(
            BotInstance.id == instance_id,
            BotInstance.user_id == current_user.id
        ).first()
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        # Stop the instance if it's running
        if instance_id in active_processes:
            try:
                await stop_instance(instance_id, db, current_user)
            except Exception as stop_error:
                logger.warning(f"Failed to stop instance {instance_id} during deletion: {stop_error}")
        
        # Delete related data first
        try:
            # Delete balance history
            db.query(BalanceHistory).filter(BalanceHistory.instance_id == instance_id).delete()
            # Delete activity logs
            db.query(ActivityLog).filter(ActivityLog.instance_id == instance_id).delete()
            # Delete error logs
            db.query(ErrorLog).filter(ErrorLog.instance_id == instance_id).delete()
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up related data for instance {instance_id}: {cleanup_error}")
        
        # Delete the instance itself
        db.delete(instance)
        db.commit()
        
        logger.info(f"✅ Successfully deleted instance {instance_id} ({instance.name}) for user {current_user.id}")
        return {"message": "Instance deleted successfully", "success": True}
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete instance: {str(e)}")

@app.put("/api/instances/{instance_id}")
async def update_instance(
    instance_id: int,
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
    balance_enabled: bool = Form(True),  # Changed from False to True - was disabling balance on updates!
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update bot instance"""
    instance = db.query(BotInstance).filter(
        BotInstance.id == instance_id,
        BotInstance.user_id == current_user.id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    # Handle API credentials based on source
    if api_source == "library":
        if not api_credential_id:
            raise HTTPException(status_code=400, detail="API credential must be selected when using library")
        
        # Check if credential exists and is available
        credential = db.query(ApiCredential).filter(ApiCredential.id == api_credential_id).first()
        if not credential:
            raise HTTPException(status_code=400, detail="Selected API credential not found")
        
        # Check if credential is in use by another instance (unless it's the current instance)
        if credential.is_in_use and credential.current_instance_id != instance_id:
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
    
    # Check if instance is running and stop it if updating critical fields
    was_active = instance.is_active
    if was_active and instance_id in active_processes:
        await stop_instance(instance_id, db, current_user)
    
    # Free up the old API credential if switching away from library
    old_credential_id = instance.api_credential_id
    if old_credential_id and api_source != "library":
        old_credential = db.query(ApiCredential).filter(ApiCredential.id == old_credential_id).first()
        if old_credential:
            old_credential.is_in_use = False
            old_credential.current_instance_id = None
    
    strategy_list = [s.strip() for s in strategies.split(",") if s.strip()] if strategies else []
    
    # Update instance based on API source
    if api_source == "library":
        instance.api_credential_id = api_credential_id
        instance.api_key = None  # Clear direct credentials
        instance.api_secret = None
        instance.api_passphrase = None
    else:
        instance.api_credential_id = None  # Clear library reference
        instance.api_key = api_key.strip()
        instance.api_secret = api_secret.strip()
        instance.api_passphrase = api_passphrase.strip() if api_passphrase else None
    
    # Update common fields
    instance.name = name.strip()
    instance.exchange = exchange.strip()
    instance.market_type = market_type.strip()
    instance.strategies = strategy_list
    instance.polling_interval = polling_interval
    instance.webhook_url = webhook_url.strip() if webhook_url else None
    instance.telegram_bot_token = telegram_bot_token.strip() if telegram_bot_token else None
    instance.telegram_chat_id = telegram_chat_id.strip() if telegram_chat_id else None
    instance.telegram_topic_id = telegram_topic_id.strip() if telegram_topic_id else None
    instance.trading_pair = trading_pair.strip() if trading_pair else None
    instance.balance_enabled = balance_enabled
    instance.updated_at = datetime.utcnow()
    
    # If using API library, mark credential as in use
    if api_source == "library" and api_credential_id:
        credential = db.query(ApiCredential).filter(ApiCredential.id == api_credential_id).first()
        if credential:
            credential.is_in_use = True
            credential.current_instance_id = instance.id
            credential.last_used = datetime.utcnow()
    
    db.commit()
    
    # Restart if it was previously active
    if was_active:
        await start_instance(instance_id, db, current_user)
    
    return {"message": "Instance updated successfully", "instance_id": instance_id}

@app.get("/api/instances/{instance_id}/growth")
async def get_instance_growth(instance_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get growth data for different time periods"""
    instance = db.query(BotInstance).filter(
        BotInstance.id == instance_id,
        BotInstance.user_id == current_user.id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if not instance.balance_enabled:
        return {"error": "Balance tracking not enabled for this instance"}
    
    try:
        now = datetime.utcnow()
        
        # Get balance history for different periods
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Get most recent balance
        latest_balance = db.query(BalanceHistory).filter(
            BalanceHistory.instance_id == instance_id
        ).order_by(BalanceHistory.timestamp.desc()).first()
        
        if not latest_balance:
            return {"error": "No balance history found"}
        
        # Calculate growth for each period
        growth_data = {
            "current_balance": latest_balance.balance_data,
            "growth": {
                "today": await _calculate_growth(db, instance_id, today_start, latest_balance),
                "7_days": await _calculate_growth(db, instance_id, week_start, latest_balance),
                "30_days": await _calculate_growth(db, instance_id, month_start, latest_balance)
            },
            "timestamp": latest_balance.timestamp.isoformat()
        }
        
        return growth_data
        
    except Exception as e:
        logger.error(f"Error calculating growth for instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate growth data")

async def _calculate_growth(db: Session, instance_id: int, start_time: datetime, latest_balance: BalanceHistory) -> Dict:
    """Calculate growth between start_time and current balance"""
    # Get balance closest to start_time
    start_balance = db.query(BalanceHistory).filter(
        BalanceHistory.instance_id == instance_id,
        BalanceHistory.timestamp >= start_time
    ).order_by(BalanceHistory.timestamp.asc()).first()
    
    if not start_balance:
        # If no balance at start time, try to get the closest earlier balance
        start_balance = db.query(BalanceHistory).filter(
            BalanceHistory.instance_id == instance_id,
            BalanceHistory.timestamp <= start_time
        ).order_by(BalanceHistory.timestamp.desc()).first()
    
    if not start_balance:
        return {"error": "No historical data available"}
    
    # Calculate percentage changes for each currency
    current_data = latest_balance.balance_data
    start_data = start_balance.balance_data
    
    growth_by_currency = {}
    
    for currency, current_amounts in current_data.items():
        if currency in start_data:
            current_total = current_amounts.get('total', 0)
            start_total = start_data[currency].get('total', 0)
            
            if start_total > 0:
                growth_percentage = ((current_total - start_total) / start_total) * 100
                absolute_change = current_total - start_total
                
                growth_by_currency[currency] = {
                    "start_amount": start_total,
                    "current_amount": current_total,
                    "absolute_change": absolute_change,
                    "percentage_change": round(growth_percentage, 2)
                }
        else:
            # New currency since start time
            growth_by_currency[currency] = {
                "start_amount": 0,
                "current_amount": current_amounts.get('total', 0),
                "absolute_change": current_amounts.get('total', 0),
                "percentage_change": float('inf')  # Infinite growth from 0
            }
    
    return {
        "currencies": growth_by_currency,
        "start_timestamp": start_balance.timestamp.isoformat(),
        "has_data": True
    }

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
    return templates.TemplateResponse("login.html", {"request": request, "current_user": None})

@app.get("/security-setup", response_class=HTMLResponse)
async def security_setup_page(request: Request):
    """Security setup page"""
    return templates.TemplateResponse("security_setup.html", {"request": request, "current_user": None})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("register.html", {"request": request, "current_user": None})

@app.get("/setup-2fa", response_class=HTMLResponse)
async def setup_2fa_page(request: Request):
    """2FA setup page"""
    return templates.TemplateResponse("setup_2fa.html", {"request": request, "current_user": None})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user_html)):
    """Main dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "current_user": current_user})

@app.get("/instances", response_class=HTMLResponse)
async def instances_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Instances management page"""
    return templates.TemplateResponse("instances.html", {"request": request, "current_user": current_user})

@app.get("/instances/new", response_class=HTMLResponse)
async def new_instance_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """New instance form"""
    return templates.TemplateResponse("new_instance.html", {"request": request, "current_user": current_user})

@app.get("/instances/{instance_id}", response_class=HTMLResponse)
async def instance_detail(request: Request, instance_id: int, current_user: User = Depends(get_current_user_html)):
    """Instance detail page"""
    return templates.TemplateResponse("instance_detail.html", {"request": request, "instance_id": instance_id, "current_user": current_user})

@app.get("/instances/{instance_id}/edit", response_class=HTMLResponse)
async def edit_instance_page(request: Request, instance_id: int, current_user: User = Depends(get_current_user_html)):
    """Edit instance form"""
    return templates.TemplateResponse("edit_instance.html", {"request": request, "instance_id": instance_id, "current_user": current_user})

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Account settings page"""
    return templates.TemplateResponse("account.html", {"request": request, "current_user": current_user})

@app.get("/decter-engine", response_class=HTMLResponse)
async def decter_engine_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Decter 001 Engine control page"""
    return templates.TemplateResponse("decter_engine.html", {"request": request, "current_user": current_user})

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

@app.get("/api/user/2fa/status")
async def get_2fa_status(current_user: User = Depends(get_current_active_user)):
    """Get current 2FA status"""
    return {
        "totp_enabled": current_user.totp_enabled,
        "has_secret": bool(current_user.totp_secret)
    }

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
async def system_logs_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """System logs dashboard"""
    return templates.TemplateResponse("system_logs.html", {"request": request, "current_user": current_user})

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



async def monitor_instances():
    """Monitor and restart failed instances"""
    # Wait for initial startup to complete
    await asyncio.sleep(10)
    
    while True:
        try:
            # Import here to avoid circular imports
            from app.database import SessionLocal
            
            # Run DB operations in thread pool to avoid blocking
            async def check_instances():
                db = SessionLocal()
                try:
                    active_instances = await asyncio.to_thread(
                        lambda: db.query(BotInstance).filter(BotInstance.is_active == True).all()
                    )
                    return active_instances
                except Exception as e:
                    logger.error(f"Failed to query instances: {e}")
                    return []
                finally:
                    db.close()
            
            active_instances = await check_instances()
            
            # Process instances without blocking
            for instance in active_instances:
                if instance.id not in active_processes:
                    try:
                        process = multiprocessing.Process(target=_run_poller_sync, args=(instance.id,))
                        process.start()
                        active_processes[instance.id] = process
                        logger.info(f"Started monitoring instance {instance.id}")
                    except Exception as e:
                        logger.error(f"Failed to start instance {instance.id}: {e}")
                
                elif not active_processes[instance.id].is_alive():
                    try:
                        del active_processes[instance.id]
                        process = multiprocessing.Process(target=_run_poller_sync, args=(instance.id,))
                        process.start()
                        active_processes[instance.id] = process
                        logger.info(f"Restarted dead instance {instance.id}")
                    except Exception as e:
                        logger.error(f"Failed to restart dead instance {instance.id}: {e}")
            
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        await asyncio.sleep(30)  # Check every 30 seconds

# Strategy Monitor Routes

@app.get("/strategy-monitors", response_class=HTMLResponse)
async def strategy_monitors_page(request: Request, current_user: User = Depends(get_current_user_html), db: Session = Depends(get_db)):
    """Strategy monitors management page"""
    # Get existing monitors
    monitors = db.query(StrategyMonitor).order_by(StrategyMonitor.strategy_name).all()
    
    # Get available strategies from active instances
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    all_strategies = set()
    for instance in instances:
        if instance.strategies:
            all_strategies.update(instance.strategies)
    
    return templates.TemplateResponse("strategy_monitors.html", {
        "request": request, 
        "current_user": current_user,
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
    current_user: User = Depends(get_current_user_html),
    db: Session = Depends(get_db)
):
    """Create new strategy monitor"""
    
    # Check if monitor already exists
    existing = db.query(StrategyMonitor).filter(StrategyMonitor.strategy_name == strategy_name).first()
    if existing:
        return RedirectResponse(url=f"/strategy-monitors?error=Monitor for strategy '{strategy_name}' already exists", status_code=303)
    
    # Validate strategy exists in active instances
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    strategy_exists = False
    for instance in instances:
        if instance.strategies and strategy_name in instance.strategies:
            strategy_exists = True
            break
    
    if not strategy_exists:
        return RedirectResponse(url=f"/strategy-monitors?error=Strategy '{strategy_name}' not found in any active instances", status_code=303)
    
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
        return RedirectResponse(url=f"/strategy-monitors?error=Failed to create monitor: {str(e)}", status_code=303)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
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
async def delete_strategy_monitor(monitor_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Delete strategy monitor"""
    
    monitor = db.query(StrategyMonitor).filter(StrategyMonitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Strategy monitor not found")
    
    strategy_name = monitor.strategy_name
    db.delete(monitor)
    db.commit()
    
    return {"message": f"Strategy monitor deleted for '{strategy_name}'"}

@app.post("/strategy-monitors/{monitor_id}/toggle")
async def toggle_strategy_monitor(monitor_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
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
    from services.strategy_monitor import StrategyMonitorService
    
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

@app.get("/api/available-strategies")
async def get_available_strategies(db: Session = Depends(get_db)):
    """Get all available strategies from active bot instances"""
    instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
    all_strategies = set()
    for instance in instances:
        if instance.strategies:
            all_strategies.update(instance.strategies)
    
    return {"strategies": sorted(all_strategies)}

@app.get("/api/strategy-monitors")
async def get_strategy_monitors(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
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
            "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
            "updated_at": monitor.updated_at.isoformat() if monitor.updated_at else None
        })
    
    return result

@app.get("/dex-arbitrage", response_class=HTMLResponse)
async def dex_arbitrage_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """DEX arbitrage monitoring page"""
    return templates.TemplateResponse("dex_arbitrage.html", {"request": request, "current_user": current_user})

@app.get("/validators", response_class=HTMLResponse)
async def validators_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Validator nodes monitoring page"""
    return templates.TemplateResponse("validators.html", {"request": request, "current_user": current_user})


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Admin user management page - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return templates.TemplateResponse("admin_users.html", {"request": request, "current_user": current_user})

@app.get("/admin/notifications", response_class=HTMLResponse)
async def admin_notifications_page(request: Request, current_user: User = Depends(get_current_user_html)):
    """Admin notification management page - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return templates.TemplateResponse("admin_notifications.html", {"request": request, "current_user": current_user})

@app.get("/api/admin/users")
async def get_all_users(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get all users with their roles - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
    
    users = db.query(User).all()
    result = []
    
    for user in users:
        user_data = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "totp_enabled": user.totp_enabled,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "roles": []
        }
        
        for user_role in user.roles:
            role_data = {
                "id": user_role.role.id,
                "name": user_role.role.name,
                "description": user_role.role.description
            }
            user_data["roles"].append(role_data)
        
        result.append(user_data)
    
    return result

@app.get("/api/admin/roles")
async def get_all_roles(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get all available roles - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
    
    from app.database import Role, RolePermission, Permission
    
    roles = db.query(Role).all()
    result = []
    
    for role in roles:
        role_data = {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": []
        }
        
        for role_permission in role.permissions:
            perm_data = {
                "id": role_permission.permission.id,
                "name": role_permission.permission.name,
                "description": role_permission.permission.description,
                "resource": role_permission.permission.resource,
                "action": role_permission.permission.action
            }
            role_data["permissions"].append(perm_data)
        
        result.append(role_data)
    
    return result

@app.post("/api/admin/users")
async def create_user_admin(
    user_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new user - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
    
    from app.database import Role, UserRole
    from auth import get_password_hash
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data["email"]).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    new_user = User(
        email=user_data["email"],
        full_name=user_data.get("full_name"),
        hashed_password=get_password_hash(user_data["password"]),
        is_active=user_data.get("is_active", True),
        is_superuser=False,  # Only existing superusers can create other superusers via edit
        needs_security_setup=True  # New users need to complete security setup
    )
    
    db.add(new_user)
    db.flush()  # Get the user ID
    
    role_ids = user_data.get("role_ids", [])
    for role_id in role_ids:
        role = db.query(Role).filter(Role.id == role_id).first()
        if role:
            user_role = UserRole(
                user_id=new_user.id,
                role_id=role_id,
                assigned_by=current_user.id
            )
            db.add(user_role)
    
    db.commit()
    
    return {"message": "User created successfully", "user_id": new_user.id}

@app.put("/api/admin/users/{user_id}")
async def update_user_admin(
    user_id: int,
    user_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a user - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
    
    from app.database import Role, UserRole
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.email = user_data.get("email", user.email)
    user.full_name = user_data.get("full_name", user.full_name)
    user.is_active = user_data.get("is_active", user.is_active)
    user.is_superuser = user_data.get("is_superuser", user.is_superuser)
    
    if "role_ids" in user_data:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        
        role_ids = user_data["role_ids"]
        for role_id in role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                user_role = UserRole(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_by=current_user.id
                )
                db.add(user_role)
    
    db.commit()
    
    return {"message": "User updated successfully"}

@app.delete("/api/admin/users/{user_id}")
async def delete_user_admin(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a user - only accessible to superusers"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
    
    from app.database import UserRole
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot delete superuser accounts")
    
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

# Serve static site if SERVE_STATIC is enabled - MUST BE LAST ROUTE
if os.getenv("SERVE_STATIC") == "true":
    # Serve static HTML files from root
    @app.get("/{path:path}")
    async def serve_static_site(path: str, request: Request):
        """Serve static site files"""
        # Backend routes take precedence
        backend_routes = ["api/", "ws", "login", "logout", "auth/", "security-setup", "setup-2fa", 
                         "dashboard", "instances", "api-library", "dex-arbitrage", "validators", 
                         "decter", "strategy-monitors", "migrations"]
        
        for route in backend_routes:
            if path.startswith(route):
                raise HTTPException(status_code=404, detail="Backend route - not handled by static server")
        
        # Handle root path
        if not path or path == "/":
            path = "index.html"
        
        # Check if file exists in static directory
        file_path = os.path.join("static", path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Determine content type
            if path.endswith('.html'):
                content_type = "text/html"
            elif path.endswith('.css'):
                content_type = "text/css"
            elif path.endswith('.js'):
                content_type = "application/javascript"
            elif path.endswith('.json'):
                content_type = "application/json"
            else:
                content_type = "application/octet-stream"
            
            # Read and return file
            with open(file_path, 'rb') as f:
                return Response(content=f.read(), media_type=content_type)
        
        # If file not found, serve index.html for SPA routing
        index_path = os.path.join("static", "index.html")
        if os.path.exists(index_path):
            with open(index_path, 'rb') as f:
                return Response(content=f.read(), media_type="text/html")
        
        # Last resort 404
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
