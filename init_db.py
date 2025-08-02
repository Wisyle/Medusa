#!/usr/bin/env python3
"""
Database initialization script for TGL MEDUSA
This script creates all database tables and runs migrations.
"""

from database import init_db
from migration import migrate_database
import sys

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
