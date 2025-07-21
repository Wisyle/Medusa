import ccxt
import hashlib
import json
import time
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from telegram import Bot
import logging

from database import SessionLocal, BotInstance, PollState, ActivityLog, ErrorLog
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExchangePoller:
    def __init__(self, instance_id: int):
        self.instance_id = instance_id
        self.db = SessionLocal()
        self.instance = self.db.query(BotInstance).filter(BotInstance.id == instance_id).first()
        
        if not self.instance:
            raise ValueError(f"Bot instance {instance_id} not found")
        
        self.exchange = self._init_exchange()
        self.telegram_bot = self._init_telegram()
        
    def _init_exchange(self) -> ccxt.Exchange:
        """Initialize the exchange connection with CloudFront bypass"""
        try:
            exchange_class = getattr(ccxt, self.instance.exchange.lower())
            
            config = {
                'apiKey': self.instance.api_key,
                'secret': self.instance.api_secret,
                'sandbox': False,
                'enableRateLimit': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                },
                'timeout': 30000,
                'rateLimit': 1200
            }
            
            if self.instance.api_passphrase:
                config['passphrase'] = self.instance.api_passphrase
            
            exchange = exchange_class(config)
            return exchange
            
        except Exception as e:
            self._log_error("exchange_init", str(e))
            raise
    
    def _init_telegram(self) -> Optional[Bot]:
        """Initialize Telegram bot"""
        token = self.instance.telegram_bot_token or settings.default_telegram_bot_token
        if token:
            return Bot(token=token)
        return None
    
    def _log_activity(self, event_type: str, symbol: str = None, message: str = "", data: Dict = None):
        """Log activity to database"""
        try:
            log = ActivityLog(
                instance_id=self.instance_id,
                event_type=event_type,
                symbol=symbol,
                message=message,
                data=data
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
    
    def _log_error(self, error_type: str, error_message: str, traceback_str: str = None):
        """Log error to database"""
        try:
            error_log = ErrorLog(
                instance_id=self.instance_id,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback_str
            )
            self.db.add(error_log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    def _get_data_hash(self, data: Any) -> str:
        """Generate hash for change detection"""
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    
    def _detect_strategy_type(self, symbol: str, data: Dict) -> str:
        """Infer strategy type from symbol or data patterns"""
        
        symbol_lower = symbol.lower()
        
        if 'dca' in symbol_lower:
            return 'DCA' if 'futures' not in symbol_lower else 'DCA Futures'
        elif 'grid' in symbol_lower:
            return 'Grid'
        elif 'combo' in symbol_lower:
            return 'Combo'
        elif 'loop' in symbol_lower:
            return 'Loop'
        elif 'btd' in symbol_lower:
            return 'BTD'
        elif 'ais' in symbol_lower:
            return 'AIS Assisted'
        
        return 'Unknown'
    
    def _should_process_symbol(self, symbol: str) -> bool:
        """Check if symbol should be processed based on selected strategies"""
        if not self.instance.strategies:
            return True  # Process all if no specific strategies selected
        
        strategy_type = self._detect_strategy_type(symbol, {})
        return strategy_type in self.instance.strategies
    
    async def fetch_positions(self) -> List[Dict]:
        """Fetch current positions"""
        try:
            positions = self.exchange.fetch_positions()
            return [pos for pos in positions if pos['contracts'] > 0]  # Only open positions
        except Exception as e:
            self._log_error("fetch_positions", str(e))
            return []
    
    async def fetch_open_orders(self) -> List[Dict]:
        """Fetch open orders"""
        try:
            return self.exchange.fetch_open_orders()
        except Exception as e:
            self._log_error("fetch_open_orders", str(e))
            return []
    
    async def fetch_recent_trades(self) -> List[Dict]:
        """Fetch recent trades since last poll"""
        try:
            since = None
            if self.instance.last_poll:
                since = int(self.instance.last_poll.timestamp() * 1000)
            
            return self.exchange.fetch_my_trades(since=since)
        except Exception as e:
            self._log_error("fetch_recent_trades", str(e))
            return []
    
    def _get_previous_state(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Get previous state for comparison"""
        state = self.db.query(PollState).filter(
            PollState.instance_id == self.instance_id,
            PollState.symbol == symbol,
            PollState.data_type == data_type
        ).order_by(PollState.timestamp.desc()).first()
        
        return state.data if state else None
    
    def _save_state(self, symbol: str, data_type: str, data: Dict):
        """Save current state"""
        data_hash = self._get_data_hash(data)
        
        state = PollState(
            instance_id=self.instance_id,
            symbol=symbol,
            data_type=data_type,
            data_hash=data_hash,
            data=data
        )
        
        self.db.add(state)
        self.db.commit()
    
    def _create_event_payload(self, event_type: str, symbol: str, data: Dict) -> Dict:
        """Create structured event payload"""
        strategy_type = self._detect_strategy_type(symbol, data)
        
        payload = {
            "event_type": event_type,
            "symbol": symbol,
            "bot_type": strategy_type,
            "timestamp": datetime.utcnow().isoformat(),
            "instance_id": self.instance_id,
            "exchange": self.instance.exchange
        }
        
        if event_type in ["order_filled", "order_cancelled", "new_order"]:
            payload.update({
                "order_id": data.get('id'),
                "side": data.get('side'),
                "entry_price": data.get('price'),
                "quantity": data.get('amount'),
                "status": data.get('status')
            })
        
        elif event_type == "position_update":
            payload.update({
                "side": data.get('side'),
                "entry_price": data.get('entryPrice'),
                "quantity": data.get('contracts'),
                "unrealized_pnl": data.get('unrealizedPnl')
            })
        
        return payload
    
    async def _send_webhook(self, payload: Dict):
        """Send webhook notification"""
        if not self.instance.webhook_url:
            return
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Secret': settings.webhook_secret
            }
            
            response = requests.post(
                self.instance.webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self._log_activity("webhook_sent", payload.get('symbol'), "Webhook sent successfully")
            else:
                self._log_error("webhook_failed", f"Webhook failed with status {response.status_code}")
                
        except Exception as e:
            self._log_error("webhook_error", str(e))
    
    async def _send_telegram_notification(self, payload: Dict):
        """Send Telegram notification with beautiful formatting"""
        if not self.telegram_bot:
            return
        
        chat_id = self.instance.telegram_chat_id or settings.default_telegram_chat_id
        if not chat_id:
            return
        
        try:
            message = self._format_telegram_message(payload)
            
            topic_id = self.instance.telegram_topic_id or settings.default_telegram_topic_id
            
            send_params = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            if topic_id:
                send_params['message_thread_id'] = int(topic_id)
            
            await self.telegram_bot.send_message(**send_params)
            
            self._log_activity("telegram_sent", payload.get('symbol'), "Telegram notification sent")
            
        except Exception as e:
            self._log_error("telegram_error", str(e))
    
    def _format_telegram_message(self, payload: Dict) -> str:
        """Format beautiful Telegram message with Unicode emojis"""
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        event_type = payload.get('event_type')
        symbol = payload.get('symbol', 'N/A')
        bot_type = payload.get('bot_type', 'Unknown')
        
        if event_type == "order_filled":
            return f"""TARCXXX, [{timestamp}]
📈 Order Filled - {timestamp}

🤖 Bot: {self.instance.name}
💱 Pair: {symbol}
🛡️ Event: Order Filled

Side: {payload.get('side', 'N/A').capitalize()}
Quantity: {payload.get('quantity', 0):.4f} @ ${payload.get('entry_price', 0):.2f}
Status: Filled
Unrealized PnL: ${payload.get('unrealized_pnl', 0):.2f}
Bot Type: {bot_type}

✅ Transaction complete."""

        elif event_type == "position_update":
            return f"""TARCXXX, [{timestamp}]
🔄 Position Change Detected - {timestamp}

🤖 Bot: {self.instance.name}
💱 Pair: {symbol}
🛡️ Event: Position Update

New Size: {payload.get('quantity', 0):.4f}
Entry Price: ${payload.get('entry_price', 0):.2f}
Unrealized PnL: ${payload.get('unrealized_pnl', 0):.2f}
Side: {payload.get('side', 'N/A').capitalize()}
Bot Type: {bot_type}

📊 Monitoring continues."""

        elif event_type == "order_cancelled":
            return f"""TARCXXX, [{timestamp}]
❌ Order Cancelled - {timestamp}

🤖 Bot: {self.instance.name}
💱 Pair: {symbol}
🛡️ Event: Order Cancelled

Order ID: {payload.get('order_id', 'N/A')}
Side: {payload.get('side', 'N/A').capitalize()}
Quantity: {payload.get('quantity', 0):.4f}
Status: Cancelled
Bot Type: {bot_type}

⚠️ Action logged."""

        elif event_type == "new_order":
            return f"""TARCXXX, [{timestamp}]
🆕 New Open Order - {timestamp}

🤖 Bot: {self.instance.name}
💱 Pair: {symbol}
🛡️ Event: New Order Opened

Order ID: {payload.get('order_id', 'N/A')}
Side: {payload.get('side', 'N/A').capitalize()}
Quantity: {payload.get('quantity', 0):.4f} @ ${payload.get('entry_price', 0):.2f}
Status: Open
Bot Type: {bot_type}

⏳ Awaiting fill."""

        else:
            return f"""TARCXXX, [{timestamp}]
📊 Bot Update - {timestamp}

🤖 Bot: {self.instance.name}
💱 Pair: {symbol}
🛡️ Event: {event_type}
Bot Type: {bot_type}

📱 Monitoring active."""
    
    async def poll_once(self):
        """Perform one polling cycle"""
        try:
            logger.info(f"Starting poll for instance {self.instance_id}")
            
            positions = await self.fetch_positions()
            orders = await self.fetch_open_orders()
            trades = await self.fetch_recent_trades()
            
            for position in positions:
                symbol = position['symbol']
                if not self._should_process_symbol(symbol):
                    continue
                
                previous_position = self._get_previous_state(symbol, 'position')
                current_hash = self._get_data_hash(position)
                previous_hash = self._get_data_hash(previous_position) if previous_position else None
                
                if current_hash != previous_hash:
                    payload = self._create_event_payload('position_update', symbol, position)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._save_state(symbol, 'position', position)
            
            for order in orders:
                symbol = order['symbol']
                if not self._should_process_symbol(symbol):
                    continue
                
                previous_order = self._get_previous_state(symbol, f"order_{order['id']}")
                
                if not previous_order:
                    payload = self._create_event_payload('new_order', symbol, order)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._save_state(symbol, f"order_{order['id']}", order)
                
                elif order['status'] != previous_order.get('status'):
                    if order['status'] == 'closed':
                        event_type = 'order_filled'
                    elif order['status'] == 'canceled':
                        event_type = 'order_cancelled'
                    else:
                        event_type = 'order_update'
                    
                    payload = self._create_event_payload(event_type, symbol, order)
                    await self._send_webhook(payload)
                    await self._send_telegram_notification(payload)
                    self._save_state(symbol, f"order_{order['id']}", order)
            
            self.instance.last_poll = datetime.utcnow()
            self.instance.last_error = None
            self.db.commit()
            
            logger.info(f"Poll completed for instance {self.instance_id}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Poll failed for instance {self.instance_id}: {error_msg}")
            
            self.instance.last_error = error_msg
            self.db.commit()
            
            self._log_error("poll_failed", error_msg)
    
    def close(self):
        """Clean up resources"""
        if self.db:
            self.db.close()

async def run_poller(instance_id: int):
    """Run poller for a specific instance"""
    poller = None
    try:
        poller = ExchangePoller(instance_id)
        
        while True:
            db = SessionLocal()
            instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
            db.close()
            
            if not instance or not instance.is_active:
                logger.info(f"Instance {instance_id} is no longer active, stopping poller")
                break
            
            await poller.poll_once()
            await asyncio.sleep(instance.polling_interval)
            
    except Exception as e:
        logger.error(f"Poller for instance {instance_id} crashed: {e}")
    finally:
        if poller:
            poller.close()
