#!/usr/bin/env python3
"""
Create default admin user for TAR Lighthouse
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, User
from app.auth import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.email == "admin@tarstrategies.com").first()
        
        if admin:
            print("Admin user already exists. Updating password...")
            admin.hashed_password = get_password_hash("admin123")
            admin.is_active = True
            admin.is_superuser = True
            admin.needs_security_setup = True
            db.commit()
            print("✅ Admin password updated to: admin123")
        else:
            print("Creating new admin user...")
            admin = User(
                email="admin@tarstrategies.com",
                full_name="TAR Admin",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True,
                needs_security_setup=True,
                totp_enabled=False
            )
            db.add(admin)
            db.commit()
            print("✅ Admin user created successfully!")
        
        print("\n📧 Login credentials:")
        print("   Email: admin@tarstrategies.com")
        print("   Password: admin123")
        print("\n⚠️  Change password after first login!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
