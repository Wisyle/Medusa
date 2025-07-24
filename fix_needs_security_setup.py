#!/usr/bin/env python3
"""
Fix missing needs_security_setup column in PostgreSQL database
This script adds the missing column that's causing login failures
"""

import logging
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_needs_security_setup_column():
    """Add needs_security_setup column to users table if missing"""
    try:
        logger.info("🔧 Fixing needs_security_setup column...")
        
        # Import settings
        try:
            from config import settings
        except ImportError:
            logger.error("❌ Could not import settings from config")
            return False
        
        # Create engine
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # Check if we're on PostgreSQL
        is_postgresql = settings.database_url.startswith('postgresql')
        logger.info(f"📊 Database type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
        
        with engine.connect() as conn:
            try:
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
                    
                    conn.commit()
                    logger.info("✅ Added needs_security_setup column")
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
                                conn.commit()
                                logger.info("✅ Converted column to BOOLEAN type")
                        except Exception as type_error:
                            logger.warning(f"⚠️  Could not check/convert column type: {type_error}")
                
                # Verify the fix
                updated_columns = {col['name']: col for col in inspector.get_columns('users')}
                if 'needs_security_setup' in updated_columns:
                    logger.info("🎉 Column fix completed successfully!")
                    return True
                else:
                    logger.error("❌ Column still missing after fix attempt")
                    return False
                    
            except ProgrammingError as pe:
                logger.error(f"❌ Database programming error: {pe}")
                return False
            except SQLAlchemyError as se:
                logger.error(f"❌ SQLAlchemy error: {se}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Failed to fix needs_security_setup column: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = fix_needs_security_setup_column()
        if success:
            print("✅ needs_security_setup column fix completed!")
            sys.exit(0)
        else:
            print("❌ needs_security_setup column fix failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Fix script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1) 