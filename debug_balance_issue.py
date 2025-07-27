#!/usr/bin/env python3
"""
Debug balance and strategy monitor issues for non-super users
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

def get_db_session():
    """Get database session"""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///medusa.db')
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def is_postgresql(engine):
    """Check if using PostgreSQL"""
    return 'postgresql' in str(engine.url)

def debug_balance_issue():
    """Debug balance issue for non-super users"""
    db, engine = get_db_session()
    is_pg = is_postgresql(engine)
    
    try:
        print("🔍 DEBUGGING BALANCE AND STRATEGY MONITOR ISSUES...")
        print("=" * 60)
        
        # 1. Check instances with balance_enabled status
        print("\n1. CHECKING BALANCE_ENABLED STATUS:")
        result = db.execute(text("""
            SELECT bi.id, bi.name, bi.balance_enabled, bi.is_active, 
                   bi.last_poll, bi.last_error, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY u.is_superuser DESC, bi.name
        """)).fetchall()
        
        if result:
            print(f"Found {len(result)} instances:")
            for row in result:
                balance_enabled = "✅" if row[2] else "❌"
                is_active = "✅" if row[3] else "❌"
                super_user = "👑" if row[7] else "👤"
                print(f"\n{super_user} Instance: {row[1]}")
                print(f"   - ID: {row[0]}")
                print(f"   - Balance Enabled: {balance_enabled} ({row[2]})")
                print(f"   - Active: {is_active}")
                print(f"   - Last Poll: {row[4]}")
                print(f"   - User: {row[6]}")
                if row[5]:
                    print(f"   - Last Error: {row[5][:100]}...")
        
        # 2. Check balance history count for each instance
        print("\n\n2. BALANCE HISTORY COUNT:")
        result = db.execute(text("""
            SELECT bi.name, u.is_superuser, COUNT(bh.id) as history_count,
                   MAX(bh.timestamp) as last_balance_save
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            LEFT JOIN balance_history bh ON bi.id = bh.instance_id
            GROUP BY bi.id, bi.name, u.is_superuser
            ORDER BY u.is_superuser DESC, bi.name
        """)).fetchall()
        
        for row in result:
            super_user = "👑" if row[1] else "👤"
            print(f"{super_user} {row[0]}: {row[2]} entries (Last: {row[3]})")
        
        # 3. Check if MUZAMMIL_DANI_CERBERUS has any balance history at all
        print("\n\n3. RECENT BALANCE HISTORY FOR NON-SUPER USERS:")
        if is_pg:
            time_clause = "bh.timestamp > NOW() - INTERVAL '1 hour'"
        else:
            time_clause = "bh.timestamp > datetime('now', '-1 hour')"
            
        result = db.execute(text(f"""
            SELECT bi.name, bh.timestamp, bh.balance_data
            FROM balance_history bh
            JOIN bot_instances bi ON bh.instance_id = bi.id
            JOIN users u ON bi.user_id = u.id
            WHERE u.is_superuser = false AND {time_clause}
            ORDER BY bh.timestamp DESC
            LIMIT 5
        """)).fetchall()
        
        if result:
            for row in result:
                print(f"\n{row[0]} at {row[1]}:")
                try:
                    balance = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                    for currency, amounts in balance.items():
                        if isinstance(amounts, dict):
                            print(f"   {currency}: {amounts.get('total', 0)}")
                except:
                    print(f"   Error parsing balance: {row[2][:100]}...")
        else:
            print("❌ No recent balance history for non-super users!")
        
        # 4. Check poll states for balance info
        print("\n\n4. POLL STATE DATA:")
        result = db.execute(text("""
            SELECT bi.name, ps.state_key, ps.state_value, ps.updated_at
            FROM poll_states ps
            JOIN bot_instances bi ON ps.instance_id = bi.id
            JOIN users u ON bi.user_id = u.id
            WHERE u.is_superuser = false 
            AND (ps.state_key LIKE '%balance%' OR ps.state_key LIKE '%error%')
            ORDER BY ps.updated_at DESC
            LIMIT 10
        """)).fetchall()
        
        if result:
            for row in result:
                print(f"\n{row[0]} - {row[1]}:")
                print(f"   Value: {row[2][:100]}...")
                print(f"   Updated: {row[3]}")
        
        # 5. Check strategy monitor state
        print("\n\n5. STRATEGY MONITOR STATE:")
        result = db.execute(text("""
            SELECT instance_id, poll_key, last_update, position_data
            FROM strategy_monitor_state
            ORDER BY last_update DESC
            LIMIT 10
        """)).fetchall()
        
        if result:
            for row in result:
                print(f"\nInstance {row[0]} - {row[1]}:")
                print(f"   Last Update: {row[2]}")
                try:
                    data = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                    print(f"   Positions: {len(data) if isinstance(data, list) else 'N/A'}")
                except:
                    print(f"   Error parsing data")
        else:
            print("❌ No strategy monitor state found!")
        
        # 6. Check trading pairs for non-super users
        print("\n\n6. TRADING PAIRS FOR NON-SUPER USERS:")
        result = db.execute(text("""
            SELECT bi.name, bi.trading_pair, bi.exchange
            FROM bot_instances bi
            JOIN users u ON bi.user_id = u.id
            WHERE u.is_superuser = false
        """)).fetchall()
        
        for row in result:
            print(f"{row[0]}: {row[1]} on {row[2]}")
        
        # 7. Check API credentials accessibility
        print("\n\n7. API CREDENTIALS CHECK:")
        result = db.execute(text("""
            SELECT bi.name, 
                   CASE WHEN bi.api_key IS NOT NULL THEN 'Direct' 
                        WHEN bi.api_credential_id IS NOT NULL THEN 'Library' 
                        ELSE 'None' END as api_type,
                   ac.name as credential_name,
                   ac.is_active as cred_active
            FROM bot_instances bi
            LEFT JOIN api_credentials ac ON bi.api_credential_id = ac.id
            JOIN users u ON bi.user_id = u.id
            WHERE u.is_superuser = false
        """)).fetchall()
        
        for row in result:
            active = "✅" if row[3] else "❌" if row[3] is not None else ""
            print(f"{row[0]}: {row[1]} API {active} (Cred: {row[2]})")
            
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_balance_issue() 