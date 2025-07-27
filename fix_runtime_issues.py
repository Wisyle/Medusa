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
        # First, check current status
        print("📊 Checking current instance status...")
        instances = db.execute(text("""
            SELECT bi.name, bi.balance_enabled, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY u.is_superuser DESC, bi.name
        """)).fetchall()
        
        print(f"Found {len(instances)} instances:")
        for instance in instances:
            status = "✅" if instance[1] else "❌"
            user_type = "👑" if instance[3] else "👤"
            print(f"{user_type} {instance[0]}: Balance {status} (User: {instance[2]})")
        
        # Enable balance for all instances
        print("\n🔧 Enabling balance for all instances...")
        result = db.execute(text("""
            UPDATE bot_instances 
            SET balance_enabled = true 
            WHERE balance_enabled = false OR balance_enabled IS NULL
        """))
        db.commit()
        print(f"✅ Updated {result.rowcount} instances")
        
        if result.rowcount == 0:
            print("   ℹ️ All instances already have balance enabled or no instances exist")
        
        # Clear old poll states that might be stuck
        print("\n🧹 Clearing stale poll states...")
        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = db.execute(text("""
            DELETE FROM poll_states 
            WHERE timestamp < :cutoff
        """), {'cutoff': cutoff})
        db.commit()
        print(f"✅ Cleared {result.rowcount} old poll states")
        
        # Clear strategy monitor states to force refresh (only if table exists)
        print("\n🔄 Resetting strategy monitor states...")
        try:
            # Check if table exists first
            if 'postgresql' in str(engine.url):
                table_check = db.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'strategy_monitor_state'
                    )
                """)).scalar()
            else:
                table_check = db.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='strategy_monitor_state'
                """)).fetchone()
                table_check = table_check is not None
            
            if table_check:
                result = db.execute(text("DELETE FROM strategy_monitor_state"))
                db.commit()
                print(f"✅ Cleared {result.rowcount} monitor states")
            else:
                print("   ℹ️ strategy_monitor_state table doesn't exist (this is OK)")
        except Exception as e:
            print(f"   ℹ️ Could not clear strategy monitor states: {e}")
            db.rollback()
        
        # Show updated status
        print("\n📊 Final instance status:")
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
        
        # Check specific instance
        print("\n🔍 Checking MUZAMMIL_DANI_CERBERUS specifically...")
        muzammil = db.execute(text("""
            SELECT bi.name, bi.balance_enabled, bi.is_active, bi.trading_pair,
                   CASE WHEN bi.api_key IS NOT NULL THEN 'Direct' 
                        WHEN bi.api_credential_id IS NOT NULL THEN 'Library' 
                        ELSE 'None' END as api_type
            FROM bot_instances bi
            WHERE bi.name LIKE '%MUZAMMIL_DANI_CERBERUS%'
        """)).fetchone()
        
        if muzammil:
            print(f"   Name: {muzammil[0]}")
            print(f"   Balance Enabled: {'✅' if muzammil[1] else '❌'} ({muzammil[1]})")
            print(f"   Active: {'✅' if muzammil[2] else '❌'}")
            print(f"   Trading Pair: {muzammil[3]}")
            print(f"   API Type: {muzammil[4]}")
        else:
            print("   ❌ Instance not found!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fix_instances()
