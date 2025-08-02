#!/usr/bin/env python3
"""
Quick test script for Decter 001 integration
Tests the basic functionality without starting the full server
"""

import sys
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all integration modules can be imported"""
    try:
        from decter_controller import decter_controller, DecterStatus, DecterConfig
        from decter_routes import decter_router
        logger.info("✅ All modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False


def test_controller_initialization():
    """Test controller initialization"""
    try:
        from decter_controller import decter_controller
        
        # Test status check (should not fail even if Decter isn't running)
        status = decter_controller.get_status()
        logger.info(f"✅ Controller status check: {status['status']}")
        
        # Test configuration methods
        config = decter_controller._get_current_config()
        logger.info(f"✅ Config loading: {config is not None}")
        
        # Test available options
        indices = decter_controller._get_available_indices()
        currencies = decter_controller._get_available_currencies()
        logger.info(f"✅ Available indices: {len(indices)}")
        logger.info(f"✅ Available currencies: {len(currencies)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Controller test error: {e}")
        return False


def test_file_structure():
    """Test that all required files exist"""
    required_files = [
        "decter_controller.py",
        "decter_routes.py",
        "templates/decter_engine.html",
        "DECTER_INTEGRATION.md",
        "setup_decter_integration.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"❌ Missing files: {missing_files}")
        return False
    
    logger.info("✅ All required files present")
    return True


def test_main_py_integration():
    """Test that main.py has been properly updated"""
    try:
        with open("main.py", "r") as f:
            content = f.read()
        
        if "decter_routes" not in content:
            logger.error("❌ main.py missing Decter routes import")
            return False
        
        if "add_decter_routes" not in content:
            logger.error("❌ main.py missing Decter routes addition")
            return False
        
        if "decter-engine" not in content:
            logger.error("❌ main.py missing Decter Engine page route")
            return False
        
        logger.info("✅ main.py properly integrated")
        return True
    except Exception as e:
        logger.error(f"❌ main.py check error: {e}")
        return False


def test_template_integration():
    """Test that templates are properly set up"""
    try:
        # Check base.html for navigation
        with open("templates/base.html", "r") as f:
            base_content = f.read()
        
        if "decter-engine" not in base_content:
            logger.warning("⚠️ base.html may be missing Decter Engine navigation")
        else:
            logger.info("✅ Navigation menu updated")
        
        # Check decter_engine.html structure
        with open("templates/decter_engine.html", "r") as f:
            template_content = f.read()
        
        required_elements = [
            "extends \"base.html\"",
            "Decter Engine",
            "controlDecter",
            "refreshAllData"
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in template_content:
                missing_elements.append(element)
        
        if missing_elements:
            logger.error(f"❌ Template missing elements: {missing_elements}")
            return False
        
        logger.info("✅ Template structure validated")
        return True
    except Exception as e:
        logger.error(f"❌ Template check error: {e}")
        return False


def main():
    """Run all integration tests"""
    logger.info("🧪 Testing Decter 001 Integration...")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Module Imports", test_imports),
        ("Controller Initialization", test_controller_initialization),
        ("Main.py Integration", test_main_py_integration),
        ("Template Integration", test_template_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
    
    logger.info(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Integration is ready to use.")
        logger.info("\n🚀 Next Steps:")
        logger.info("1. Start TARC Lighthouse: python main.py")
        logger.info("2. Login to your dashboard")
        logger.info("3. Click 'Decter Engine' in the sidebar")
        logger.info("4. Start controlling Decter 001!")
        return True
    else:
        logger.error("❌ Some tests failed. Please check the integration setup.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)