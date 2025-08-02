#!/usr/bin/env python3
"""
Render Deployment Readiness Check
"""

import os
import sys
import importlib.util

def render_deployment_check():
    """Check if the Strategy Monitor System is ready for Render deployment"""
    print("🚀 RENDER DEPLOYMENT READINESS CHECK")
    print("=" * 50)
    
    checks_passed = 0
    total_checks = 6
    
    # 1. Check strategy_monitor_model
    try:
        from strategy_monitor_model import StrategyMonitor
        print("✅ 1. StrategyMonitor model imports correctly")
        
        # Check if it has the correct field by inspecting the table columns
        columns = [col.name for col in StrategyMonitor.__table__.columns]
        if 'include_pnl' in columns:
            print("✅    - include_pnl field exists")
            checks_passed += 1
        else:
            print(f"❌    - include_pnl field missing. Available columns: {columns}")
    except Exception as e:
        print(f"❌ 1. StrategyMonitor model import failed: {e}")
    
    # 2. Check strategy_monitor service
    try:
        from strategy_monitor import StrategyMonitorService
        print("✅ 2. StrategyMonitorService imports correctly")
        checks_passed += 1
    except Exception as e:
        print(f"❌ 2. StrategyMonitorService import failed: {e}")
    
    # 3. Check strategy_monitor_worker
    try:
        from strategy_monitor_worker import StrategyMonitorWorker
        print("✅ 3. StrategyMonitorWorker imports correctly")
        checks_passed += 1
    except Exception as e:
        print(f"❌ 3. StrategyMonitorWorker import failed: {e}")
    
    # 4. Check main.py has strategy monitor routes
    try:
        from main import app
        routes = [route.path for route in app.routes]
        if '/strategy-monitors' in routes:
            print("✅ 4. Strategy monitor routes exist in main.py")
            checks_passed += 1
        else:
            print("❌ 4. Strategy monitor routes missing from main.py")
    except Exception as e:
        print(f"❌ 4. Main app check failed: {e}")
    
    # 5. Check render.yaml configuration
    try:
        import yaml
        with open('render.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        services = config.get('services', [])
        monitor_service = None
        for service in services:
            if service.get('name') == 'medusa-strategy-monitor':
                monitor_service = service
                break
        
        if monitor_service:
            print("✅ 5. Strategy monitor service configured in render.yaml")
            print(f"     - Start command: {monitor_service.get('startCommand')}")
            checks_passed += 1
        else:
            print("❌ 5. Strategy monitor service missing from render.yaml")
    except Exception as e:
        print(f"❌ 5. render.yaml check failed: {e}")
    
    # 6. Check migration script
    try:
        from migration import migrate_database
        print("✅ 6. Migration script available")
        checks_passed += 1
    except Exception as e:
        print(f"❌ 6. Migration script check failed: {e}")
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed == total_checks:
        print("🎉 ALL CHECKS PASSED - READY FOR RENDER DEPLOYMENT!")
        print("\n📋 What happens on deployment:")
        print("   1. Web service starts with Strategy Monitor UI")
        print("   2. Main worker starts with polling instances")
        print("   3. Strategy Monitor worker starts automatically")
        print("   4. Database migration runs and creates tables")
        print("   5. Strategy Monitor system ready for use")
        print("\n🔗 After deployment, visit: /strategy-monitors")
        return True
    else:
        print("❌ DEPLOYMENT NOT READY - Fix issues above first")
        return False

if __name__ == "__main__":
    success = render_deployment_check()
    sys.exit(0 if success else 1)
