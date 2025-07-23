#!/usr/bin/env python3
"""
Post-deployment validation script for TGL MEDUSA API Library
Run this after deployment to verify everything is working correctly
"""

import sys
import os
import json
import requests
import time
from datetime import datetime

def test_health_endpoint(base_url):
    """Test the health endpoint and migration status"""
    try:
        print("🏥 Testing health endpoint...")
        response = requests.get(f"{base_url}/api/health", timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
        
        data = response.json()
        print(f"✅ Health endpoint responding: {data['status']}")
        
        # Check migration status
        migration_status = data.get('migration_status', 'unknown')
        print(f"🔄 Migration status: {migration_status}")
        
        if migration_status == "completed":
            print("✅ API Library migration completed successfully")
            return True
        elif migration_status == "in_progress":
            print("⏳ Migration still in progress, waiting...")
            return False
        else:
            print(f"❌ Migration failed: {data.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_web_interface(base_url):
    """Test that the web interface is accessible"""
    try:
        print("🌐 Testing web interface...")
        
        # Test main dashboard
        response = requests.get(base_url, timeout=30)
        if response.status_code != 200:
            print(f"❌ Dashboard not accessible: {response.status_code}")
            return False
        print("✅ Dashboard accessible")
        
        # Test API Library page
        response = requests.get(f"{base_url}/api-library", timeout=30)
        if response.status_code not in [200, 302]:  # 302 might be redirect to login
            print(f"❌ API Library page not accessible: {response.status_code}")
            return False
        print("✅ API Library page accessible")
        
        return True
        
    except Exception as e:
        print(f"❌ Web interface test failed: {e}")
        return False

def test_api_endpoints(base_url):
    """Test key API endpoints"""
    try:
        print("🔌 Testing API endpoints...")
        
        # Test instances endpoint
        response = requests.get(f"{base_url}/api/instances", timeout=30)
        if response.status_code == 200:
            instances = response.json()
            print(f"✅ Instances API working ({len(instances)} instances)")
        else:
            print(f"⚠️  Instances API returned {response.status_code} (might need auth)")
        
        # Test API Library endpoints
        response = requests.get(f"{base_url}/api/api-credentials", timeout=30)
        if response.status_code in [200, 401, 403]:  # Auth required is OK
            print("✅ API Library endpoints accessible")
        else:
            print(f"❌ API Library endpoints failed: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ API endpoints test failed: {e}")
        return False

def validate_deployment(base_url, max_wait_minutes=10):
    """Main validation function"""
    print(f"🚀 Starting post-deployment validation for: {base_url}")
    print(f"📅 Time: {datetime.now().isoformat()}")
    
    # Wait for migration to complete
    print(f"\n⏳ Waiting for migration to complete (max {max_wait_minutes} minutes)...")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while time.time() - start_time < max_wait_seconds:
        if test_health_endpoint(base_url):
            print("✅ Migration completed!")
            break
        print("⏳ Migration still in progress, waiting 30 seconds...")
        time.sleep(30)
    else:
        print("❌ Migration did not complete within timeout")
        return False
    
    # Run additional tests
    tests = [
        ("Web Interface", lambda: test_web_interface(base_url)),
        ("API Endpoints", lambda: test_api_endpoints(base_url))
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print(f"{'='*50}")
        
        if not test_func():
            failed_tests.append(test_name)
    
    # Summary
    print(f"\n{'='*50}")
    print("POST-DEPLOYMENT VALIDATION SUMMARY")
    print(f"{'='*50}")
    
    if failed_tests:
        print(f"❌ {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"   - {test}")
        print("\n🚨 Some issues detected - please investigate!")
        return False
    else:
        print("✅ All tests passed!")
        print("🎉 Deployment validation successful!")
        print("\n📋 Next steps:")
        print("   1. Test creating an API credential at /api-library")
        print("   2. Create a new bot instance using the API Library")
        print("   3. Verify existing instances are still working")
        print("   4. Monitor strategy monitor timing for accuracy")
        return True

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python post_deployment_validation.py <BASE_URL>")
        print("Example: python post_deployment_validation.py https://your-app.onrender.com")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    success = validate_deployment(base_url)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
