#!/usr/bin/env python3
"""
Debug script to help understand why polling isn't processing symbols
"""

from database import SessionLocal, BotInstance
from polling import ExchangePoller
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_polling():
    """Debug the polling process"""
    db = SessionLocal()
    
    # Get first instance
    instance = db.query(BotInstance).first()
    if not instance:
        print("❌ No bot instances found!")
        print("You need to create a bot instance first.")
        return
    
    print(f"🤖 Instance: {instance.name}")
    print(f"📊 Exchange: {instance.exchange}")
    print(f"💱 Trading Pair: {instance.trading_pair}")
    print(f"🎯 Strategies: {instance.strategies}")
    print(f"📞 Telegram Bot Token: {'✅ Set' if instance.telegram_bot_token else '❌ Not set'}")
    print(f"💬 Telegram Chat ID: {instance.telegram_chat_id}")
    print(f"📝 Telegram Topic ID: {instance.telegram_topic_id}")
    print(f"🔔 Webhook URL: {'✅ Set' if instance.webhook_url else '❌ Not set'}")
    print()
    
    try:
        # Initialize poller
        poller = ExchangePoller(instance.id)
        
        # Fetch data
        print("📡 Fetching positions...")
        positions = await poller.fetch_positions()
        print(f"   Found {len(positions)} positions")
        
        print("📡 Fetching orders...")
        orders = await poller.fetch_open_orders()
        print(f"   Found {len(orders)} orders")
        
        print("📡 Fetching trades...")
        trades = await poller.fetch_recent_trades()
        print(f"   Found {len(trades)} trades")
        print()
        
        # Check symbol filtering
        print("🔍 Checking symbol filtering...")
        all_symbols = set()
        
        for pos in positions:
            all_symbols.add(pos['symbol'])
        for order in orders:
            all_symbols.add(order['symbol'])
        for trade in trades:
            all_symbols.add(trade['symbol'])
        
        print(f"📋 All symbols found: {sorted(all_symbols)}")
        print()
        
        # Test each symbol
        for symbol in sorted(all_symbols):
            should_process = poller._should_process_symbol(symbol)
            status = "✅ WILL PROCESS" if should_process else "❌ FILTERED OUT"
            print(f"   {symbol}: {status}")
            
            if not should_process:
                # Explain why
                if instance.trading_pair and symbol != instance.trading_pair:
                    print(f"      Reason: Trading pair filter (configured: {instance.trading_pair})")
                elif instance.strategies:
                    strategy_type = poller._detect_strategy_type(symbol, {})
                    print(f"      Reason: Strategy filter (detected: {strategy_type}, allowed: {instance.strategies})")
        
        print()
        
        # Recommendations
        print("💡 RECOMMENDATIONS:")
        if instance.trading_pair:
            print(f"   • Your trading pair is set to '{instance.trading_pair}'")
            print("   • Only this pair will be processed")
            print("   • To process all pairs, remove the trading pair restriction")
        
        if not instance.telegram_bot_token:
            print("   • No Telegram bot token configured")
            print("   • Telegram notifications will not be sent")
            
        if not instance.telegram_chat_id:
            print("   • No Telegram chat ID configured")
            print("   • Telegram notifications will not be sent")
            
        if not instance.webhook_url:
            print("   • No webhook URL configured")
            print("   • Webhook notifications will not be sent")
            
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_polling())
