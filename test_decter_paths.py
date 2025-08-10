#!/usr/bin/env python3
"""Test script to debug Decter paths on Render"""

import os
import sys
from pathlib import Path

print("=== Decter Path Debugging ===")
print(f"Current working directory: {os.getcwd()}")
print(f"Python executable: {sys.executable}")
print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
print(f"sys.path: {sys.path[:3]}...")  # Show first 3 paths

# Check if Decter directory exists
decter_path = Path("Decter")
print(f"\nDecter directory exists: {decter_path.exists()}")
print(f"Decter absolute path: {decter_path.absolute()}")

if decter_path.exists():
    print("\nContents of Decter directory:")
    for item in sorted(decter_path.iterdir())[:10]:  # Show first 10 items
        print(f"  - {item.name}")
    
    main_py = decter_path / "main.py"
    print(f"\nmain.py exists: {main_py.exists()}")
    print(f"main.py absolute path: {main_py.absolute()}")
    
    data_dir = decter_path / "data"
    print(f"\ndata directory exists: {data_dir.exists()}")
    if data_dir.exists():
        print("Contents of data directory:")
        for item in sorted(data_dir.iterdir()):
            print(f"  - {item.name}")
else:
    print("\n❌ Decter directory not found!")
    print("Current directory contents:")
    for item in sorted(Path(".").iterdir())[:20]:  # Show first 20 items
        print(f"  - {item.name}")
