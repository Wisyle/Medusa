#!/usr/bin/env python3
"""
Detailed balance debugging script for production
Focuses on API credential access and exchange connectivity
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

def test_api_credentials(api_key, api_secret, api_passphrase, exchange):
    """Test if API credentials actually work"""
    try:
        import ccxt
        
        # Initialize exchange
        exchange_class = getattr(ccxt, exchange.lower())
        exchange_obj = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_passphrase,
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # Try to fetch balance
        balance = exchange_obj.fetch_balance()
        return True, len(balance), "API credentials work"
        
    except Exception as e:
        return False, 0, str(e)

def debug_balance_issues():
    """Debug balance-related issues in detail"""
    db, engine = get_db_session()
    
    try:
        print("🔍 DETAILED BALANCE DEBUGGING...")
        
        # Get all instances with their API credentials
        print("\n=== CHECKING API CREDENTIAL ACCESS ===")
        
        instances = db.execute(text("""
            SELECT bi.id, bi.name, bi.user_id, bi.exchange, bi.balance_enabled,
                   bi.api_credential_id, bi.api_key, bi.api_secret, bi.api_passphrase,
                   u.email, u.is_superuser,
                   ac.user_id as cred_user_id, ac.is_active, ac.name as cred_name
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            LEFT JOIN api_credentials ac ON bi.api_credential_id = ac.id
            WHERE bi.is_active = TRUE
        """)).fetchall()
        
        for instance in instances:
            print(f"\n{'='*50}")
            print(f"🤖 INSTANCE: {instance[1]}")
            print(f"   Exchange: {instance[3]}")
            print(f"   User: {instance[9]} (ID: {instance[2]}, Super: {instance[10]})")
            print(f"   Balance Enabled: {instance[4]}")
            
            # Check API credential access method
            if instance[5]:  # Using API library
                print(f"   📚 Using API Library:")
                print(f"     Credential ID: {instance[5]}")
                print(f"     Credential Owner: User {instance[11]}")
                print(f"     Credential Active: {instance[12]}")
                print(f"     Credential Name: {instance[13]}")
                
                if instance[2] != instance[11]:
                    print(f"   ❌ MISMATCH: Instance user ({instance[2]}) ≠ Credential user ({instance[11]})")
                    continue
                
                if not instance[12]:
                    print(f"   ❌ CREDENTIAL INACTIVE")
                    continue
                
                # Get actual API keys from credential
                cred_details = db.execute(text("""
                    SELECT api_key, api_secret, api_passphrase 
                    FROM api_credentials 
                    WHERE id = :id AND user_id = :user_id AND is_active = TRUE
                """), {"id": instance[5], "user_id": instance[2]}).fetchone()
                
                if cred_details:
                    api_key, api_secret, api_passphrase = cred_details
                    print(f"   ✅ API Credential accessible")
                else:
                    print(f"   ❌ API Credential NOT accessible")
                    continue
                    
            else:  # Using direct API keys
                print(f"   🔑 Using Direct API Keys:")
                if instance[6] and instance[7]:
                    api_key = instance[6]
                    api_secret = instance[7]
                    api_passphrase = instance[8]
                    print(f"   ✅ Direct API keys present")
                else:
                    print(f"   ❌ No direct API keys")
                    continue
            
            # Test API connection
            print(f"   🔗 Testing API Connection...")
            success, balance_count, message = test_api_credentials(
                api_key, api_secret, api_passphrase, instance[3]
            )
            
            if success:
                print(f"   ✅ API Test: SUCCESS ({balance_count} currencies)")
            else:
                print(f"   ❌ API Test: FAILED - {message}")
        
        # Check recent balance history
        print(f"\n{'='*50}")
        print(f"📊 RECENT BALANCE HISTORY")
        
        recent_balances = db.execute(text("""
            SELECT bi.name, bh.timestamp, bh.balance_data, bh.total_value_usd
            FROM balance_history bh
            JOIN bot_instances bi ON bh.instance_id = bi.id
            ORDER BY bh.timestamp DESC
            LIMIT 10
        """)).fetchall()
        
        if recent_balances:
            for balance in recent_balances:
                print(f"   {balance[1]} - {balance[0]} - ${balance[3]} ({balance[2] if balance[2] else 'No data'})")
        else:
            print("   ❌ No balance history found")
        
        # Check error logs
        print(f"\n{'='*50}")
        print(f"🚨 RECENT ERROR LOGS")
        
        recent_errors = db.execute(text("""
            SELECT bi.name, el.timestamp, el.error_type, el.error_message
            FROM error_logs el
            LEFT JOIN bot_instances bi ON el.instance_id = bi.id
            WHERE el.error_type LIKE '%balance%' OR el.error_type LIKE '%fetch%'
            ORDER BY el.timestamp DESC
            LIMIT 10
        """)).fetchall()
        
        if recent_errors:
            for error in recent_errors:
                print(f"   {error[1]} - {error[0]} - {error[2]}: {error[3][:100]}...")
        else:
            print("   ✅ No balance-related errors found")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Balance Debug Tool - Detailed Analysis")
    success = debug_balance_issues()
    
    if success:
        print(f"\n🎉 Debug completed!")
        print(f"\n💡 Common fixes:")
        print(f"  • If API test fails: Check API key permissions on exchange")
        print(f"  • If credential mismatch: Reassign credential to correct user") 
        print(f"  • If no balance history: Check polling is active")
        print(f"  • For bitget: Ensure API keys have 'Read' permission")
    else:
        print(f"\n❌ Debug failed - check errors above")
    
    sys.exit(0 if success else 1) 