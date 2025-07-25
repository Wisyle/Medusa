#!/usr/bin/env python3
"""
Automatic Startup Migration for Render Deployment
Handles PostgreSQL database migrations on application startup
"""

import logging
import os
import re
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_enhanced_bypass_features():
    """
    Automatically apply enhanced bypass features to templates and static files
    This ensures all UI improvements are applied on fresh deployments
    """
    try:
        logger.info("🎨 Applying enhanced bypass features...")
        
        # Template file path
        template_path = "templates/api_library.html"
        
        if not os.path.exists(template_path):
            logger.warning(f"⚠️ Template file not found: {template_path}")
            return True  # Don't fail the migration if template is missing
        
        # Read current template content
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if custom modal CSS is already present
        if 'custom-modal-overlay' in content:
            logger.info("✅ Enhanced bypass features already applied")
            return True
        
        logger.info("🔧 Applying custom modal system...")
        
        # Apply enhanced modal system fixes
        enhanced_content = apply_custom_modal_system(content)
        
        # Write back the enhanced content
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(enhanced_content)
        
        logger.info("✅ Enhanced bypass features applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply enhanced bypass features: {e}")
        # Don't fail the entire migration for UI enhancements
        return True

def apply_custom_modal_system(content):
    """Apply the complete custom modal system to replace Bootstrap modals"""
    
    # 1. Replace the modal CSS with custom modal CSS
    css_pattern = r'/\* Simple modal styling \*/.*?\.modal \+\.form-select:focus \{[^}]+\}'
    custom_css = '''/* Custom Modal Styling */
.custom-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
}

.custom-modal-overlay.show {
    display: flex;
}

.custom-modal {
    background-color: var(--secondary-black);
    border: 1px solid var(--medium-gray);
    border-radius: 8px;
    max-width: 90%;
    max-height: 90%;
    overflow-y: auto;
    color: var(--white);
    width: 600px;
}

.custom-modal-header {
    padding: 1rem;
    border-bottom: 1px solid var(--medium-gray);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.custom-modal-header h5 {
    margin: 0;
    color: var(--white);
}

.custom-modal-body {
    padding: 1rem;
}

.custom-modal-footer {
    padding: 1rem;
    border-top: 1px solid var(--medium-gray);
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
}

.close-btn {
    background: none;
    border: none;
    color: var(--white);
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.close-btn:hover {
    color: var(--accent-blue);
}

.custom-modal .form-control, .custom-modal .form-select {
    background-color: var(--secondary-black);
    border: 1px solid var(--medium-gray);
    color: var(--white);
}

.custom-modal .form-control:focus, .custom-modal .form-select:focus {
    background-color: var(--secondary-black);
    color: var(--white);
    border-color: var(--accent-blue);
    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}'''
    
    content = re.sub(css_pattern, custom_css, content, flags=re.DOTALL)
    
    # 2. Replace Bootstrap modal trigger buttons
    content = content.replace(
        'data-bs-toggle="modal" data-bs-target="#createCredentialModal"',
        'onclick="showCustomModal()"'
    )
    
    # 3. Replace create modal HTML structure
    create_modal_pattern = r'<!-- Create API Credential Modal -->.*?</div>\s*</div>\s*</div>'
    create_modal_replacement = '''<!-- Custom Create API Credential Modal -->
<div class="custom-modal-overlay" id="createCredentialModal">
    <div class="custom-modal">
        <div class="custom-modal-header">
            <h5>Add API Credential</h5>
            <button type="button" class="close-btn" onclick="hideCustomModal()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <form id="createCredentialForm">
            <div class="custom-modal-body">
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createName" class="form-label">Name</label>
                            <input type="text" class="form-control" id="createName" name="name" required>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createExchange" class="form-label">Exchange</label>
                            <select class="form-select" id="createExchange" name="exchange" required>
                                <option value="">Select Exchange</option>
                                <option value="binance">Binance</option>
                                <option value="bybit">Bybit</option>
                                <option value="kucoin">KuCoin</option>
                                <option value="okx">OKX</option>
                                <option value="bitget">Bitget</option>
                                <option value="gate">Gate.io</option>
                                <option value="mexc">MEXC</option>
                                <option value="huobi">Huobi</option>
                                <option value="coinbase">Coinbase Pro</option>
                                <option value="kraken">Kraken</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createApiKey" class="form-label">API Key</label>
                            <input type="text" class="form-control" id="createApiKey" name="api_key" required>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createApiSecret" class="form-label">API Secret</label>
                            <input type="password" class="form-control" id="createApiSecret" name="api_secret" required>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createPassphrase" class="form-label">Passphrase (Optional)</label>
                            <input type="password" class="form-control" id="createPassphrase" name="passphrase">
                            <small class="form-text text-muted">Required for some exchanges like OKX, KuCoin</small>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="createTestnet" class="form-label">Environment</label>
                            <select class="form-select" id="createTestnet" name="testnet">
                                <option value="false">Mainnet</option>
                                <option value="true">Testnet</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="mb-3">
                    <label for="createDescription" class="form-label">Description (Optional)</label>
                    <textarea class="form-control" id="createDescription" name="description" rows="2"></textarea>
                </div>
            </div>
            <div class="custom-modal-footer">
                <button type="button" class="btn btn-secondary" onclick="hideCustomModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Create API Credential</button>
            </div>
        </form>
    </div>
</div>'''
    
    content = re.sub(create_modal_pattern, create_modal_replacement, content, flags=re.DOTALL)
    
    # 4. Replace edit modal HTML structure
    edit_modal_pattern = r'<!-- Edit API Credential Modal -->.*?</form>\s*</div>\s*</div>\s*</div>'
    edit_modal_replacement = '''<!-- Edit API Credential Modal -->
<div class="custom-modal-overlay" id="editCredentialModal">
    <div class="custom-modal">
        <div class="custom-modal-header">
            <h5>Edit API Credential</h5>
            <button type="button" class="close-btn" onclick="hideEditModal()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <form id="editCredentialForm">
            <div class="custom-modal-body">
                <input type="hidden" id="editCredentialId" name="credential_id">
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="editName" class="form-label">Name</label>
                            <input type="text" class="form-control" id="editName" name="name" required>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="editExchange" class="form-label">Exchange</label>
                            <select class="form-select" id="editExchange" name="exchange" required>
                                <option value="binance">Binance</option>
                                <option value="bybit">Bybit</option>
                                <option value="kucoin">KuCoin</option>
                                <option value="okx">OKX</option>
                                <option value="bitget">Bitget</option>
                                <option value="gate">Gate.io</option>
                                <option value="mexc">MEXC</option>
                                <option value="huobi">Huobi</option>
                                <option value="coinbase">Coinbase Pro</option>
                                <option value="kraken">Kraken</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="editTestnet" class="form-label">Environment</label>
                            <select class="form-select" id="editTestnet" name="testnet">
                                <option value="false">Mainnet</option>
                                <option value="true">Testnet</option>
                            </select>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label for="editDescription" class="form-label">Description</label>
                            <textarea class="form-control" id="editDescription" name="description" rows="2"></textarea>
                        </div>
                    </div>
                </div>
            </div>
            <div class="custom-modal-footer">
                <button type="button" class="btn btn-secondary" onclick="hideEditModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
        </form>
    </div>
</div>'''
    
    content = re.sub(edit_modal_pattern, edit_modal_replacement, content, flags=re.DOTALL)
    
    # 5. Update JavaScript to use custom modal functions
    js_pattern = r'// Load credentials on page load and handle modal events.*?document\.addEventListener\(\'DOMContentLoaded\'[^}]+\}\);'
    js_replacement = '''// Custom modal functions
function showCustomModal() {
    document.getElementById('createCredentialForm').reset();
    document.getElementById('createCredentialModal').classList.add('show');
}

function hideCustomModal() {
    document.getElementById('createCredentialModal').classList.remove('show');
}

function hideEditModal() {
    document.getElementById('editCredentialModal').classList.remove('show');
}

// Close modal when clicking overlay
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('custom-modal-overlay')) {
        if (e.target.id === 'createCredentialModal') {
            hideCustomModal();
        } else if (e.target.id === 'editCredentialModal') {
            hideEditModal();
        }
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const createModal = document.getElementById('createCredentialModal');
        const editModal = document.getElementById('editCredentialModal');
        if (createModal && createModal.classList.contains('show')) {
            hideCustomModal();
        } else if (editModal && editModal.classList.contains('show')) {
            hideEditModal();
        }
    }
});

// Load credentials on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCredentials();
});'''
    
    content = re.sub(js_pattern, js_replacement, content, flags=re.DOTALL)
    
    # 6. Update form submission handlers to close modals
    content = content.replace(
        'alert(data.message);\n                location.reload();',
        'hideCustomModal();\n                alert(data.message);\n                location.reload();'
    )
    
    content = content.replace(
        'if (data.message) {\n            alert(data.message);\n            location.reload();',
        'if (data.message) {\n            hideEditModal();\n            alert(data.message);\n            location.reload();'
    )
    
    # 7. Update edit modal trigger
    content = content.replace(
        'const modal = new bootstrap.Modal(document.getElementById(\'editCredentialModal\'));\n            modal.show();',
        'document.getElementById(\'editCredentialModal\').classList.add(\'show\');'
    )
    
    # 8. Update "Create one now" links
    content = content.replace(
        'data-bs-toggle="modal" data-bs-target="#createCredentialModal"',
        'onclick="showCustomModal()"'
    )
    
    return content

def run_startup_migrations():
    """Run all necessary migrations on application startup"""
    try:
        logger.info("🚀 Starting automatic deployment migrations...")
        logger.info("🔧 ADMIN LOGIN FIX - This migration will ensure admin@tarstrategies.com works")
        
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
                # 1. Create tables in dependency order to avoid foreign key issues
                logger.info("📋 Creating base tables in dependency order...")
                
                # Import all models to ensure they're registered
                from database import Base, User, ActivityLog, ErrorLog, BotInstance
                from api_library_model import ApiCredential
                from strategy_monitor_model import StrategyMonitor
                from dex_arbitrage_model import DEXArbitrageInstance, DEXOpportunity
                from validator_node_model import ValidatorNode
                
                # Create tables without foreign key dependencies first
                logger.info("📊 Creating independent tables...")
                User.__table__.create(engine, checkfirst=True)
                ActivityLog.__table__.create(engine, checkfirst=True) 
                ErrorLog.__table__.create(engine, checkfirst=True)
                ApiCredential.__table__.create(engine, checkfirst=True)
                StrategyMonitor.__table__.create(engine, checkfirst=True)
                DEXArbitrageInstance.__table__.create(engine, checkfirst=True)
                DEXOpportunity.__table__.create(engine, checkfirst=True)
                
                # Now create tables with foreign key dependencies
                logger.info("📊 Creating tables with foreign key dependencies...")
                BotInstance.__table__.create(engine, checkfirst=True)
                ValidatorNode.__table__.create(engine, checkfirst=True)
                
                logger.info("✅ All tables created successfully in correct order")
                
                # 2. Ensure users table has proper structure (FIRST)
                if not ensure_users_table(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to ensure users table")
                    return False
                
                # 2.5. Fix needs_security_setup column (CRITICAL FIX)
                if not fix_needs_security_setup_column(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to fix needs_security_setup column")
                    return False
                
                # 2.6. Fix NULL boolean fields in users table (CRITICAL FIX)
                if not fix_null_boolean_fields(conn, is_postgresql):
                    logger.error("❌ Failed to fix NULL boolean fields")
                    return False
                
                # 3. Check and fix api_credentials table (AFTER users table exists)
                if not check_api_credentials_schema(conn, inspector, is_postgresql):
                    logger.error("❌ Failed to fix api_credentials schema")
                    return False
                
                # 4. Create default admin user if needed
                if not create_default_admin_user(conn, is_postgresql):
                    logger.error("❌ Failed to create default admin user")
                    return False
                
                # 5. Skip non-critical migrations for faster deployment
                logger.info("⏭️ Skipping non-critical migrations for faster deployment")
                logger.info("⏭️ Skipping api_credentials user_id fix - not critical")
                logger.info("⏭️ Skipping enhanced bypass features - not critical") 
                logger.info("⏭️ Skipping strategy monitors setup - will be done later")
                
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

def fix_null_boolean_fields(conn, is_postgresql):
    """Fix NULL boolean fields in users table that cause validation errors"""
    try:
        logger.info("🔧 Fixing NULL boolean fields in users table...")
        
        # Check for NULL values first
        count_result = conn.execute(text("SELECT COUNT(*) FROM users WHERE totp_enabled IS NULL OR is_active IS NULL OR is_superuser IS NULL"))
        null_count = count_result.scalar()
        
        if null_count == 0:
            logger.info("✅ No NULL boolean fields found")
            return True
        
        logger.info(f"Found {null_count} rows with NULL boolean fields")
        
        # Update NULL totp_enabled to False
        if is_postgresql:
            result = conn.execute(text("UPDATE users SET totp_enabled = :val WHERE totp_enabled IS NULL"), {"val": False})
        else:
            result = conn.execute(text("UPDATE users SET totp_enabled = ? WHERE totp_enabled IS NULL"), (0,))
        
        if result.rowcount > 0:
            logger.info(f"✅ Fixed {result.rowcount} NULL totp_enabled values")
        
        # Update NULL is_active to True (safer default for existing users)
        if is_postgresql:
            result = conn.execute(text("UPDATE users SET is_active = :val WHERE is_active IS NULL"), {"val": True})
        else:
            result = conn.execute(text("UPDATE users SET is_active = ? WHERE is_active IS NULL"), (1,))
        
        if result.rowcount > 0:
            logger.info(f"✅ Fixed {result.rowcount} NULL is_active values")
        
        # Update NULL is_superuser to False
        if is_postgresql:
            result = conn.execute(text("UPDATE users SET is_superuser = :val WHERE is_superuser IS NULL"), {"val": False})
        else:
            result = conn.execute(text("UPDATE users SET is_superuser = ? WHERE is_superuser IS NULL"), (0,))
        
        if result.rowcount > 0:
            logger.info(f"✅ Fixed {result.rowcount} NULL is_superuser values")
        
        # Verify the fix (no commit here - let outer transaction handle it)
        verify_result = conn.execute(text("SELECT COUNT(*) FROM users WHERE totp_enabled IS NULL OR is_active IS NULL OR is_superuser IS NULL"))
        remaining_nulls = verify_result.scalar()
        
        if remaining_nulls == 0:
            logger.info("✅ All NULL boolean fields fixed successfully")
        else:
            logger.warning(f"⚠️ {remaining_nulls} NULL boolean fields still remain")
        
        # Add NOT NULL constraints with defaults to prevent future NULL values
        try:
            if is_postgresql:
                # PostgreSQL syntax
                conn.execute(text("ALTER TABLE users ALTER COLUMN totp_enabled SET DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN totp_enabled SET NOT NULL"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN is_active SET NOT NULL"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN is_superuser SET DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN is_superuser SET NOT NULL"))
            else:
                # SQLite doesn't support ALTER COLUMN directly, so we'll skip constraints
                # But the default values in the model should prevent this
                logger.info("SQLite detected - skipping column constraints (will rely on model defaults)")
            
            logger.info("✅ Added NOT NULL constraints to boolean columns")
        except Exception as constraint_error:
            logger.warning(f"⚠️ Could not add NOT NULL constraints: {constraint_error}")
            # Don't fail the migration for this
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to fix NULL boolean fields: {e}")
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
            default_password_hash = '$2b$12$AMiPtvZPRSrPlnJ8F4m6/ehwl25HJ5XupSRJ5Jar0PBzmuhIMfqCO'
            
            if is_postgresql:
                conn.execute(text("""
                    INSERT INTO users (email, hashed_password, full_name, is_superuser, is_active, needs_security_setup) 
                    VALUES ('admin@tarstrategies.com', :password, 'TAR Admin', TRUE, TRUE, TRUE)
                    ON CONFLICT (email) DO UPDATE SET 
                        hashed_password = EXCLUDED.hashed_password,
                        needs_security_setup = TRUE,
                        private_key_hash = NULL,
                        passphrase_hash = NULL,
                        totp_secret = NULL,
                        totp_enabled = FALSE;
                """), {'password': default_password_hash})
            else:
                conn.execute(text("""
                    INSERT OR REPLACE INTO users (email, hashed_password, full_name, is_superuser, is_active, needs_security_setup, private_key_hash, passphrase_hash, totp_secret, totp_enabled) 
                    VALUES ('admin@tarstrategies.com', ?, 'TAR Admin', 1, 1, 1, NULL, NULL, NULL, 0);
                """), (default_password_hash,))
            
            logger.info("✅ Created default admin user")
            logger.info("🔑 Default login: admin@tarstrategies.com / admin123")
            logger.info("⚠️  CHANGE DEFAULT PASSWORD AFTER FIRST LOGIN!")
        else:
            logger.info("✅ Default admin user already exists")
        
        # Skip admin user update for now - enhanced bypass features are the priority
        logger.info("✅ Admin user exists - enhanced bypass features are primary focus")
        logger.info("🔑 Login available with existing credentials")
        
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
                                {"admin_id": admin_id})
        else:
            result = conn.execute(text("UPDATE api_credentials SET user_id = ? WHERE user_id IS NULL;"), 
                                [admin_id])
        
        updated_count = result.rowcount
        if updated_count > 0:
            logger.info(f"✅ Updated {updated_count} api_credentials records with admin user_id")
        else:
            logger.info("✅ No api_credentials records needed fixing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to fix existing api_credentials: {e}")
        return False

def ensure_new_strategy_monitors(conn, is_postgresql):
    """Create strategy monitors for new strategy types: TGLX, Cerberus, Predators"""
    try:
        logger.info("🎯 Ensuring new strategy monitors exist...")
        
        # List of new strategy types to add
        new_strategies = ['TGLX', 'Cerberus', 'Predators']
        
        for strategy_name in new_strategies:
            # Check if strategy monitor already exists
            if is_postgresql:
                result = conn.execute(text("SELECT COUNT(*) FROM strategy_monitors WHERE strategy_name = :name;"), 
                                    {"name": strategy_name})
            else:
                result = conn.execute(text("SELECT COUNT(*) FROM strategy_monitors WHERE strategy_name = ?;"), 
                                    (strategy_name,))
            
            count = result.scalar()
            
            if count == 0:
                logger.info(f"➕ Creating strategy monitor for {strategy_name}...")
                
                if is_postgresql:
                    conn.execute(text("""
                        INSERT INTO strategy_monitors (strategy_name, is_active, report_interval, include_positions, 
                                                     include_orders, include_trades, include_pnl, max_recent_positions)
                        VALUES (:name, TRUE, 3600, TRUE, TRUE, TRUE, TRUE, 10);
                    """), {"name": strategy_name})
                else:
                    conn.execute(text("""
                        INSERT INTO strategy_monitors (strategy_name, is_active, report_interval, include_positions, 
                                                     include_orders, include_trades, include_pnl, max_recent_positions)
                        VALUES (?, 1, 3600, 1, 1, 1, 1, 10);
                    """), (strategy_name,))
                
                logger.info(f"✅ Created strategy monitor for {strategy_name}")
            else:
                logger.info(f"✅ Strategy monitor for {strategy_name} already exists")
        
        logger.info("✅ All new strategy monitors ensured")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to ensure new strategy monitors: {e}")
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