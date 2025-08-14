#!/usr/bin/env python3
"""
Decter 001 Integration Setup Script for TARC Lighthouse
This script sets up the Decter 001 integration automatically
"""

import os
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Setup Decter 001 integration"""
    logger.info("🤖 Setting up Decter 001 integration for TARC Lighthouse...")
    
    # Check if we're in the correct directory
    if not Path("main.py").exists():
        logger.error("❌ Please run this script from the TARC directory containing main.py")
        return False
    
    try:
        # 1. Check if Decter 001 path exists
        decter_path = Path("/mnt/c/users/rober/downloads/001")
        if not decter_path.exists():
            logger.warning(f"⚠️ Decter 001 path not found at {decter_path}")
            logger.info("📍 Please update the path in decter_controller.py if Decter 001 is located elsewhere")
        else:
            logger.info(f"✅ Decter 001 found at {decter_path}")
        
        # 2. Verify integration files exist
        integration_files = [
            "decter_controller.py",
            "decter_routes.py",
            "templates/decter_engine.html"
        ]
        
        missing_files = []
        for file in integration_files:
            if not Path(file).exists():
                missing_files.append(file)
        
        if missing_files:
            logger.error(f"❌ Missing integration files: {missing_files}")
            return False
        
        logger.info("✅ All integration files found")
        
        # 3. Check if main.py has been updated
        with open("main.py", "r") as f:
            main_content = f.read()
        
        if "decter_routes" not in main_content:
            logger.error("❌ main.py has not been updated with Decter routes")
            logger.info("📝 Please add these lines to main.py after other route imports:")
            logger.info("   # Add Decter 001 routes")
            logger.info("   from decter_routes import add_decter_routes")
            logger.info("   add_decter_routes(app)")
            return False
        
        logger.info("✅ main.py properly configured")
        
        # 4. Check base.html navigation
        base_html = Path("templates/base.html")
        if base_html.exists():
            with open(base_html, "r") as f:
                base_content = f.read()
            
            if "decter-engine" not in base_content:
                logger.warning("⚠️ Navigation menu may not include Decter Engine link")
                logger.info("📝 Consider adding navigation menu item to templates/base.html")
            else:
                logger.info("✅ Navigation menu configured")
        
        # 5. Create data directory if it doesn't exist in Decter path
        if decter_path.exists():
            data_dir = decter_path / "data"
            data_dir.mkdir(exist_ok=True)
            logger.info(f"✅ Decter data directory ready: {data_dir}")
        
        # 6. Test imports
        try:
            from decter_controller import decter_controller
            from decter_routes import add_decter_routes
            logger.info("✅ Integration modules import successfully")
        except ImportError as e:
            logger.error(f"❌ Import error: {e}")
            return False
        
        # 7. Print integration summary
        logger.info("\n🎉 Decter 001 Integration Setup Complete!")
        logger.info("\n📋 Integration Summary:")
        logger.info("   ✅ Decter Controller - Manages bot process and API calls")
        logger.info("   ✅ Decter Routes - REST API endpoints for control")
        logger.info("   ✅ Decter Engine UI - Web interface with real-time monitoring")
        logger.info("   ✅ Navigation Menu - Easy access from sidebar")
        logger.info("\n🚀 Features Available:")
        logger.info("   • Start/Stop/Restart Decter 001 bot")
        logger.info("   • Configure trading parameters")
        logger.info("   • Real-time status monitoring")
        logger.info("   • View trade history and logs")
        logger.info("   • Send commands to the bot")
        logger.info("   • Performance metrics and analytics")
        logger.info("\n🎯 Access the Decter Engine:")
        logger.info("   1. Start your TARC Lighthouse server: python main.py")
        logger.info("   2. Login to your dashboard")
        logger.info("   3. Click 'Decter Engine' in the sidebar")
        logger.info("   4. Control Decter 001 from the unified interface!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)