#!/usr/bin/env python3
"""
Enable balance for all instances and clear stale poll states
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

def get_db_session():
    database_url = os.getenv('DATABASE_URL', 'sqlite:///medusa.db')
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def fix_instances():
    db, engine = get_db_session()
    
    try:
        # Enable balance for all instances
        print("🔧 Enabling balance for all instances...")
        result = db.execute(text("""
            UPDATE bot_instances 
            SET balance_enabled = true 
            WHERE balance_enabled = false OR balance_enabled IS NULL
        """))
        db.commit()
        print(f"✅ Updated {result.rowcount} instances")
        
        # Clear old poll states that might be stuck
        print("\n🧹 Clearing stale poll states...")
        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = db.execute(text("""
            DELETE FROM poll_states 
            WHERE timestamp < :cutoff
        """), {'cutoff': cutoff})
        db.commit()
        print(f"✅ Cleared {result.rowcount} old poll states")
        
        # Clear strategy monitor states to force refresh
        print("\n🔄 Resetting strategy monitor states...")
        result = db.execute(text("DELETE FROM strategy_monitor_state"))
        db.commit()
        print(f"✅ Cleared {result.rowcount} monitor states")
        
        # Show current status
        print("\n📊 Current instance status:")
        instances = db.execute(text("""
            SELECT bi.name, bi.balance_enabled, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY u.is_superuser DESC, bi.name
        """)).fetchall()
        
        for instance in instances:
            status = "✅" if instance[1] else "❌"
            user_type = "👑" if instance[3] else "👤"
            print(f"{user_type} {instance[0]}: Balance {status} (User: {instance[2]})")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_instances()
