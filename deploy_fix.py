#!/usr/bin/env python3
"""
Deployment fix script for Render
Fixes the missing needs_security_setup column issue
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_database_fix():
    """Run the database fix script"""
    try:
        logger.info("🚀 Running database fix for needs_security_setup column...")
        
        # Run the fix script
        result = subprocess.run([sys.executable, "fix_needs_security_setup.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Database fix completed successfully!")
            logger.info(result.stdout)
            return True
        else:
            logger.error("❌ Database fix failed!")
            logger.error(result.stderr)
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to run database fix: {e}")
        return False

if __name__ == "__main__":
    success = run_database_fix()
    if not success:
        sys.exit(1)
    print("🎉 Deployment fix completed!") 