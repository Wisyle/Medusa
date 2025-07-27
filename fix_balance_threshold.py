#!/usr/bin/env python3
"""
Fix balance display threshold issue
The problem appears to be balance filtering hiding small amounts
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def get_db_session():
    """Get database session"""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///medusa.db')
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def fix_balance_display():
    """Check and fix balance display thresholds"""
    db, engine = get_db_session()
    
    try:
        print("🔍 CHECKING BALANCE DISPLAY ISSUE...")
        
        # Detect database type
        database_url = os.getenv('DATABASE_URL', 'sqlite:///medusa.db')
        is_postgresql = database_url.startswith('postgresql')
        
        # Use appropriate datetime function for database type
        if is_postgresql:
            datetime_clause = "bh.timestamp >= NOW() - INTERVAL '1 day'"
            error_datetime_clause = "el.timestamp >= NOW() - INTERVAL '1 day'"
        else:
            datetime_clause = "bh.timestamp >= datetime('now', '-1 day')"
            error_datetime_clause = "el.timestamp >= datetime('now', '-1 day')"
        
        # Check recent balance history for both instances
        print("\n=== RECENT BALANCE HISTORY ===")
        balance_query = f"""
            SELECT bi.name, bi.user_id, u.email, u.is_superuser,
                   bh.timestamp, bh.balance_data, bh.total_value_usd
            FROM balance_history bh
            JOIN bot_instances bi ON bh.instance_id = bi.id
            LEFT JOIN users u ON bi.user_id = u.id
            WHERE {datetime_clause}
            ORDER BY bh.timestamp DESC
            LIMIT 20
        """
        
        recent_balances = db.execute(text(balance_query)).fetchall()
        
        if recent_balances:
            print("Recent balance entries:")
            for balance in recent_balances:
                super_status = "SUPER" if balance[3] else "REGULAR"
                print(f"   {balance[4]} - {balance[0]} ({super_status}) - ${balance[6]}")
                if balance[5]:  # balance_data
                    import json
                    try:
                        balance_data = json.loads(balance[5]) if isinstance(balance[5], str) else balance[5]
                        print(f"     Currencies: {list(balance_data.keys())}")
                        for curr, amounts in balance_data.items():
                            if isinstance(amounts, dict):
                                total = amounts.get('total', 0)
                                print(f"       {curr}: {total}")
                    except:
                        print(f"     Raw data: {balance[5]}")
                print()
        else:
            print("   ❌ No recent balance history found")
        
        # Check if there are polling errors for non-super users
        print("\n=== RECENT ERRORS FOR NON-SUPER USERS ===")
        error_query = f"""
            SELECT bi.name, u.email, u.is_superuser, el.timestamp, el.error_message
            FROM error_logs el
            JOIN bot_instances bi ON el.instance_id = bi.id
            LEFT JOIN users u ON bi.user_id = u.id
            WHERE u.is_superuser = FALSE 
            AND {error_datetime_clause}
            ORDER BY el.timestamp DESC
            LIMIT 10
        """
        
        recent_errors = db.execute(text(error_query)).fetchall()
        
        if recent_errors:
            print("Recent errors for regular users:")
            for error in recent_errors:
                print(f"   {error[3]} - {error[0]} ({error[1]}): {error[4][:100]}...")
        else:
            print("   ✅ No recent errors for non-super users")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Balance Display Threshold Checker")
    success = fix_balance_display()
    
    if success:
        print(f"\n💡 Possible issues:")
        print(f"  • Balance amounts too small (< $1 threshold)")
        print(f"  • Currency filtering excluding non-USDT balances")  
        print(f"  • Active coin detection failing for bitget symbols")
        print(f"  • Balance history not being saved for non-super users")
    else:
        print(f"\n❌ Check failed")
    
    sys.exit(0 if success else 1) 