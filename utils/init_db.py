#!/usr/bin/env python3
"""
Database initialization script for TGL MEDUSA
This script creates all database tables and runs migrations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db
from migrations.migration import migrate_database

def main():
    """Initialize database tables and run migrations"""
    try:
        print("Creating database tables...")
        init_db()
        print("Tables created successfully!")
        
        print("Running database migrations...")
        migrate_database()
        print("Migrations completed successfully!")
        
        print("Database initialization complete!")
        
    except Exception as e:
        print(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
