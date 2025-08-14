#!/usr/bin/env python3
"""
Force redeploy script for Decter Engine
This helps trigger a fresh deployment on Render
"""

import os
import sys
from datetime import datetime

def main():
    """Force redeploy by updating a marker file"""
    
    print("🔄 Forcing Decter Engine redeploy...")
    
    # Create deployment marker
    marker_content = f"""
# Decter Engine Deployment Marker
# Generated: {datetime.now().isoformat()}
# Purpose: Force fresh deployment on Render

DEPLOYMENT_ID = "{datetime.now().strftime('%Y%m%d_%H%M%S')}"
FORCE_REDEPLOY = True

# This file is updated to trigger fresh deployments
# when there are caching issues or need to restart services
"""
    
    marker_file = "Decter/deployment_marker.py"
    
    with open(marker_file, 'w') as f:
        f.write(marker_content)
    
    print(f"✅ Created deployment marker: {marker_file}")
    print("📝 This will force Render to redeploy the Decter Engine service")
    print("🚀 Push these changes to trigger redeploy")
    
    # Also update render.yaml comment to force cache bust
    render_file = "render.yaml"
    
    with open(render_file, 'r') as f:
        content = f.read()
    
    # Add timestamp comment to force cache bust
    timestamp_comment = f"# Updated: {datetime.now().isoformat()}\n"
    
    if "# Updated:" in content:
        # Replace existing timestamp
        lines = content.split('\n')
        lines = [line for line in lines if not line.startswith("# Updated:")]
        content = '\n'.join(lines)
    
    content = timestamp_comment + content
    
    with open(render_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated render.yaml with timestamp")
    print("\n🎯 Next steps:")
    print("1. git add .")
    print("2. git commit -m 'Force Decter Engine redeploy'")
    print("3. git push origin master")
    print("4. Monitor Render deployment logs")

if __name__ == "__main__":
    main()