#!/usr/bin/env python3
"""
Pre-Deployment Validation Script
Ensures all enhanced bypass features are properly applied before deployment
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_enhanced_bypass_features():
    """Validate that enhanced bypass features are properly applied"""
    try:
        logger.info("🔍 Validating enhanced bypass features...")
        
        # Check if template file exists
        template_path = "templates/api_library.html"
        if not os.path.exists(template_path):
            logger.error(f"❌ Template file not found: {template_path}")
            return False
        
        # Read template content
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Validate required elements are present
        required_elements = [
            'custom-modal-overlay',  # Custom modal CSS class
            'showCustomModal()',     # Custom modal JavaScript function
            'hideCustomModal()',     # Custom modal close function
            'hideEditModal()',       # Edit modal close function
            'onclick="showCustomModal()"',  # Modal trigger
            'custom-modal-header',   # Modal header styling
            'custom-modal-body',     # Modal body styling
            'custom-modal-footer'    # Modal footer styling
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in content:
                missing_elements.append(element)
        
        if missing_elements:
            logger.error(f"❌ Missing enhanced bypass elements: {missing_elements}")
            return False
        
        logger.info("✅ All enhanced bypass features validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return False

def validate_static_files():
    """Validate that required static files are present"""
    try:
        logger.info("📁 Validating static files...")
        
        static_dir = Path("static")
        if not static_dir.exists():
            logger.warning("⚠️ Static directory not found, but this is not critical")
            return True
        
        # Check for important static files
        important_files = [
            "lighthouse-logo.svg",
            "lighthouse-login.gif"
        ]
        
        for file in important_files:
            file_path = static_dir / file
            if file_path.exists():
                logger.info(f"✅ Found static file: {file}")
            else:
                logger.warning(f"⚠️ Static file not found: {file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Static file validation failed: {e}")
        return True  # Don't fail deployment for static files

def validate_database_migration_readiness():
    """Validate that database migration system is ready"""
    try:
        logger.info("🗄️ Validating database migration readiness...")
        
        # Check if startup_migration.py exists
        if not os.path.exists("startup_migration.py"):
            logger.error("❌ startup_migration.py not found")
            return False
        
        # Check if main.py has the migration import
        if not os.path.exists("main.py"):
            logger.error("❌ main.py not found")
            return False
        
        with open("main.py", 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        if 'run_startup_migrations()' not in main_content:
            logger.error("❌ Startup migrations not integrated in main.py")
            return False
        
        logger.info("✅ Database migration system validated")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database migration validation failed: {e}")
        return False

def validate_environment_setup():
    """Validate environment configuration"""
    try:
        logger.info("🌍 Validating environment setup...")
        
        # Check for critical environment indicators
        required_files = [
            "requirements.txt",
            "config.py",
            "database.py"
        ]
        
        for file in required_files:
            if not os.path.exists(file):
                logger.error(f"❌ Required file not found: {file}")
                return False
            else:
                logger.info(f"✅ Found required file: {file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Environment validation failed: {e}")
        return False

def main():
    """Main validation function"""
    logger.info("🚀 Starting pre-deployment validation...")
    
    validations = [
        ("Environment Setup", validate_environment_setup),
        ("Database Migration Readiness", validate_database_migration_readiness),
        ("Enhanced Bypass Features", validate_enhanced_bypass_features),
        ("Static Files", validate_static_files)
    ]
    
    failed_validations = []
    
    for name, validation_func in validations:
        logger.info(f"🔍 Running validation: {name}")
        if not validation_func():
            failed_validations.append(name)
        else:
            logger.info(f"✅ {name} validation passed")
    
    if failed_validations:
        logger.error(f"❌ Validation failed for: {', '.join(failed_validations)}")
        logger.error("🛑 Pre-deployment validation failed!")
        return False
    else:
        logger.info("🎉 All pre-deployment validations passed!")
        logger.info("🚀 Ready for deployment with enhanced bypass features!")
        return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("✅ PRE-DEPLOYMENT VALIDATION SUCCESSFUL!")
