#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, BotInstance

def main():
    db = SessionLocal()
    try:
        count = db.query(BotInstance).count()
        print(f"Total bot instances: {count}")
        
        if count > 0:
            instances = db.query(BotInstance).all()
            print("\nCurrent Bot Instances:")
            print("=" * 50)
            for instance in instances:
                print(f"ID: {instance.id}")
                print(f"Name: {instance.name}")
                print(f"Exchange: {instance.exchange}")
                print(f"Trading Pair: {instance.trading_pair}")
                print(f"Market Type: {getattr(instance, 'market_type', 'None')}")
                print(f"Is Active: {instance.is_active}")
                print("-" * 30)
        else:
            print("No bot instances found!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
