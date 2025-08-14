#!/bin/bash
# TGL MEDUSA Main Application Startup Script

# Exit on any error
set -e

echo "🚀 Starting TGL MEDUSA Application..."

# Set Python path
export PYTHONPATH=/app

# Run database migrations (optional, based on environment variable)
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "📊 Running database migrations..."
    python migrations/migration.py
fi

# Start the main application
echo "▶️ Starting web server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
