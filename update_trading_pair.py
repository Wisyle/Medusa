#!/usr/bin/env python3
"""
Quick script to update instance 4's trading pair from XRPUSDT to BCHUSDT
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, BotInstance

def main():
    if len(sys.argv) != 4:
        print("Usage: python update_instance_trading_pair.py <instance_id> <old_trading_pair> <new_trading_pair>")
        print("Example: python update_instance_trading_pair.py 4 XRPUSDT BCHUSDT")
        sys.exit(1)
    
    instance_id = int(sys.argv[1])
    old_trading_pair = sys.argv[2]
    new_trading_pair = sys.argv[3]
    
    db = SessionLocal()
    try:
        instance = db.query(BotInstance).filter(BotInstance.id == instance_id).first()
        if not instance:
            print(f"❌ Instance {instance_id} not found!")
            return
        
        print(f"Found instance {instance_id}:")
        print(f"  Name: {instance.name}")
        print(f"  Exchange: {instance.exchange}")
        print(f"  Current Trading Pair: {instance.trading_pair}")
        print(f"  Is Active: {instance.is_active}")
        
        if instance.trading_pair != old_trading_pair:
            print(f"⚠️ Warning: Current trading pair '{instance.trading_pair}' doesn't match expected '{old_trading_pair}'")
            confirm = input("Continue anyway? (y/N): ")
            if confirm.lower() != 'y':
                print("Cancelled")
                return
        
        # Update the trading pair
        instance.trading_pair = new_trading_pair
        db.commit()
        
        print(f"✅ Successfully updated instance {instance_id} trading pair:")
        print(f"  Old: {old_trading_pair}")
        print(f"  New: {new_trading_pair}")
        
        if instance.is_active:
            print("\n⚠️ Note: Instance is currently active. You may need to restart it for changes to take effect.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
