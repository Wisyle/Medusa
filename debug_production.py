#!/usr/bin/env python3
"""
Production debug and fix script
Run this directly on your Render server via terminal
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

def debug_and_fix():
    """Debug and fix production database issues"""
    db, engine = get_db_session()
    
    try:
        print("🔍 DEBUGGING PRODUCTION DATABASE...")
        
        # Check users
        print("\n=== USERS ===")
        users = db.execute(text("SELECT id, email, is_superuser FROM users")).fetchall()
        for user in users:
            print(f"ID: {user[0]}, Email: {user[1]}, Super: {user[2]}")
        
        # Check API credentials
        print("\n=== API CREDENTIALS ===")
        try:
            creds = db.execute(text("SELECT id, user_id, name, is_active, exchange FROM api_credentials")).fetchall()
            for cred in creds:
                print(f"ID: {cred[0]}, User: {cred[1]}, Name: {cred[2]}, Active: {cred[3]}, Exchange: {cred[4]}")
        except Exception as e:
            print(f"No API credentials table or error: {e}")
        
        # Check bot instances
        print("\n=== BOT INSTANCES ===")
        instances = db.execute(text("""
            SELECT id, name, user_id, exchange, balance_enabled, 
                   api_credential_id, api_key, is_active 
            FROM bot_instances
        """)).fetchall()
        
        instances_without_user = []
        instances_with_api_issues = []
        
        for instance in instances:
            print(f"\n--- {instance[1]} ---")
            print(f"  ID: {instance[0]}")
            print(f"  User ID: {instance[2]}")
            print(f"  Exchange: {instance[3]}")
            print(f"  Balance Enabled: {instance[4]}")
            print(f"  API Credential ID: {instance[5]}")
            print(f"  Has Direct API Key: {'Yes' if instance[6] else 'No'}")
            print(f"  Active: {instance[7]}")
            
            if not instance[2]:  # No user_id
                instances_without_user.append(instance)
                print(f"  ❌ NO USER ASSIGNED!")
            
            if not instance[5] and not instance[6]:  # No API access
                instances_with_api_issues.append(instance)
                print(f"  ❌ NO API CREDENTIALS!")
        
        # Fix issues
        print(f"\n🔧 FIXING ISSUES...")
        changes_made = []
        
        # Fix instances without user_id
        if instances_without_user:
            print(f"Found {len(instances_without_user)} instances without user_id")
            
            # Get first regular user, or admin if no regular users
            regular_user = db.execute(text("SELECT id, email FROM users WHERE is_superuser = FALSE LIMIT 1")).fetchone()
            if not regular_user:
                regular_user = db.execute(text("SELECT id, email FROM users WHERE is_superuser = TRUE LIMIT 1")).fetchone()
            
            if regular_user:
                print(f"Assigning to user: {regular_user[1]} (ID: {regular_user[0]})")
                
                for instance in instances_without_user:
                    db.execute(text(
                        "UPDATE bot_instances SET user_id = :user_id WHERE id = :instance_id"
                    ), {"user_id": regular_user[0], "instance_id": instance[0]})
                    changes_made.append(f"Assigned {instance[1]} to {regular_user[1]}")
                
                db.commit()
                print(f"✅ Updated {len(instances_without_user)} instances")
        
        # Summary
        print(f"\n📊 SUMMARY:")
        print(f"  Total Users: {len(users)}")
        print(f"  Total Instances: {len(instances)}")
        print(f"  Instances Fixed: {len(changes_made)}")
        
        if changes_made:
            print(f"\n✅ CHANGES MADE:")
            for change in changes_made:
                print(f"  - {change}")
        else:
            print(f"\n✅ No fixes needed - all instances properly configured")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Production Database Debug & Fix Tool")
    success = debug_and_fix()
    
    if success:
        print("\n🎉 Debug completed successfully!")
        print("\n💡 Next steps:")
        print("  1. Restart your worker service")
        print("  2. Check if balance notifications now work")
        print("  3. Monitor strategy reports for proper position display")
    else:
        print("\n❌ Debug failed - check errors above")
    
    sys.exit(0 if success else 1) 