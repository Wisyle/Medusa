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

from database import get_db
from auth import get_current_active_user, User
from notification_service import notification_manager, NotificationMessage
from config import settings

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
        current_user: User = Depends(get_current_active_user)
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
        current_user: User = Depends(get_current_active_user)
    ):
        """Send a custom notification"""
        
        try:
            notification_data = await request.json()
            
            if "title" not in notification_data or "message" not in notification_data:
                raise HTTPException(status_code=400, detail="Title and message are required")
            
            notification = NotificationMessage(
                event_type=notification_data.get("event_type", "custom"),
                title=notification_data["title"],
                message=notification_data["message"],
                data=notification_data.get("data", {}),
                priority=notification_data.get("priority", "normal"),
                user_id=current_user.id,
                instance_id=notification_data.get("instance_id")
            )
            
            success = await notification_manager.send_notification(notification)
            
            return {
                "status": "success" if success else "failure",
                "message": "Notification sent" if success else "Failed to send notification"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending custom notification: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.get("/api/notifications/test")
    async def test_notification(
        current_user: User = Depends(get_current_active_user)
    ):
        """Send a test notification"""
        
        notification = NotificationMessage(
            event_type="system_test",
            title="Test Notification",
            message="This is a test notification from TAR Global Strategies Unified Command Hub",
            data={
                "test_user": current_user.email,
                "timestamp": datetime.utcnow().isoformat(),
                "system_status": "operational"
            },
            priority="normal",
            user_id=current_user.id
        )
        
        success = await notification_manager.send_notification(notification)
        
        return {
            "status": "success" if success else "failure",
            "message": "Test notification sent" if success else "Failed to send test notification"
        }
    
    @app.post("/api/webhooks/configure")
    async def configure_webhooks(
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ):
        """Configure webhook URLs for external integrations"""
        
        if not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        try:
            config_data = await request.json()
            webhook_urls = config_data.get("webhook_urls", [])
            
            notification_manager.webhook_urls.clear()
            
            for url in webhook_urls:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    notification_manager.add_webhook_url(url)
            
            return {
                "status": "success",
                "message": f"Configured {len(notification_manager.webhook_urls)} webhook URLs",
                "webhook_urls": notification_manager.webhook_urls
            }
            
        except Exception as e:
            logger.error(f"Error configuring webhooks: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.get("/api/webhooks/status")
    async def webhook_status(
        current_user: User = Depends(get_current_active_user)
    ):
        """Get webhook configuration status"""
        
        telegram_configured = bool(settings.default_telegram_bot_token and settings.default_telegram_chat_id)
        
        return {
            "telegram": {
                "configured": telegram_configured,
                "bot_token_set": bool(settings.default_telegram_bot_token),
                "chat_id_set": bool(settings.default_telegram_chat_id),
                "topic_id_set": bool(settings.default_telegram_topic_id),
                "notifications_enabled": settings.enable_telegram_notifications
            },
            "webhooks": {
                "count": len(notification_manager.webhook_urls),
                "urls": notification_manager.webhook_urls if current_user.is_superuser else ["***HIDDEN***"] * len(notification_manager.webhook_urls)
            },
            "rate_limiting": {
                "enabled": True,
                "rate_limit_seconds": settings.notification_rate_limit,
                "batch_size": settings.notification_batch_size
            }
        }
