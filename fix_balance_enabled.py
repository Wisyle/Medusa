#!/usr/bin/env python3
"""
Check and fix balance_enabled settings for all instances
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

def get_db_session():
    """Get database session"""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///medusa.db')
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def check_and_fix_balance_enabled():
    """Check and fix balance_enabled settings"""
    db, engine = get_db_session()
    
    try:
        print("🔍 CHECKING BALANCE_ENABLED SETTINGS...")
        
        # Check all instances and their balance_enabled status
        query = """
            SELECT bi.id, bi.name, bi.balance_enabled, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY bi.id
        """
        
        instances = db.execute(text(query)).fetchall()
        
        if not instances:
            print("❌ No instances found")
            return False
        
        print(f"\n📋 Found {len(instances)} instances:\n")
        print(f"{'ID':<5} {'Name':<30} {'Balance':<10} {'User':<30} {'Super':<6}")
        print("-" * 85)
        
        needs_fix = []
        for inst in instances:
            id, name, balance_enabled, email, is_super = inst
            balance_str = "✅ Yes" if balance_enabled else "❌ No"
            super_str = "Yes" if is_super else "No"
            print(f"{id:<5} {name[:30]:<30} {balance_str:<10} {email or 'N/A':<30} {super_str:<6}")
            
            # If balance is disabled, mark for fixing
            if not balance_enabled:
                needs_fix.append((id, name))
        
        if needs_fix:
            print(f"\n⚠️  Found {len(needs_fix)} instances with balance disabled!")
            print("\n🔧 FIXING BALANCE_ENABLED...")
            
            # Enable balance for all instances
            update_query = "UPDATE bot_instances SET balance_enabled = :true_value"
            
            # Use correct boolean value based on database type
            is_postgresql = "postgresql" in str(engine.url)
            true_value = True if is_postgresql else 1
            
            db.execute(text(update_query), {"true_value": true_value})
            db.commit()
            
            print("✅ Enabled balance tracking for all instances!")
            
            # Verify the fix
            print("\n📋 VERIFICATION:")
            verify = db.execute(text("""
                SELECT name, balance_enabled 
                FROM bot_instances 
                WHERE id IN :ids
            """), {"ids": tuple(id for id, _ in needs_fix)}).fetchall()
            
            for name, enabled in verify:
                status = "✅ Fixed" if enabled else "❌ Still disabled"
                print(f"  {name}: {status}")
        else:
            print("\n✅ All instances already have balance enabled!")
        
        # Check for recent balance history
        print("\n📊 RECENT BALANCE HISTORY CHECK:")
        balance_check = """
            SELECT 
                bi.name,
                COUNT(bh.id) as history_count,
                MAX(bh.timestamp) as last_balance
            FROM bot_instances bi
            LEFT JOIN balance_history bh ON bi.id = bh.instance_id
            GROUP BY bi.id, bi.name
            ORDER BY bi.name
        """
        
        balance_stats = db.execute(text(balance_check)).fetchall()
        
        print(f"\n{'Instance':<30} {'History Count':<15} {'Last Balance':<25}")
        print("-" * 70)
        
        for name, count, last_ts in balance_stats:
            last_str = str(last_ts) if last_ts else "Never"
            print(f"{name[:30]:<30} {count:<15} {last_str:<25}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Balance Enabled Check & Fix")
    print("=" * 85)
    
    success = check_and_fix_balance_enabled()
    
    if success:
        print(f"\n✅ Check completed successfully!")
        print(f"💡 If balance was disabled, it's now enabled for all instances")
        print(f"📌 The instances should start saving balance history on next poll")
    else:
        print(f"\n❌ Check failed")
    
    sys.exit(0 if success else 1) 