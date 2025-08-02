#!/usr/bin/env python3
"""
Emergency rollback script for TGL MEDUSA API Library deployment
Use this only if there are critical issues after deployment
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a shell command and return success status"""
    try:
        logger.info(f"🔄 {description}...")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ {description} completed")
            return True
        else:
            logger.error(f"❌ {description} failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"❌ {description} failed with exception: {e}")
        return False

def check_git_status():
    """Check current git status"""
    try:
        result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            logger.warning("⚠️  Uncommitted changes detected:")
            logger.warning(result.stdout)
            return False
        return True
    except Exception as e:
        logger.error(f"❌ Git status check failed: {e}")
        return False

def get_last_commit():
    """Get the last commit hash"""
    try:
        result = subprocess.run("git rev-parse HEAD", shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"❌ Failed to get last commit: {e}")
        return None

def perform_rollback():
    """Perform the rollback"""
    logger.info("🚨 EMERGENCY ROLLBACK INITIATED")
    logger.info("This will revert the API Library changes")
    
    # Confirm rollback
    confirm = input("⚠️  Are you sure you want to rollback? Type 'ROLLBACK' to confirm: ")
    if confirm != "ROLLBACK":
        logger.info("❌ Rollback cancelled")
        return False
    
    # Check git status
    if not check_git_status():
        logger.error("❌ Please commit or stash changes first")
        return False
    
    current_commit = get_last_commit()
    if not current_commit:
        return False
    
    logger.info(f"📝 Current commit: {current_commit}")
    
    # Create rollback steps
    steps = [
        ("git log --oneline -5", "Showing recent commits"),
        ("git revert HEAD --no-edit", "Reverting last commit"),
        ("git push origin main", "Pushing rollback to repository")
    ]
    
    logger.info("🔄 Executing rollback steps...")
    
    for command, description in steps:
        if not run_command(command, description):
            logger.error(f"❌ Rollback failed at step: {description}")
            logger.error("🚨 Manual intervention required!")
            return False
    
    logger.info("✅ Rollback completed successfully!")
    logger.info("📋 Next steps:")
    logger.info("   1. Wait for Render to redeploy (automatic)")
    logger.info("   2. Verify services are working")
    logger.info("   3. Check database integrity")
    logger.info("   4. Investigate the original issue")
    
    return True

def show_safe_rollback_info():
    """Show information about why rollback is safe"""
    logger.info("ℹ️  ROLLBACK SAFETY INFORMATION:")
    logger.info("   ✅ Database changes are additive only - no data loss")
    logger.info("   ✅ Existing bot instances will continue working")
    logger.info("   ✅ Only new API Library features will be disabled")
    logger.info("   ✅ No breaking changes to existing functionality")
    logger.info("")

def main():
    """Main rollback function"""
    logger.info("🚨 TGL MEDUSA Emergency Rollback Script")
    logger.info("Use this only if there are critical issues after deployment")
    
    show_safe_rollback_info()
    
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        logger.error("❌ Not in a git repository!")
        sys.exit(1)
    
    # Perform rollback
    success = perform_rollback()
    
    if success:
        logger.info("🎉 Rollback completed successfully!")
        logger.info("Monitor your Render dashboard for redeployment status")
    else:
        logger.error("❌ Rollback failed - manual intervention required")
        logger.error("Contact your team for assistance")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
