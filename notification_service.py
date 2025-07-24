#!/usr/bin/env python3
"""
Notification Service - Handle Telegram notifications and webhooks
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp
import requests
from sqlalchemy.orm import Session

from config import settings
from database import get_db

logger = logging.getLogger(__name__)

@dataclass
class NotificationMessage:
    """Structured notification message"""
    event_type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    priority: str = "normal"  # low, normal, high, critical
    user_id: Optional[int] = None
    instance_id: Optional[int] = None
    
class TelegramNotificationService:
    """Service for sending Telegram notifications"""
    
    def __init__(self):
        self.bot_token = settings.default_telegram_bot_token
        self.chat_id = settings.default_telegram_chat_id
        self.topic_id = settings.default_telegram_topic_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.rate_limiter = {}  # Track last notification times
        
    async def send_message(
        self, 
        message: str, 
        chat_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """Send a message to Telegram"""
        if not self.bot_token or not self.base_url:
            logger.warning("Telegram bot token not configured")
            return False
            
        target_chat = chat_id or self.chat_id
        target_topic = topic_id or self.topic_id
        
        if not target_chat:
            logger.warning("No Telegram chat ID configured")
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": message,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }
        
        if target_topic:
            payload["message_thread_id"] = target_topic
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=settings.telegram_timeout)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Telegram message sent successfully to {target_chat}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send Telegram message: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message_sync(
        self, 
        message: str, 
        chat_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        parse_mode: str = "HTML"
    ) -> bool:
        """Synchronous version of send_message"""
        if not self.bot_token or not self.base_url:
            logger.warning("Telegram bot token not configured")
            return False
            
        target_chat = chat_id or self.chat_id
        target_topic = topic_id or self.topic_id
        
        if not target_chat:
            logger.warning("No Telegram chat ID configured")
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": message,
            "parse_mode": parse_mode
        }
        
        if target_topic:
            payload["message_thread_id"] = target_topic
            
        try:
            response = requests.post(url, json=payload, timeout=settings.telegram_timeout)
            if response.status_code == 200:
                logger.info(f"Telegram message sent successfully to {target_chat}")
                return True
            else:
                logger.error(f"Failed to send Telegram message: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def is_rate_limited(self, key: str) -> bool:
        """Check if a notification type is rate limited"""
        now = time.time()
        last_sent = self.rate_limiter.get(key, 0)
        
        if now - last_sent < settings.notification_rate_limit:
            return True
            
        self.rate_limiter[key] = now
        return False

class NotificationManager:
    """Main notification manager"""
    
    def __init__(self):
        self.telegram_service = TelegramNotificationService()
        self.webhook_urls = []  # List of webhook URLs for external systems
        
    async def send_notification(self, notification: NotificationMessage) -> bool:
        """Send a notification through all configured channels"""
        success = True
        
        rate_limit_key = f"{notification.event_type}_{notification.instance_id or 'global'}"
        if self.telegram_service.is_rate_limited(rate_limit_key):
            logger.debug(f"Notification rate limited: {rate_limit_key}")
            return True  # Don't consider rate limiting as failure
        
        telegram_message = self._format_telegram_message(notification)
        
        if settings.enable_telegram_notifications:
            telegram_success = await self.telegram_service.send_message(telegram_message)
            success = success and telegram_success
        
        webhook_success = await self._send_to_webhooks(notification)
        success = success and webhook_success
        
        return success
    
    def send_notification_sync(self, notification: NotificationMessage) -> bool:
        """Synchronous version of send_notification"""
        rate_limit_key = f"{notification.event_type}_{notification.instance_id or 'global'}"
        if self.telegram_service.is_rate_limited(rate_limit_key):
            logger.debug(f"Notification rate limited: {rate_limit_key}")
            return True
        
        telegram_message = self._format_telegram_message(notification)
        
        if settings.enable_telegram_notifications:
            return self.telegram_service.send_message_sync(telegram_message)
        
        return True
    
    def _format_telegram_message(self, notification: NotificationMessage) -> str:
        """Format notification for Telegram with emojis and rich formatting"""
        
        priority_emojis = {
            "low": "🔵",
            "normal": "🟢", 
            "high": "🟡",
            "critical": "🔴"
        }
        
        event_emojis = {
            "bot_start": "📡",
            "bot_stop": "⏹️",
            "order_placed": "✅",
            "order_filled": "💰",
            "position_update": "📊",
            "position_closed": "❌",
            "error": "⚠️",
            "system_alert": "🚨",
            "validator_reward": "💎",
            "arbitrage_opportunity": "⚡",
            "api_error": "🔧",
            "connection_lost": "📡❌",
            "connection_restored": "📡✅"
        }
        
        priority_emoji = priority_emojis.get(notification.priority, "🔵")
        event_emoji = event_emojis.get(notification.event_type, "📢")
        
        lines = [
            f"{priority_emoji} {event_emoji} <b>{notification.title}</b>",
            "",
            notification.message
        ]
        
        if notification.data:
            lines.append("")
            lines.append("📋 <b>Details:</b>")
            for key, value in notification.data.items():
                if isinstance(value, (int, float)):
                    if key.lower() in ['pnl', 'profit', 'loss']:
                        emoji = "📈" if value >= 0 else "📉"
                        lines.append(f"{emoji} {key.title()}: {value}")
                    else:
                        lines.append(f"🔢 {key.title()}: {value}")
                else:
                    lines.append(f"📝 {key.title()}: {value}")
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append("")
        lines.append(f"🕐 {timestamp}")
        
        return "\n".join(lines)
    
    async def _send_to_webhooks(self, notification: NotificationMessage) -> bool:
        """Send notification to configured webhook URLs"""
        if not self.webhook_urls:
            return True
            
        webhook_payload = {
            "event_type": notification.event_type,
            "title": notification.title,
            "message": notification.message,
            "data": notification.data or {},
            "priority": notification.priority,
            "user_id": notification.user_id,
            "instance_id": notification.instance_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        success = True
        
        async with aiohttp.ClientSession() as session:
            for webhook_url in self.webhook_urls:
                try:
                    async with session.post(
                        webhook_url,
                        json=webhook_payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status not in [200, 201, 202]:
                            logger.error(f"Webhook failed: {webhook_url} - {response.status}")
                            success = False
                        else:
                            logger.info(f"Webhook sent successfully: {webhook_url}")
                            
                except Exception as e:
                    logger.error(f"Error sending webhook to {webhook_url}: {e}")
                    success = False
        
        return success
    
    def add_webhook_url(self, url: str):
        """Add a webhook URL"""
        if url not in self.webhook_urls:
            self.webhook_urls.append(url)
    
    def remove_webhook_url(self, url: str):
        """Remove a webhook URL"""
        if url in self.webhook_urls:
            self.webhook_urls.remove(url)

notification_manager = NotificationManager()

async def notify_bot_start(instance_id: int, symbol: str, strategy: str, user_id: Optional[int] = None):
    """Send bot start notification"""
    notification = NotificationMessage(
        event_type="bot_start",
        title="Bot Starting",
        message=f"🔁 Initializing instance for {symbol}\n🧠 Strategy: {strategy}",
        data={"instance_id": instance_id, "symbol": symbol, "strategy": strategy},
        priority="normal",
        user_id=user_id,
        instance_id=instance_id
    )
    return await notification_manager.send_notification(notification)

async def notify_order_placed(instance_id: int, order_data: Dict[str, Any], user_id: Optional[int] = None):
    """Send order placed notification"""
    notification = NotificationMessage(
        event_type="order_placed",
        title="Order Placed",
        message=f"🔹 Symbol: {order_data.get('symbol', 'N/A')}\n📈 Side: {order_data.get('side', 'N/A')} | 🔧 Leverage: {order_data.get('leverage', 'N/A')}x\n💰 Entry: {order_data.get('price', 'N/A')}\n🧮 Size: {order_data.get('size', 'N/A')}",
        data=order_data,
        priority="normal",
        user_id=user_id,
        instance_id=instance_id
    )
    return await notification_manager.send_notification(notification)

async def notify_position_update(instance_id: int, position_data: Dict[str, Any], user_id: Optional[int] = None):
    """Send position update notification"""
    notification = NotificationMessage(
        event_type="position_update",
        title="Position Update",
        message=f"🪙 {position_data.get('symbol', 'N/A')} | {position_data.get('side', 'N/A')}\n📌 Entry: {position_data.get('entry_price', 'N/A')} | 📉 Mark: {position_data.get('mark_price', 'N/A')}\n💹 PnL: {position_data.get('pnl_percent', 'N/A')}% | 💣 Liq: {position_data.get('liquidation_price', 'N/A')}",
        data=position_data,
        priority="normal",
        user_id=user_id,
        instance_id=instance_id
    )
    return await notification_manager.send_notification(notification)

async def notify_error(instance_id: Optional[int], error_message: str, error_data: Optional[Dict[str, Any]] = None, user_id: Optional[int] = None):
    """Send error notification"""
    notification = NotificationMessage(
        event_type="error",
        title="System Error",
        message=error_message,
        data=error_data or {},
        priority="high",
        user_id=user_id,
        instance_id=instance_id
    )
    return await notification_manager.send_notification(notification)

def notify_bot_start_sync(instance_id: int, symbol: str, strategy: str, user_id: Optional[int] = None):
    """Synchronous version of notify_bot_start"""
    notification = NotificationMessage(
        event_type="bot_start",
        title="Bot Starting",
        message=f"🔁 Initializing instance for {symbol}\n🧠 Strategy: {strategy}",
        data={"instance_id": instance_id, "symbol": symbol, "strategy": strategy},
        priority="normal",
        user_id=user_id,
        instance_id=instance_id
    )
    return notification_manager.send_notification_sync(notification)
