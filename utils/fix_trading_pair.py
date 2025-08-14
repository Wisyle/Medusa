#!/usr/bin/env python3
"""
Remove trading pair filter to process all symbols
"""

from app.database import SessionLocal, BotInstance

def remove_trading_pair_filter():
    """Remove trading pair filter from all instances"""
    db = SessionLocal()
    
    try:
        instances = db.query(BotInstance).all()
        
        for instance in instances:
            if instance.trading_pair:
                print(f"Removing trading pair filter '{instance.trading_pair}' from {instance.name}")
                instance.trading_pair = None
            else:
                print(f"{instance.name} already processes all trading pairs")
        
        db.commit()
        print("✅ Trading pair filters removed. Bot will now process ALL symbols.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    remove_trading_pair_filter()
