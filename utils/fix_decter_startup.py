#!/usr/bin/env python3
"""
Fix Decter startup issues on Render deployment
Ensures data directory and required files exist
"""

import os
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_decter_startup():
    """Ensure Decter data directory and files are properly set up"""
    
    # Determine if we're in production (Render)
    is_production = os.getenv("ENVIRONMENT") == "production"
    
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"ENVIRONMENT variable: {os.getenv('ENVIRONMENT')}")
    
    if is_production:
        logger.info("🚀 Running in production environment (Render)")
        decter_path = Path("Decter")
    else:
        logger.info("💻 Running in development environment")
        decter_path = Path("/mnt/c/users/rober/downloads/tarc/Decter")
    
    logger.info(f"Decter path: {decter_path}")
    logger.info(f"Decter path exists: {decter_path.exists()}")
    
    if decter_path.exists():
        main_py = decter_path / "main.py"
        logger.info(f"main.py exists: {main_py.exists()}")
    
    # Create data directory
    data_dir = decter_path / "data"
    
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Data directory created/verified: {data_dir}")
        
        # Create required files if they don't exist
        required_files = [
            "subprocess.log",
            "trading_bot.log", 
            "engine_logs.json",
            "live_logs.json",
            "trading_stats.json",
            "saved_params.json",
            "version.json"
        ]
        
        for filename in required_files:
            file_path = data_dir / filename
            if not file_path.exists():
                if filename.endswith('.json'):
                    # Create empty JSON files
                    file_path.write_text('{}')
                else:
                    # Create empty log files
                    file_path.touch()
                logger.info(f"✅ Created {filename}")
            else:
                logger.info(f"✓ {filename} already exists")
        
        # Set proper permissions (if possible)
        try:
            for file_path in data_dir.iterdir():
                os.chmod(file_path, 0o666)  # Read/write for all
            logger.info("✅ File permissions set")
        except Exception as e:
            logger.warning(f"⚠️ Could not set file permissions: {e}")
        
        logger.info("✅ Decter startup fix completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during startup fix: {e}")
        return False

if __name__ == "__main__":
    success = fix_decter_startup()
    sys.exit(0 if success else 1)
