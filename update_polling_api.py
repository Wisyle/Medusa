#!/usr/bin/env python3
"""
Update API credential references in polling.py
"""

import re

def update_polling_api_references():
    """Update API credential references in polling.py"""
    
    with open('polling.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace API key references
    content = content.replace("self.instance.api_key", "self.api_credentials['api_key']")
    content = content.replace("self.instance.api_secret", "self.api_credentials['api_secret']")
    content = content.replace("self.instance.api_passphrase", "self.api_credentials.get('api_passphrase')")
    
    with open('polling.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Updated API credential references in polling.py")

if __name__ == "__main__":
    update_polling_api_references()
