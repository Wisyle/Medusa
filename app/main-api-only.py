#!/usr/bin/env python3
# TAR Global Strategies - API-Only Backend
# Optimized for static site frontend
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import uvicorn

# Import core app modules
from app.database import get_db, init_db, BotInstance, ActivityLog, ErrorLog, User, BalanceHistory, SessionLocal, engine
from app.config import settings
from app.auth import (
    authenticate_user, create_access_token, create_refresh_token, verify_refresh_token,
    get_current_active_user, create_user, get_current_user,
    UserCreate, UserLogin, UserResponse, Token, RefreshTokenRequest
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events"""
    logger.info("🚀 TAR Global Strategies API starting up...")
    
    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    # Start background tasks
    try:
        # You can add startup tasks here
        logger.info("✅ Background services ready")
    except Exception as e:
        logger.error(f"❌ Background service startup failed: {e}")
    
    yield
    
    logger.info("🛑 TAR Global Strategies API shutting down...")
    logger.info("✅ API shutdown complete")

# Create FastAPI app (API only)
app = FastAPI(
    title="TAR Global Strategies API", 
    version="2.0.0",
    description="API-only backend for TAR Global Strategies static site",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, user_id: int = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
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
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# CORS configuration for static site
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://tar-strategies-frontend.onrender.com",
    os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
]

# Flatten the list and remove empty strings
allowed_origins = [origin.strip() for sublist in allowed_origins for origin in (sublist if isinstance(sublist, list) else [sublist]) if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add API Library routes
add_api_library_routes(app)

# Include additional routes
from app.routes.dex_arbitrage_routes import router as dex_arbitrage_router
app.include_router(dex_arbitrage_router, prefix="/api")

from app.routes.validator_node_routes import router as validator_node_router
app.include_router(validator_node_router, prefix="/api")

from app.routes.migration_routes import router as migration_router
app.include_router(migration_router, prefix="/api")

# Add Decter routes
from app.routes.decter_routes import add_decter_routes
add_decter_routes(app)

# Strategy Monitor routes
from app.routes.strategy_monitor_routes import router as strategy_monitor_router
app.include_router(strategy_monitor_router, prefix="/api")

# API-only routes (no HTML templates)

@app.post("/api/auth/login", response_model=Token)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT tokens"""
    try:
        user = authenticate_user(
            db, 
            user_login.email, 
            user_login.password,
            user_login.totp_code,
            user_login.private_key,
            user_login.passphrase
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email, password, or authentication factors",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        logger.info(f"✅ User logged in: {user.email}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                totp_enabled=user.totp_enabled
            )
        }
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        email = verify_refresh_token(refresh_request.refresh_token)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        access_token = create_access_token(data={"sub": user.email})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_request.refresh_token,  # Keep the same refresh token
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"❌ Token refresh error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get dashboard statistics for the current user"""
    try:
        # Get user's instances
        instances = db.query(BotInstance).filter(BotInstance.user_id == current_user.id).all()
        
        total_instances = len(instances)
        active_instances = len([i for i in instances if i.is_active])
        
        # Calculate total balance (mock data for now)
        total_balance = sum([10000 + (i.id * 1000) for i in instances])  # Mock calculation
        
        # Calculate daily P&L (mock data)
        daily_pnl = total_balance * 0.02  # 2% daily return (mock)
        
        # Win rate (mock)
        win_rate = 75.5
        
        return {
            "total_instances": total_instances,
            "active_instances": active_instances,
            "total_balance": total_balance,
            "daily_pnl": daily_pnl,
            "win_rate": win_rate,
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving dashboard statistics")

@app.get("/api/instances")
async def get_instances(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get all bot instances for the current user"""
    try:
        instances = db.query(BotInstance).filter(BotInstance.user_id == current_user.id).all()
        return [
            {
                "id": instance.id,
                "name": instance.name,
                "exchange": instance.exchange,
                "market_type": instance.market_type,
                "is_active": instance.is_active,
                "last_poll": instance.last_poll.isoformat() if instance.last_poll else None,
                "created_at": instance.created_at.isoformat(),
                "strategies": instance.strategies or [],
                "trading_pair": instance.trading_pair,
                "balance_enabled": instance.balance_enabled
            }
            for instance in instances
        ]
    except Exception as e:
        logger.error(f"❌ Error getting instances: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving instances")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                # Handle authentication
                if message.get("type") == "auth":
                    token = message.get("token")
                    # Verify token and associate user with websocket
                    # Implementation depends on your token verification logic
                    pass
                
                # Echo message back (you can customize this)
                await manager.send_personal_message(f"Echo: {data}", websocket)
                
            except json.JSONDecodeError:
                await manager.send_personal_message("Invalid JSON", websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"detail": "API endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main-api-only:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
