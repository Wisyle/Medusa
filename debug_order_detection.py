#!/usr/bin/env python3

import sys
sys.path.append('.')
import asyncio
from database import SessionLocal, BotInstance
from polling import ExchangePoller

async def debug_order_detection():
    """Debug order detection issues"""
    print("=== Debugging Order Detection ===")
    
    db = SessionLocal()
    try:
        instances = db.query(BotInstance).filter(BotInstance.is_active == True).all()
        print(f"Found {len(instances)} active instances")
        
        for instance in instances:
            print(f"\n--- Instance {instance.id}: {instance.name} ---")
            print(f"Exchange: {instance.exchange}")
            print(f"Trading Pair: {instance.trading_pair}")
            print(f"API Key: {instance.api_key[:10]}...")
            
            try:
                poller = ExchangePoller(instance.id)
                
                print(f"Testing exchange connectivity...")
                positions = await poller.fetch_positions()
                orders = await poller.fetch_open_orders()
                trades = await poller.fetch_recent_trades()
                
                print(f"✅ Exchange connected successfully")
                print(f"Positions: {len(positions)}")
                print(f"Open Orders: {len(orders)}")
                print(f"Recent Trades: {len(trades)}")
                
                if trades:
                    print(f"Sample trade: {trades[0]}")
                    
                print(f"Testing polling cycle...")
                await poller.poll_once()
                print(f"✅ Polling cycle completed")
                
                poller.close()
                
            except Exception as e:
                print(f"❌ Error testing instance {instance.id}: {e}")
                import traceback
                traceback.print_exc()
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_order_detection())
