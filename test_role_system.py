#!/usr/bin/env python3
"""
Test script to verify the enhanced role system works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_db, User, Role, Permission, UserRole
from sqlalchemy.orm import Session

def test_role_system():
    """Test the role system functionality"""
    print("Testing enhanced role system...")
    
    try:
        print("Initializing database...")
        init_db()
        print("✅ Database initialization successful")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    try:
        db = next(get_db())
        
        roles = db.query(Role).all()
        print(f"✅ Found {len(roles)} roles in database:")
        for role in roles:
            print(f"  - {role.name}: {role.description}")
        
        permissions = db.query(Permission).all()
        print(f"✅ Found {len(permissions)} permissions in database")
        
        admin_user = db.query(User).filter(User.is_superuser == True).first()
        if admin_user:
            print(f"✅ Found admin user: {admin_user.email}")
            
            has_dashboard_read = admin_user.has_permission('dashboard', 'read')
            has_admin_role = admin_user.has_role('admin')
            permissions_list = admin_user.get_permissions()
            
            print(f"  - Has dashboard read permission: {has_dashboard_read}")
            print(f"  - Has admin role: {has_admin_role}")
            print(f"  - Total permissions: {len(permissions_list)}")
        else:
            print("⚠️  No admin user found")
        
        db.close()
        print("✅ Role system test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Role system test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_role_system()
    sys.exit(0 if success else 1)
