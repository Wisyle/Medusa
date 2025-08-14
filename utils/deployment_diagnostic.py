#!/usr/bin/env python3
"""
Deployment diagnostic script to debug path and environment issues
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    print("=== Deployment Diagnostic Report ===")
    print(f"Python Version: {sys.version}")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Script Location: {os.path.abspath(__file__)}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    
    # Check if we're in the correct directory structure
    print("\n=== Directory Structure Check ===")
    expected_dirs = ['app', 'services', 'utils', 'models', 'migrations', 'Decter']
    for dir_name in expected_dirs:
        path = Path(dir_name)
        if path.exists():
            print(f"✅ {dir_name}/ exists")
        else:
            print(f"❌ {dir_name}/ NOT FOUND")
    
    # Check for key files
    print("\n=== Key Files Check ===")
    key_files = [
        'requirements.txt',
        'render.yaml',
        'app/main.py',
        'services/worker.py',
        'utils/fix_decter_startup.py',
        'Decter/main.py'
    ]
    for file_path in key_files:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} NOT FOUND")
    
    # List files in current directory
    print("\n=== Files in Current Directory ===")
    try:
        files = list(Path('.').iterdir())
        for f in sorted(files)[:20]:  # Show first 20 items
            print(f"  {'[DIR]' if f.is_dir() else '[FILE]'} {f.name}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more items")
    except Exception as e:
        print(f"Error listing directory: {e}")
    
    # Check environment variables
    print("\n=== Relevant Environment Variables ===")
    env_vars = ['DATABASE_URL', 'SECRET_KEY', 'ENVIRONMENT', 'PORT', 'RENDER', 'RENDER_SERVICE_NAME']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            if var in ['DATABASE_URL', 'SECRET_KEY']:
                print(f"{var}: [REDACTED]")
            else:
                print(f"{var}: {value}")
        else:
            print(f"{var}: Not set")
    
    # Try to import key modules
    print("\n=== Module Import Test ===")
    test_imports = [
        ('app.config', 'App config'),
        ('app.database', 'App database'),
        ('models.strategy_monitor_model', 'Strategy Monitor model')
    ]
    for module_name, description in test_imports:
        try:
            __import__(module_name)
            print(f"✅ {description} imports successfully")
        except ImportError as e:
            print(f"❌ {description} import failed: {e}")
    
    print("\n=== Diagnostic Complete ===")

if __name__ == "__main__":
    main()
