#!/usr/bin/env python3
"""
Render Startup Performance Fix
Diagnoses and fixes slow startup issues on Render deployment
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_optimized_dockerfile():
    """Generate optimized Dockerfile for faster startup"""
    content = """FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check with simple endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start with environment variable to skip migrations
ENV SKIP_MIGRATIONS=true
ENV PYTHONUNBUFFERED=1

# Use single worker for better resource usage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop"]
"""
    
    with open('Dockerfile.optimized', 'w') as f:
        f.write(content)
    logger.info("✅ Created optimized Dockerfile")

def generate_startup_script():
    """Generate startup script with proper initialization"""
    content = """#!/bin/bash
# Render startup script with optimizations

echo "🚀 Starting TAR Lighthouse Dashboard..."

# Set environment variables for fast startup
export SKIP_MIGRATIONS=true
export PYTHONUNBUFFERED=1
export WORKER_TIMEOUT=30

# Check database connectivity first
echo "🔍 Checking database connection..."
python -c "
import os
from sqlalchemy import create_engine, text
import sys
import time

db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('❌ DATABASE_URL not set!')
    sys.exit(1)

try:
    engine = create_engine(db_url, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Database connection check failed!"
    exit 1
fi

# Start the application
echo "🚀 Starting web server..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --loop uvloop \
    --timeout-keep-alive 120 \
    --limit-concurrency 100
"""
    
    with open('start.sh', 'w') as f:
        f.write(content)
    os.chmod('start.sh', 0o755)
    logger.info("✅ Created optimized startup script")

def main():
    """Generate all optimization files"""
    logger.info("🔧 Generating Render startup optimizations...")
    
    generate_optimized_dockerfile()
    generate_startup_script()
    
    logger.info("\n📋 Next steps:")
    logger.info("1. Update render.yaml to use: startCommand: './start.sh'")
    logger.info("2. Add these environment variables in Render:")
    logger.info("   - SKIP_MIGRATIONS=true")
    logger.info("   - PYTHONUNBUFFERED=1")
    logger.info("3. Consider using Dockerfile.optimized for custom Docker builds")
    logger.info("4. Monitor startup logs for any remaining issues")
    
    logger.info("\n💡 Additional recommendations:")
    logger.info("- Ensure DATABASE_URL uses connection pooling")
    logger.info("- Use Redis for session storage if available")
    logger.info("- Enable Render's health check grace period")

if __name__ == "__main__":
    main() 