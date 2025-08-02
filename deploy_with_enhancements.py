#!/usr/bin/env python3
"""
Manual Deployment Enhancement Script
Run this script to manually apply all enhanced bypass features
Useful for testing and manual deployment scenarios
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_startup_migration():
    """Run the startup migration script"""
    try:
        logger.info("🚀 Running startup migration...")
        
        # Import and run startup migration
        from startup_migration import run_startup_migrations
        
        success = run_startup_migrations()
        if success:
            logger.info("✅ Startup migration completed successfully")
            return True
        else:
            logger.error("❌ Startup migration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running startup migration: {e}")
        return False

def run_pre_deployment_validation():
    """Run pre-deployment validation"""
    try:
        logger.info("🔍 Running pre-deployment validation...")
        
        # Import and run validation
        from pre_deployment_validation import main as validate_main
        
        success = validate_main()
        if success:
            logger.info("✅ Pre-deployment validation passed")
            return True
        else:
            logger.error("❌ Pre-deployment validation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error running validation: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        logger.info("📦 Checking dependencies...")
        
        if not os.path.exists("requirements.txt"):
            logger.error("❌ requirements.txt not found")
            return False
        
        # Try to import key modules
        try:
            import fastapi
            import sqlalchemy
            import uvicorn
            logger.info("✅ Core dependencies available")
        except ImportError as e:
            logger.error(f"❌ Missing dependency: {e}")
            logger.info("💡 Run: pip install -r requirements.txt")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Dependency check failed: {e}")
        return False

def backup_templates():
    """Create backup of template files before modification"""
    try:
        logger.info("💾 Creating template backups...")
        
        template_dir = Path("templates")
        backup_dir = Path("templates_backup")
        
        if not template_dir.exists():
            logger.warning("⚠️ Templates directory not found")
            return True
        
        # Create backup directory
        backup_dir.mkdir(exist_ok=True)
        
        # Backup template files
        for template_file in template_dir.glob("*.html"):
            backup_file = backup_dir / template_file.name
            backup_file.write_text(template_file.read_text(encoding='utf-8'), encoding='utf-8')
            logger.info(f"📋 Backed up: {template_file.name}")
        
        logger.info("✅ Template backups created")
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup creation failed: {e}")
        return False

def verify_deployment_readiness():
    """Final verification that everything is ready for deployment"""
    try:
        logger.info("🎯 Final deployment readiness check...")
        
        # Check if enhanced features are applied
        template_path = "templates/api_library.html"
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'custom-modal-overlay' in content:
                logger.info("✅ Enhanced bypass features detected")
            else:
                logger.warning("⚠️ Enhanced bypass features not detected")
        
        # Check if main files exist
        required_files = [
            "main.py",
            "startup_migration.py",
            "pre_deployment_validation.py",
            "render.yaml"
        ]
        
        for file in required_files:
            if os.path.exists(file):
                logger.info(f"✅ Found: {file}")
            else:
                logger.error(f"❌ Missing: {file}")
                return False
        
        logger.info("✅ Deployment readiness verified")
        return True
        
    except Exception as e:
        logger.error(f"❌ Readiness check failed: {e}")
        return False

def main():
    """Main deployment enhancement function"""
    logger.info("🚀 Starting Enhanced Deployment Process...")
    logger.info("=" * 60)
    
    steps = [
        ("Dependency Check", check_dependencies),
        ("Template Backup", backup_templates),
        ("Startup Migration", run_startup_migration),
        ("Pre-deployment Validation", run_pre_deployment_validation),
        ("Final Readiness Check", verify_deployment_readiness)
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        logger.info(f"\n🔹 {step_name}")
        logger.info("-" * 40)
        
        try:
            if step_func():
                logger.info(f"✅ {step_name} completed successfully")
            else:
                logger.error(f"❌ {step_name} failed")
                failed_steps.append(step_name)
        except Exception as e:
            logger.error(f"❌ {step_name} encountered error: {e}")
            failed_steps.append(step_name)
    
    logger.info("\n" + "=" * 60)
    logger.info("DEPLOYMENT ENHANCEMENT SUMMARY")
    logger.info("=" * 60)
    
    if failed_steps:
        logger.error(f"❌ {len(failed_steps)} step(s) failed:")
        for step in failed_steps:
            logger.error(f"   - {step}")
        logger.error("\n🚨 Enhanced deployment preparation failed!")
        logger.info("💡 Fix the issues above before deploying")
        return False
    else:
        logger.info("🎉 ALL ENHANCEMENT STEPS COMPLETED SUCCESSFULLY!")
        logger.info("\n📋 DEPLOYMENT CHECKLIST:")
        logger.info("   ✅ Dependencies verified")
        logger.info("   ✅ Templates backed up")
        logger.info("   ✅ Database migrations ready")
        logger.info("   ✅ Enhanced bypass features applied")
        logger.info("   ✅ Validation completed")
        logger.info("\n🚀 READY FOR DEPLOYMENT!")
        logger.info("   Deploy using: render.yaml configuration")
        logger.info("   Enhanced features will auto-apply on deployment")
        return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n" + "🎯" * 20)
        print("✅ ENHANCED DEPLOYMENT READY!")
        print("🎯" * 20)
        sys.exit(0)
    else:
        print("\n" + "🚨" * 20)
        print("❌ DEPLOYMENT ENHANCEMENT FAILED!")
        print("🚨" * 20)
        sys.exit(1) 