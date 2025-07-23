import sqlite3
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Add new columns to existing database if they don't exist"""
    try:
        database_url = settings.database_url
        logger.info("🚀 Starting database migration...")
        
        if database_url.startswith('postgresql'):
            logger.info("🐘 Running PostgreSQL migrations...")
            migrate_postgresql()
        else:
            logger.info("🗄️ Running SQLite migrations...")
            migrate_sqlite()
            
        logger.info("✅ Database migration completed!")
        
    except Exception as e:
        logger.warning(f"Migration skipped - database may not be ready yet: {e}")
        # Don't raise the exception to prevent startup failure

def check_column_exists_pg(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in PostgreSQL"""
    try:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table AND column_name = :column
        """), {"table": table_name, "column": column_name})
        return result.fetchone() is not None
    except Exception:
        return False

def check_table_exists_pg(conn, table_name: str) -> bool:
    """Check if a table exists in PostgreSQL"""
    try:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = :table
        """), {"table": table_name})
        return result.fetchone() is not None
    except Exception:
        return False

def migrate_postgresql():
    """Handle PostgreSQL migrations with enhanced error handling"""
    try:
        engine = create_engine(settings.database_url, echo=False)
        
        with engine.connect() as conn:
            # First check if bot_instances table exists
            if not check_table_exists_pg(conn, 'bot_instances'):
                logger.info("bot_instances table doesn't exist yet, skipping column migrations")
                return
            
            logger.info("✅ bot_instances table exists, checking columns...")
            
            # Define columns to add
            columns_to_add = [
                ('trading_pair', 'VARCHAR(20)', 'Trading pair filter'),
                ('telegram_topic_id', 'VARCHAR(100)', 'Telegram topic ID'),
                ('market_type', "VARCHAR(20) DEFAULT 'unified'", 'Market type (spot/futures/unified)')
            ]
            
            # Add missing columns
            for col_name, col_def, description in columns_to_add:
                if not check_column_exists_pg(conn, 'bot_instances', col_name):
                    try:
                        logger.info(f"➕ Adding {col_name} column: {description}")
                        conn.execute(text(f"ALTER TABLE bot_instances ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                        logger.info(f"✅ Successfully added {col_name} column")
                    except Exception as e:
                        logger.error(f"❌ Failed to add {col_name} column: {e}")
                        conn.rollback()
                else:
                    logger.info(f"✅ {col_name} column already exists")
            
            # Check and create users table
            if not check_table_exists_pg(conn, 'users'):
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
            
            # Check and add strategy_monitors table
            if not check_table_exists_pg(conn, 'strategy_monitors'):
                logger.info("➕ Creating strategy_monitors table...")
                try:
                    conn.execute(text("""
                        CREATE TABLE strategy_monitors (
                            id SERIAL PRIMARY KEY,
                            strategy_name VARCHAR(255) UNIQUE NOT NULL,
                            telegram_bot_token VARCHAR(255),
                            telegram_chat_id VARCHAR(255),
                            telegram_topic_id VARCHAR(255),
                            report_interval INTEGER DEFAULT 3600,
                            include_positions BOOLEAN DEFAULT TRUE,
                            include_orders BOOLEAN DEFAULT TRUE,
                            include_trades BOOLEAN DEFAULT TRUE,
                            include_pnl BOOLEAN DEFAULT TRUE,
                            max_recent_positions INTEGER DEFAULT 20,
                            is_active BOOLEAN DEFAULT TRUE,
                            last_report TIMESTAMP,
                            last_error TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP
                        )
                    """))
                    conn.commit()
                    logger.info("✅ Successfully created strategy_monitors table")
                except Exception as e:
                    logger.error(f"❌ Failed to create strategy_monitors table: {e}")
                    conn.rollback()
            else:
                logger.info("✅ strategy_monitors table already exists")
            
            # Check and update poll_states table data_type column
            if check_table_exists_pg(conn, 'poll_states'):
                if check_column_exists_pg(conn, 'poll_states', 'data_type'):
                    try:
                        # Check current column type
                        result = conn.execute(text("""
                            SELECT character_maximum_length 
                            FROM information_schema.columns 
                            WHERE table_name = 'poll_states' AND column_name = 'data_type'
                        """))
                        current_length = result.fetchone()
                        
                        if current_length and current_length[0] == 20:
                            logger.info("➕ Updating poll_states.data_type column from VARCHAR(20) to VARCHAR(100)")
                            conn.execute(text("ALTER TABLE poll_states ALTER COLUMN data_type TYPE VARCHAR(100)"))
                            conn.commit()
                            logger.info("✅ Successfully updated poll_states.data_type column")
                        else:
                            logger.info("✅ poll_states.data_type column already has correct size")
                    except Exception as e:
                        logger.error(f"❌ Failed to update poll_states.data_type column: {e}")
                        conn.rollback()
                else:
                    logger.info("poll_states.data_type column doesn't exist")
            else:
                logger.info("poll_states table doesn't exist yet")
        
        logger.info("🎉 PostgreSQL migration completed successfully")
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL migration error: {e}")
        # Don't raise the exception to prevent startup failure

def migrate_sqlite():
    """Handle SQLite migrations with enhanced logging"""
    db_path = settings.database_url.replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        logger.info("Database doesn't exist yet, will be created on first run")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(bot_instances)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        logger.info(f"Existing columns: {existing_columns}")
        
        # Define columns to add
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
        
        # Check and add strategy_monitors table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_monitors'")
        if not cursor.fetchone():
            try:
                logger.info("➕ Creating strategy_monitors table")
                cursor.execute("""
                    CREATE TABLE strategy_monitors (
                        id INTEGER PRIMARY KEY,
                        strategy_name VARCHAR(255) UNIQUE NOT NULL,
                        telegram_bot_token VARCHAR(255),
                        telegram_chat_id VARCHAR(255),
                        telegram_topic_id VARCHAR(255),
                        report_interval INTEGER DEFAULT 3600,
                        include_positions BOOLEAN DEFAULT 1,
                        include_orders BOOLEAN DEFAULT 1,
                        include_trades BOOLEAN DEFAULT 1,
                        include_pnl BOOLEAN DEFAULT 1,
                        max_recent_positions INTEGER DEFAULT 20,
                        is_active BOOLEAN DEFAULT 1,
                        last_report DATETIME,
                        last_error TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME
                    )
                """)
                logger.info("✅ Successfully created strategy_monitors table")
            except Exception as e:
                logger.error(f"❌ Failed to create strategy_monitors table: {e}")
        else:
            logger.info("✅ strategy_monitors table already exists")
        
        # Check poll_states table (SQLite doesn't support ALTER COLUMN TYPE easily)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poll_states'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(poll_states)")
            poll_columns = {column[1]: column[2] for column in cursor.fetchall()}
            if 'data_type' in poll_columns and 'VARCHAR(20)' in poll_columns['data_type']:
                logger.warning("⚠️ poll_states.data_type column is VARCHAR(20) but needs VARCHAR(100)")
                logger.warning("⚠️ SQLite doesn't easily support column type changes")
                logger.warning("⚠️ This may cause errors with long order/trade IDs")
            else:
                logger.info("✅ poll_states.data_type column has correct type or doesn't exist yet")
        else:
            logger.info("poll_states table doesn't exist yet, will be created with correct schema")
        
        conn.commit()
        logger.info("🎉 SQLite migration completed successfully")
        
    except Exception as e:
        logger.error(f"❌ SQLite migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
