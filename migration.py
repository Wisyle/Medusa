import sqlite3
import os
from config import settings

def migrate_database():
    """Add new columns to existing database if they don't exist"""
    db_path = settings.database_url.replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet, will be created on first run")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(bot_instances)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'telegram_topic_id' not in columns:
            print("Adding telegram_topic_id column to bot_instances table")
            cursor.execute("ALTER TABLE bot_instances ADD COLUMN telegram_topic_id VARCHAR(100)")
        
        if 'trading_pair' not in columns:
            print("Adding trading_pair column to bot_instances table")
            cursor.execute("ALTER TABLE bot_instances ADD COLUMN trading_pair VARCHAR(20)")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Creating users table")
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
        
        conn.commit()
        print("Database migration completed successfully")
        
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
