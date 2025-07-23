#!/usr/bin/env python3
"""
Deployment Validation Script for Strategy Monitor System
"""

import sys
import os
import importlib.util

def check_file_exists(file_path, description):
    """Check if a file exists"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False

def check_import(module_name, description):
    """Check if a module can be imported"""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            print(f"✅ {description}: {module_name}")
            return True
        else:
            print(f"❌ {description}: {module_name} - NOT FOUND")
            return False
    except Exception as e:
        print(f"❌ {description}: {module_name} - ERROR: {e}")
        return False

def validate_deployment():
    """Validate Strategy Monitor System deployment"""
    print("🚀 TGL MEDUSA Strategy Monitor System - Deployment Validation")
    print("=" * 70)
    
    all_good = True
    
    # Check core files
    files_to_check = [
        ("strategy_monitor_model.py", "Strategy Monitor Database Model"),
        ("strategy_monitor.py", "Strategy Monitor Service"),
        ("strategy_monitor_worker.py", "Strategy Monitor Worker"),
        ("init_strategy_monitor.py", "Strategy Monitor Initialization"),
        ("templates/strategy_monitors.html", "Strategy Monitor Web Template"),
        ("render.yaml", "Render Deployment Config"),
        ("requirements.txt", "Python Dependencies"),
        ("migration.py", "Database Migration Script"),
    ]
    
    print("\n📁 File Validation:")
    for file_path, description in files_to_check:
        if not check_file_exists(file_path, description):
            all_good = False
    
    # Check imports
    print("\n📦 Import Validation:")
    imports_to_check = [
        ("strategy_monitor_model", "Strategy Monitor Model"),
        ("strategy_monitor", "Strategy Monitor Service"),
        ("strategy_monitor_worker", "Strategy Monitor Worker"),
        ("database", "Database Module"),
        ("migration", "Migration Module"),
        ("main", "Main Application"),
    ]
    
    for module_name, description in imports_to_check:
        if not check_import(module_name, description):
            all_good = False
    
    # Check render.yaml configuration
    print("\n🚀 Render Configuration:")
    try:
        import yaml
        with open("render.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        services = config.get("services", [])
        strategy_monitor_service = None
        
        for service in services:
            if service.get("name") == "medusa-strategy-monitor":
                strategy_monitor_service = service
                break
        
        if strategy_monitor_service:
            print("✅ Strategy Monitor Service found in render.yaml")
            print(f"   - Type: {strategy_monitor_service.get('type')}")
            print(f"   - Start Command: {strategy_monitor_service.get('startCommand')}")
        else:
            print("❌ Strategy Monitor Service NOT found in render.yaml")
            all_good = False
            
    except Exception as e:
        print(f"❌ Error reading render.yaml: {e}")
        all_good = False
    
    # Check database migration
    print("\n🗄️ Database Migration:")
    try:
        from migration import migrate_database
        print("✅ Migration function available")
    except Exception as e:
        print(f"❌ Migration function error: {e}")
        all_good = False
    
    print("\n" + "=" * 70)
    if all_good:
        print("🎉 ALL CHECKS PASSED - Strategy Monitor System ready for deployment!")
        print("\n📋 Deployment Checklist:")
        print("   1. ✅ All required files present")
        print("   2. ✅ All modules importable")
        print("   3. ✅ Render configuration updated")
        print("   4. ✅ Database migration ready")
        print("\n🚀 Ready to deploy to Render!")
    else:
        print("❌ VALIDATION FAILED - Please fix the issues above before deploying")
    
    return all_good

if __name__ == "__main__":
    success = validate_deployment()
    sys.exit(0 if success else 1)
