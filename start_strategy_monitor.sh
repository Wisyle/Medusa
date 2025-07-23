#!/bin/bash
"""
Render Startup Script for Strategy Monitor Worker
"""

# Exit on any error
set -e

echo "🚀 Starting TGL MEDUSA Strategy Monitor Worker..."

# Run database migrations and initialization
echo "📊 Running database migrations..."
python migration.py

echo "🎯 Initializing Strategy Monitor System..."
python init_strategy_monitor.py

echo "▶️ Starting Strategy Monitor Worker..."
exec python strategy_monitor_worker.py
