#!/usr/bin/env python3
"""
Comprehensive debug script for production issues:
1. Non-super user balance not showing
2. Strategy monitor values stuck
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
    
    # Handle PostgreSQL on Render
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def debug_all_issues():
    """Debug all reported issues"""
    db, engine = get_db_session()
    is_postgresql = "postgresql" in str(engine.url)
    
    try:
        print("🚀 COMPREHENSIVE PRODUCTION DEBUG")
        print("=" * 80)
        
        # 1. CHECK BALANCE_ENABLED SETTINGS
        print("\n📊 1. BALANCE_ENABLED STATUS CHECK")
        print("-" * 40)
        
        query = """
            SELECT bi.id, bi.name, bi.balance_enabled, u.email, u.is_superuser,
                   bi.exchange, bi.trading_pair, bi.is_active
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY u.is_superuser DESC, bi.name
        """
        
        instances = db.execute(text(query)).fetchall()
        
        balance_disabled = []
        non_super_instances = []
        
        print(f"\n{'Name':<30} {'Balance':<10} {'User':<30} {'Super':<6} {'Active':<8}")
        print("-" * 90)
        
        for inst in instances:
            id, name, balance_enabled, email, is_super, exchange, pair, is_active = inst
            balance_str = "✅" if balance_enabled else "❌"
            super_str = "Yes" if is_super else "No"
            active_str = "✅" if is_active else "❌"
            
            print(f"{name[:30]:<30} {balance_str:<10} {email[:30]:<30} {super_str:<6} {active_str:<8}")
            
            if not balance_enabled:
                balance_disabled.append((id, name, email))
            if not is_super:
                non_super_instances.append((id, name, email))
        
        if balance_disabled:
            print(f"\n⚠️  Found {len(balance_disabled)} instances with balance DISABLED!")
            for id, name, email in balance_disabled:
                print(f"   - {name} (User: {email})")
        
        # 2. CHECK RECENT BALANCE HISTORY
        print("\n\n📊 2. BALANCE HISTORY ANALYSIS")
        print("-" * 40)
        
        # Use correct SQL for each database type
        if is_postgresql:
            time_clause = "bh.timestamp > NOW() - INTERVAL '1 hour'"
        else:
            time_clause = "bh.timestamp > datetime('now', '-1 hour')"
        
        balance_query = f"""
            SELECT 
                bi.name,
                u.is_superuser,
                COUNT(bh.id) as recent_saves,
                MAX(bh.timestamp) as last_save
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            LEFT JOIN balance_history bh ON bi.id = bh.instance_id AND {time_clause}
            WHERE bi.is_active = :true_val
            GROUP BY bi.id, bi.name, u.is_superuser
            ORDER BY u.is_superuser DESC, bi.name
        """
        
        true_val = True if is_postgresql else 1
        balance_stats = db.execute(text(balance_query), {"true_val": true_val}).fetchall()
        
        print(f"\n{'Instance':<30} {'Super':<6} {'Saves (1hr)':<12} {'Last Save':<25}")
        print("-" * 75)
        
        for name, is_super, count, last_ts in balance_stats:
            super_str = "Yes" if is_super else "No"
            last_str = str(last_ts)[:19] if last_ts else "Never in last hour"
            status = "✅" if count > 0 else "❌"
            print(f"{name[:30]:<30} {super_str:<6} {status} {count:<10} {last_str:<25}")
        
        # 3. CHECK MUZAMMIL_DANI_CERBERUS SPECIFICALLY
        print("\n\n🔍 3. MUZAMMIL_DANI_CERBERUS DETAILED CHECK")
        print("-" * 40)
        
        muzammil_query = """
            SELECT bi.*, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            WHERE bi.name LIKE '%MUZAMMIL_DANI_CERBERUS%'
        """
        
        muzammil = db.execute(text(muzammil_query)).fetchone()
        
        if muzammil:
            print(f"Instance ID: {muzammil.id}")
            print(f"User: {muzammil.email} (Super: {muzammil.is_superuser})")
            print(f"Exchange: {muzammil.exchange}")
            print(f"Balance Enabled: {'✅ Yes' if muzammil.balance_enabled else '❌ No'}")
            print(f"Active: {'✅ Yes' if muzammil.is_active else '❌ No'}")
            print(f"Trading Pair: {muzammil.trading_pair or 'None'}")
            
            # Check latest balance data
            latest_balance = db.execute(text("""
                SELECT balance_data, timestamp
                FROM balance_history
                WHERE instance_id = :id
                ORDER BY timestamp DESC
                LIMIT 1
            """), {"id": muzammil.id}).fetchone()
            
            if latest_balance:
                print(f"\nLatest Balance Entry: {latest_balance.timestamp}")
                balance_data = json.loads(latest_balance.balance_data) if isinstance(latest_balance.balance_data, str) else latest_balance.balance_data
                print("Currencies:")
                for currency, amounts in balance_data.items():
                    if isinstance(amounts, dict):
                        total = amounts.get('total', 0)
                        print(f"  - {currency}: {total}")
            else:
                print("\n❌ NO BALANCE HISTORY FOUND!")
            
            # Check recent errors
            if is_postgresql:
                error_time = "timestamp > NOW() - INTERVAL '6 hours'"
            else:
                error_time = "timestamp > datetime('now', '-6 hours')"
                
            recent_errors = db.execute(text(f"""
                SELECT message, timestamp
                FROM error_logs
                WHERE instance_id = :id AND {error_time}
                ORDER BY timestamp DESC
                LIMIT 5
            """), {"id": muzammil.id}).fetchall()
            
            if recent_errors:
                print(f"\nRecent Errors:")
                for error in recent_errors:
                    print(f"  - {error.timestamp}: {error.message[:100]}")
            else:
                print("\n✅ No recent errors")
        
        # 4. CHECK STRATEGY MONITOR UPDATES
        print("\n\n📊 4. STRATEGY MONITOR UPDATE CHECK")
        print("-" * 40)
        
        # Check recent poll states for duplicates
        if is_postgresql:
            recent_time = "timestamp > NOW() - INTERVAL '30 minutes'"
        else:
            recent_time = "timestamp > datetime('now', '-30 minutes')"
            
        position_query = f"""
            SELECT 
                ps.instance_id,
                bi.name,
                ps.symbol,
                ps.data_type,
                COUNT(*) as update_count,
                COUNT(DISTINCT ps.data) as unique_values
            FROM poll_states ps
            JOIN bot_instances bi ON ps.instance_id = bi.id
            WHERE ps.data_type = 'position' AND {recent_time}
            GROUP BY ps.instance_id, bi.name, ps.symbol, ps.data_type
            HAVING COUNT(*) > 1
            ORDER BY bi.name, ps.symbol
        """
        
        position_updates = db.execute(text(position_query)).fetchall()
        
        if position_updates:
            print(f"\n{'Instance':<30} {'Symbol':<20} {'Updates':<10} {'Unique':<10}")
            print("-" * 70)
            
            stuck_monitors = []
            for inst_id, name, symbol, dtype, updates, unique in position_updates:
                status = "❌ STUCK" if unique == 1 else "✅ OK"
                print(f"{name[:30]:<30} {symbol:<20} {updates:<10} {unique:<10} {status}")
                if unique == 1:
                    stuck_monitors.append((inst_id, name, symbol))
            
            if stuck_monitors:
                print(f"\n⚠️  Found {len(stuck_monitors)} stuck position monitors!")
        else:
            print("\n✅ No position update issues found in last 30 minutes")
        
        # 5. FIX BALANCE_ENABLED IF NEEDED
        if balance_disabled:
            print("\n\n🔧 5. FIXING BALANCE_ENABLED")
            print("-" * 40)
            
            update_query = "UPDATE bot_instances SET balance_enabled = :true_value WHERE balance_enabled = :false_value"
            true_value = True if is_postgresql else 1
            false_value = False if is_postgresql else 0
            
            result = db.execute(text(update_query), {
                "true_value": true_value,
                "false_value": false_value
            })
            
            db.commit()
            print(f"✅ Enabled balance for {result.rowcount} instances")
        
        # 6. SUMMARY AND RECOMMENDATIONS
        print("\n\n📋 SUMMARY & RECOMMENDATIONS")
        print("=" * 80)
        
        issues_found = []
        
        if balance_disabled:
            issues_found.append(f"- {len(balance_disabled)} instances had balance disabled (now fixed)")
        
        if non_super_instances:
            no_balance_history = []
            for id, name, email in non_super_instances:
                count = db.execute(text("""
                    SELECT COUNT(*) FROM balance_history WHERE instance_id = :id
                """), {"id": id}).scalar()
                if count == 0:
                    no_balance_history.append(name)
            
            if no_balance_history:
                issues_found.append(f"- {len(no_balance_history)} non-super instances have NO balance history")
        
        if stuck_monitors:
            issues_found.append(f"- {len(stuck_monitors)} position monitors appear stuck")
        
        if issues_found:
            print("\n🔍 Issues Found:")
            for issue in issues_found:
                print(issue)
            
            print("\n💡 Recommendations:")
            print("1. Restart polling workers to pick up balance_enabled changes")
            print("2. Check exchange API connectivity for affected instances")
            print("3. Monitor logs for API errors or rate limits")
            print("4. Verify API credentials are valid and have correct permissions")
        else:
            print("\n✅ All systems appear to be functioning correctly!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 80)
    print("🔧 PRODUCTION ISSUES DEBUG SCRIPT")
    print("=" * 80)
    
    success = debug_all_issues()
    
    if not success:
        print("\n❌ Debug script encountered errors")
    
    sys.exit(0 if success else 1) 