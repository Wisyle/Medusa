#!/usr/bin/env python3
"""
Script to create an admin superuser for testing the admin user management functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, User
from app.auth import get_password_hash
from sqlalchemy.orm import Session

def create_admin_user():
    """Create an admin superuser"""
    print("Creating admin superuser...")
    
    try:
        db = next(get_db())
        
        existing_admin = db.query(User).filter(User.email == "admin@example.com").first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.email}")
            print(f"Is superuser: {existing_admin.is_superuser}")
            print(f"Is active: {existing_admin.is_active}")
            return existing_admin
        
        admin_user = User(
            email="admin@example.com",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            totp_enabled=False
        )
        
        db.add(admin_user)
        db.commit()
        
        print(f"✅ Admin user created successfully!")
        print(f"  Email: {admin_user.email}")
        print(f"  Full Name: {admin_user.full_name}")
        print(f"  Is Superuser: {admin_user.is_superuser}")
        print(f"  Is Active: {admin_user.is_active}")
        
        return admin_user
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
