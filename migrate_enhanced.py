#!/usr/bin/env python3
"""
Enhanced migration system for database schema updates
This ensures all database changes are applied properly on Render
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from config import settings
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Could not inspect {table_name} columns: {e}")
        return False

def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists"""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return table_name in tables
    except Exception as e:
        logger.warning(f"Could not inspect tables: {e}")
        return False

def migrate_postgresql_enhanced():
    """Enhanced PostgreSQL migrations with better error handling"""
    try:
        engine = create_engine(settings.database_url, echo=False)
        
        with engine.connect() as conn:
            # Check if bot_instances table exists
            if not check_table_exists(engine, 'bot_instances'):
                logger.info("bot_instances table doesn't exist yet, skipping column migrations")
                return
            
            logger.info("✅ bot_instances table exists, checking columns...")
            
            # List of columns to add with their definitions
            columns_to_add = [
                {
                    'name': 'trading_pair',
                    'definition': 'VARCHAR(20)',
                    'description': 'Trading pair filter'
                },
                {
                    'name': 'telegram_topic_id',
                    'definition': 'VARCHAR(100)',
                    'description': 'Telegram topic ID for forum groups'
                },
                {
                    'name': 'market_type',
                    'definition': "VARCHAR(20) DEFAULT 'unified'",
                    'description': 'Market type (spot/futures/unified)'
                }
            ]
            
            # Add missing columns
            for col in columns_to_add:
                if not check_column_exists(engine, 'bot_instances', col['name']):
                    try:
                        logger.info(f"➕ Adding {col['name']} column: {col['description']}")
                        conn.execute(text(f"ALTER TABLE bot_instances ADD COLUMN {col['name']} {col['definition']}"))
                        conn.commit()
                        logger.info(f"✅ Successfully added {col['name']} column")
                    except Exception as e:
                        logger.error(f"❌ Failed to add {col['name']} column: {e}")
                        conn.rollback()
                else:
                    logger.info(f"✅ {col['name']} column already exists")
            
            # Check and create users table
            if not check_table_exists(engine, 'users'):
                try:
                    logger.info("➕ Creating users table")
                    conn.execute(text("""
                        CREATE TABLE users (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            hashed_password VARCHAR(255) NOT NULL,
                            full_name VARCHAR(255),
                            is_active BOOLEAN DEFAULT TRUE,
                            is_superuser BOOLEAN DEFAULT FALSE,
                            totp_secret VARCHAR(255),
                            totp_enabled BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.commit()
                    logger.info("✅ Successfully created users table")
                except Exception as e:
                    logger.error(f"❌ Failed to create users table: {e}")
                    conn.rollback()
            else:
                logger.info("✅ users table already exists")
        
        logger.info("🎉 PostgreSQL migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL migration error: {e}")
        return False

def migrate_sqlite_enhanced():
    """Enhanced SQLite migrations"""
    try:
        db_path = settings.database_url.replace('sqlite:///', '')
        
        if not os.path.exists(db_path):
            logger.info("Database doesn't exist yet, will be created on first run")
            return True
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check existing columns
            cursor.execute("PRAGMA table_info(bot_instances)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            logger.info(f"Existing columns: {existing_columns}")
            
            # List of columns to add
            columns_to_add = [
                ('telegram_topic_id', 'VARCHAR(100)', 'Telegram topic ID'),
                ('trading_pair', 'VARCHAR(20)', 'Trading pair filter'),
                ('market_type', "VARCHAR(20) DEFAULT 'unified'", 'Market type')
            ]
            
            for col_name, col_def, description in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        logger.info(f"➕ Adding {col_name} column: {description}")
                        cursor.execute(f"ALTER TABLE bot_instances ADD COLUMN {col_name} {col_def}")
                        logger.info(f"✅ Successfully added {col_name} column")
                    except Exception as e:
                        logger.error(f"❌ Failed to add {col_name} column: {e}")
                else:
                    logger.info(f"✅ {col_name} column already exists")
            
            # Check and create users table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                try:
                    logger.info("➕ Creating users table")
                    cursor.execute("""
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            hashed_password VARCHAR(255) NOT NULL,
                            full_name VARCHAR(255),
                            is_active BOOLEAN DEFAULT 1,
                            is_superuser BOOLEAN DEFAULT 0,
                            totp_secret VARCHAR(255),
                            totp_enabled BOOLEAN DEFAULT 0,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    logger.info("✅ Successfully created users table")
                except Exception as e:
                    logger.error(f"❌ Failed to create users table: {e}")
            else:
                logger.info("✅ users table already exists")
            
            conn.commit()
            logger.info("🎉 SQLite migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ SQLite migration error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"❌ SQLite migration error: {e}")
        return False

def migrate_database_enhanced():
    """Enhanced database migration with detailed logging"""
    logger.info("🚀 Starting database migration...")
    
    try:
        database_url = settings.database_url
        logger.info(f"Database URL: {database_url.split('@')[0]}@***")  # Hide credentials
        
        if database_url.startswith('postgresql'):
            logger.info("🐘 Running PostgreSQL migrations...")
            success = migrate_postgresql_enhanced()
        else:
            logger.info("🗄️ Running SQLite migrations...")
            success = migrate_sqlite_enhanced()
        
        if success:
            logger.info("✅ Database migration completed successfully!")
        else:
            logger.error("❌ Database migration failed!")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Migration failed - database may not be ready yet: {e}")
        return False

if __name__ == "__main__":
    migrate_database_enhanced()
