#!/bin/bash
"""
Render Startup Script for Strategy Monitor Worker
"""

# Exit on any error
set -e

echo "🚀 Starting TGL MEDUSA Strategy Monitor Worker..."

# Set Python path
export PYTHONPATH=/app

# Run database migrations and initialization
echo "📊 Running database migrations..."
python migrations/migration.py

echo "🎯 Initializing Strategy Monitor System..."
python utils/init_strategy_monitor.py

echo "▶️ Starting Strategy Monitor Worker..."
exec python services/strategy_monitor_worker.py
