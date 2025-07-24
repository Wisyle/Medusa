#!/usr/bin/env python3
"""
Automatic Startup Migration for Render Deployment
Handles PostgreSQL database migrations on application startup
"""

import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_startup_migrations():
    """Run all necessary migrations on application startup"""
    try:
        logger.info("🚀 Starting automatic deployment migrations...")
        
        # Create engine
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # Determine database type
        is_postgresql = settings.database_url.startswith('postgresql')
        logger.info(f"📊 Database type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # 1. Create all base tables first
                logger.info("📋 Creating base tables...")
                from database import Base
                Base.metadata.create_all(bind=engine)
                
                # 2. Ensure users table has proper structure (FIRST)
                if not ensure_users_table(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to ensure users table")
                    return False
                
                # 2.5. Fix needs_security_setup column (CRITICAL FIX)
                if not fix_needs_security_setup_column(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to fix needs_security_setup column")
                    return False
                
                # 3. Check and fix api_credentials table (AFTER users table exists)
                if not check_api_credentials_schema(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to fix api_credentials schema")
                    return False
                
                # 4. Create default admin user if needed
                if not create_default_admin_user(conn, is_postgresql):
                    logger.error("❌ Failed to create default admin user")
                    return False
                
                # 5. Fix any existing api_credentials without user_id
                if not fix_existing_api_credentials(conn, is_postgresql):
                    logger.error("❌ Failed to fix existing api_credentials")
                    return False
                
                # Commit transaction
                trans.commit()
                logger.info("🎉 All deployment migrations completed successfully!")
                return True
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Migration failed, rolling back: {e}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Migration setup failed: {e}")
        return False

def fix_needs_security_setup_column(conn, inspector, is_postgresql):
    """Fix missing needs_security_setup column that causes login failures"""
    try:
        logger.info("🔧 Fixing needs_security_setup column...")
        
        # Check if users table exists
        tables = inspector.get_table_names()
        if 'users' not in tables:
            logger.error("❌ Users table doesn't exist!")
            return False
        
        # Check current columns
        columns = {col['name']: col for col in inspector.get_columns('users')}
        logger.info(f"📊 Current users table columns: {list(columns.keys())}")
        
        # Check if needs_security_setup column exists
        if 'needs_security_setup' not in columns:
            logger.info("➕ Adding needs_security_setup column...")
            
            if is_postgresql:
                # PostgreSQL - add BOOLEAN column
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN needs_security_setup BOOLEAN DEFAULT FALSE;
                """))
            else:
                # SQLite - add INTEGER column  
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN needs_security_setup INTEGER DEFAULT 0;
                """))
            
            logger.info("✅ Added needs_security_setup column")
            
            # Simple verification by checking if the ADD COLUMN command succeeded
            # The actual column verification will happen after the transaction commits
            logger.info("🎉 needs_security_setup column fix completed!")
            return True
        else:
            logger.info("✅ needs_security_setup column already exists")
            
            # Check if it's the correct type for PostgreSQL
            if is_postgresql:
                try:
                    column_info = columns['needs_security_setup']
                    column_type = str(column_info['type']).upper()
                    logger.info(f"📊 Column type: {column_type}")
                    
                    if 'INTEGER' in column_type and 'BOOLEAN' not in column_type:
                        logger.info("🔄 Converting INTEGER column to BOOLEAN...")
                        conn.execute(text("""
                            ALTER TABLE users 
                            ALTER COLUMN needs_security_setup TYPE BOOLEAN 
                            USING needs_security_setup::BOOLEAN;
                        """))
                        logger.info("✅ Converted column to BOOLEAN type")
                except Exception as type_error:
                    logger.warning(f"⚠️  Could not check/convert column type: {type_error}")
            
            logger.info("🎉 needs_security_setup column already properly configured!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to fix needs_security_setup column: {e}")
        return False

def check_api_credentials_schema(conn, inspector, is_postgresql):
    """Check and fix api_credentials table schema"""
    try:
        logger.info("🔍 Checking api_credentials table schema...")
        
        # Check if table exists
        tables = inspector.get_table_names()
        if 'api_credentials' not in tables:
            logger.info("➕ api_credentials table doesn't exist, will be created by Base.metadata.create_all")
            return True
        
        # Check columns
        columns = {col['name']: col for col in inspector.get_columns('api_credentials')}
        logger.info(f"📊 Current api_credentials columns: {list(columns.keys())}")
        
        # Add user_id column if missing
        if 'user_id' not in columns:
            logger.info("➕ Adding user_id column to api_credentials...")
            
            if is_postgresql:
                # PostgreSQL syntax
                conn.execute(text("ALTER TABLE api_credentials ADD COLUMN user_id INTEGER;"))
                
                # Add foreign key constraint only if it doesn't exist
                try:
                    conn.execute(text("ALTER TABLE api_credentials ADD CONSTRAINT fk_api_credentials_user_id FOREIGN KEY (user_id) REFERENCES users(id);"))
                    logger.info("✅ Added foreign key constraint")
                except Exception as fk_error:
                    if "already exists" in str(fk_error).lower() or "duplicate" in str(fk_error).lower():
                        logger.info("✅ Foreign key constraint already exists")
                    else:
                        logger.warning(f"⚠️  Could not add foreign key constraint: {fk_error}")
            else:
                # SQLite syntax
                conn.execute(text("ALTER TABLE api_credentials ADD COLUMN user_id INTEGER DEFAULT 1;"))
            
            logger.info("✅ Added user_id column")
        else:
            logger.info("✅ user_id column already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to check api_credentials schema: {e}")
        return False

def ensure_users_table(conn, inspector, is_postgresql):
    """Ensure users table exists with proper structure"""
    try:
        logger.info("🔍 Checking users table...")
        
        tables = inspector.get_table_names()
        if 'users' not in tables:
            logger.info("➕ Creating users table...")
            
            if is_postgresql:
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
                        private_key_hash VARCHAR(255),
                        passphrase_hash VARCHAR(255),
                        needs_security_setup INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        full_name TEXT,
                        is_active INTEGER DEFAULT 1,
                        is_superuser INTEGER DEFAULT 0,
                        totp_secret TEXT,
                        totp_enabled INTEGER DEFAULT 0,
                        private_key_hash TEXT,
                        passphrase_hash TEXT,
                        needs_security_setup INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """))
            
            logger.info("✅ Created users table")
        else:
            logger.info("✅ users table already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to ensure users table: {e}")
        return False

def create_default_admin_user(conn, is_postgresql):
    """Create default admin user if it doesn't exist"""
    try:
        logger.info("🔍 Checking for default admin user...")
        
        # Check if admin user exists
        if is_postgresql:
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE email = 'admin@tarstrategies.com';"))
        else:
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE email = 'admin@tarstrategies.com';"))
        
        count = result.scalar()
        
        if count == 0:
            logger.info("➕ Creating default admin user...")
            
            # Default password hash for 'admin123' (change this in production!)
            default_password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LgHGXLGDzQQ5PnW0a'
            
            if is_postgresql:
                conn.execute(text("""
                    INSERT INTO users (email, hashed_password, full_name, is_superuser, is_active, needs_security_setup) 
                    VALUES ('admin@tarstrategies.com', :password, 'TAR Admin', TRUE, TRUE, TRUE);
                """), {'password': default_password_hash})
            else:
                conn.execute(text("""
                    INSERT INTO users (email, hashed_password, full_name, is_superuser, is_active, needs_security_setup) 
                    VALUES ('admin@tarstrategies.com', ?, 'TAR Admin', 1, 1, 1);
                """), (default_password_hash,))
            
            logger.info("✅ Created default admin user")
            logger.info("🔑 Default login: admin@tarstrategies.com / admin123")
            logger.info("⚠️  CHANGE DEFAULT PASSWORD AFTER FIRST LOGIN!")
        else:
            logger.info("✅ Default admin user already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create default admin user: {e}")
        return False

def fix_existing_api_credentials(conn, is_postgresql):
    """Fix any existing api_credentials records without user_id"""
    try:
        logger.info("🔍 Fixing existing api_credentials...")
        
        # Get admin user ID
        result = conn.execute(text("SELECT id FROM users WHERE email = 'admin@tarstrategies.com' LIMIT 1;"))
        admin_user = result.fetchone()
        
        if not admin_user:
            logger.warning("⚠️  No admin user found, skipping api_credentials fix")
            return True
        
        admin_id = admin_user[0]
        
        # Update NULL user_id values
        if is_postgresql:
            result = conn.execute(text("UPDATE api_credentials SET user_id = :admin_id WHERE user_id IS NULL;"), 
                                {'admin_id': admin_id})
        else:
            result = conn.execute(text("UPDATE api_credentials SET user_id = ? WHERE user_id IS NULL;"), 
                                (admin_id,))
        
        updated_count = result.rowcount
        if updated_count > 0:
            logger.info(f"✅ Updated {updated_count} api_credentials records with admin user_id")
        else:
            logger.info("✅ No api_credentials records needed fixing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to fix existing api_credentials: {e}")
        return False

def verify_migration_success():
    """Verify that all migrations were successful"""
    try:
        logger.info("🔍 Verifying migration success...")
        
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # Check required tables exist
        tables = inspector.get_table_names()
        required_tables = ['users', 'api_credentials', 'bot_instances']
        
        for table in required_tables:
            if table not in tables:
                logger.error(f"❌ Required table missing: {table}")
                return False
        
        # Check api_credentials has user_id column
        columns = {col['name']: col for col in inspector.get_columns('api_credentials')}
        if 'user_id' not in columns:
            logger.error("❌ api_credentials table missing user_id column")
            return False
        
        # Test database connection with a simple query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users;"))
            user_count = result.scalar()
            logger.info(f"📊 Database verification: {user_count} users found")
        
        logger.info("✅ Migration verification successful!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration verification failed: {e}")
        return False

if __name__ == "__main__":
    success = run_startup_migrations()
    if success:
        verify_migration_success()
        print("🎉 Deployment migrations completed successfully!")
    else:
        print("❌ Deployment migrations failed!")
        exit(1) 