#!/usr/bin/env python3
"""
Fix balance display and strategy monitor issues:
1. Update balance_enabled default to TRUE in migrations
2. Enable balance for existing instances  
3. Fix strategy monitor polling
"""

import os
import re

print("🔧 FIXING BALANCE AND STRATEGY MONITOR ISSUES...")
print("=" * 60)

# 1. Fix migration files to use TRUE as default
files_to_fix = [
    ('startup_migration.py', [
        ('balance_enabled BOOLEAN DEFAULT FALSE', 'balance_enabled BOOLEAN DEFAULT TRUE'),
        ('balance_enabled INTEGER DEFAULT 0', 'balance_enabled INTEGER DEFAULT 1')
    ]),
    ('main.py', [
        ('balance_enabled BOOLEAN DEFAULT FALSE', 'balance_enabled BOOLEAN DEFAULT TRUE'),
        ('balance_enabled BOOLEAN DEFAULT 0', 'balance_enabled BOOLEAN DEFAULT 1')
    ])
]

for filename, replacements in files_to_fix:
    if os.path.exists(filename):
        print(f"\n📝 Updating {filename}...")
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                modified = True
                print(f"   ✅ Changed: {old} → {new}")
        
        if modified:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"   ✅ {filename} updated!")
        else:
            print(f"   ℹ️ No changes needed in {filename}")

# 2. Create SQL migration to enable balance for existing instances
print("\n📝 Creating SQL migration script...")
sql_migration = """-- Enable balance tracking for all existing instances
UPDATE bot_instances SET balance_enabled = true WHERE balance_enabled = false OR balance_enabled IS NULL;

-- Show results
SELECT name, balance_enabled, user_id FROM bot_instances ORDER BY name;"""

with open('enable_balance_migration.sql', 'w', encoding='utf-8') as f:
    f.write(sql_migration)
print("   ✅ Created enable_balance_migration.sql")

# 3. Create a runtime fix script
print("\n📝 Creating runtime fix script...")
runtime_fix = """#!/usr/bin/env python3
\"\"\"
Enable balance for all instances and clear stale poll states
\"\"\"

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
        result = db.execute(text(\"\"\"
            UPDATE bot_instances 
            SET balance_enabled = true 
            WHERE balance_enabled = false OR balance_enabled IS NULL
        \"\"\"))
        db.commit()
        print(f"✅ Updated {result.rowcount} instances")
        
        # Clear old poll states that might be stuck
        print("\\n🧹 Clearing stale poll states...")
        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = db.execute(text(\"\"\"
            DELETE FROM poll_states 
            WHERE timestamp < :cutoff
        \"\"\"), {'cutoff': cutoff})
        db.commit()
        print(f"✅ Cleared {result.rowcount} old poll states")
        
        # Clear strategy monitor states to force refresh
        print("\\n🔄 Resetting strategy monitor states...")
        result = db.execute(text("DELETE FROM strategy_monitor_state"))
        db.commit()
        print(f"✅ Cleared {result.rowcount} monitor states")
        
        # Show current status
        print("\\n📊 Current instance status:")
        instances = db.execute(text(\"\"\"
            SELECT bi.name, bi.balance_enabled, u.email, u.is_superuser
            FROM bot_instances bi
            LEFT JOIN users u ON bi.user_id = u.id
            ORDER BY u.is_superuser DESC, bi.name
        \"\"\")).fetchall()
        
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
"""

with open('fix_runtime_issues.py', 'w', encoding='utf-8') as f:
    f.write(runtime_fix)
print("   ✅ Created fix_runtime_issues.py")

print("\n✅ ALL FIXES APPLIED!")
print("\n📋 Next steps:")
print("1. Run 'python fix_runtime_issues.py' on your server to enable balance for existing instances")
print("2. The balance logic has been fixed to show even without active coin")
print("3. Migration defaults changed to TRUE for new instances")
print("4. Strategy monitor states will be cleared to force refresh") 