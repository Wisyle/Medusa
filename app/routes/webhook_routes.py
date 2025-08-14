#!/usr/bin/env python3
"""
Webhook Routes - Handle external webhook integrations
"""

from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
import hmac
import hashlib
import logging
from datetime import datetime

from app.database import get_db
from app.auth import get_current_user_html, User
from services.notification_service import notification_manager, NotificationMessage
from app.config import settings

logger = logging.getLogger(__name__)

def add_webhook_routes(app: FastAPI):
    """Add webhook routes to the FastAPI app"""
    
    @app.post("/webhooks/telegram")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: Optional[str] = Header(None)
    ):
        """Handle incoming Telegram webhook updates"""
        
        if settings.telegram_webhook_secret:
            if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
                raise HTTPException(status_code=403, detail="Invalid webhook secret")
        
        try:
            update_data = await request.json()
            logger.info(f"Received Telegram webhook update: {update_data}")
            
            if "message" in update_data:
                message = update_data["message"]
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                
                logger.info(f"Telegram message from {chat_id}: {text}")
            
            return {"ok": True}
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.post("/webhooks/external")
    async def external_webhook(
        request: Request,
        current_user: User = Depends(get_current_user_html)
    ):
        """Handle incoming webhooks from external systems"""
        
        try:
            webhook_data = await request.json()
            
            logger.info(f"Received external webhook from user {current_user.email}: {webhook_data}")
            
            event_type = webhook_data.get("event_type", "external_webhook")
            title = webhook_data.get("title", "External Webhook")
            message = webhook_data.get("message", "Received external webhook")
            data = webhook_data.get("data", {})
            priority = webhook_data.get("priority", "normal")
            
            notification = NotificationMessage(
                event_type=event_type,
                title=title,
                message=message,
                data=data,
                priority=priority,
                user_id=current_user.id
            )
            
            success = await notification_manager.send_notification(notification)
            
            return {
                "status": "success" if success else "partial_failure",
                "message": "Webhook processed and notification sent",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing external webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.post("/api/notifications/send")
    async def send_notification(
        request: Request,
        current_user: User = Depends(get_current_user_html)
    ):
        """Send a custom notification"""
        
        try:
            notification_data = await request.json()
            
            notification = NotificationMessage(
                event_type=notification_data.get("event_type", "custom"),
                title=notification_data.get("title", "Custom Notification"),
                message=notification_data.get("message", ""),
                data=notification_data.get("data", {}),
                priority=notification_data.get("priority", "normal"),
                user_id=current_user.id
            )
            
            success = await notification_manager.send_notification(notification)
            
            return {
                "status": "success" if success else "failed",
                "message": "Notification sent" if success else "Failed to send notification",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise HTTPException(status_code=500, detail="Failed to send notification")
    
    @app.get("/api/notifications/history")
    async def get_notification_history(
        request: Request,
        limit: int = 50,
        current_user: User = Depends(get_current_user_html)
    ):
        """Get notification history for the current user"""
        
        try:
            # This would typically query a notifications table
            # For now, return a placeholder response
            return {
                "notifications": [],
                "total": 0,
                "limit": limit,
                "user_id": current_user.id
            }
            
        except Exception as e:
            logger.error(f"Error getting notification history: {e}")
            raise HTTPException(status_code=500, detail="Failed to get notification history")
    
    @app.post("/api/webhooks/configure")
    async def configure_webhook(
        request: Request,
        current_user: User = Depends(get_current_user_html)
    ):
        """Configure webhook settings"""
        
        try:
            config_data = await request.json()
            
            # Store webhook configuration (would typically save to database)
            logger.info(f"Webhook configuration updated by user {current_user.email}: {config_data}")
            
            return {
                "status": "success",
                "message": "Webhook configuration updated",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error configuring webhook: {e}")
            raise HTTPException(status_code=500, detail="Failed to configure webhook")
    
    @app.get("/api/webhooks/status")
    async def get_webhook_status(
        request: Request,
        current_user: User = Depends(get_current_user_html)
    ):
        """Get webhook system status"""
        
        try:
            return {
                "telegram_configured": bool(settings.default_telegram_bot_token),
                "webhook_secret_configured": bool(settings.telegram_webhook_secret),
                "notification_service_status": "active",
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting webhook status: {e}")
            raise HTTPException(status_code=500, detail="Failed to get webhook status")
