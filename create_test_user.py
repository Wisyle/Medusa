#!/usr/bin/env python3
"""
Create a test user for authentication
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all models to avoid relationship issues
from database import init_db, SessionLocal, User
from api_library_model import ApiCredential
from strategy_monitor_model import StrategyMonitor
from auth import get_password_hash

def create_test_user():
    """Create a test user"""
    # Initialize database first
    init_db()
    
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == 'admin@test.com').first()
        if existing_user:
            print("✅ Test user already exists: admin@test.com")
            return existing_user
        
        # Create new user
        hashed_password = get_password_hash('password123')
        user = User(
            email='admin@test.com',
            hashed_password=hashed_password,
            full_name='Admin User',
            is_active=True,
            totp_enabled=False
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ Test user created successfully!")
        print(f"   Email: {user.email}")
        print(f"   Password: password123")
        print(f"   Full Name: {user.full_name}")
        
        return user
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
