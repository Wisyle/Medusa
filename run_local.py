#!/usr/bin/env python3
"""
Local development runner for TGL MEDUSA
Sets up proper Python path and runs the application
"""

import os
import sys
import subprocess

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))

# Run the application
subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])
