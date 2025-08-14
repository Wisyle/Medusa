#!/usr/bin/env python3
"""
Standalone Migration Script
Run this when you need to apply database migrations without restarting the web service.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from migrations.migration import migrate_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("🚀 Starting standalone database migration...")
    migrate_database()
    logger.info("✅ Migration completed!") 