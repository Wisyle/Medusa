#!/usr/bin/env python3
"""
Script to check API key configurations for instances
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, BotInstance

def main():
    db = SessionLocal()
    try:
        instances = db.query(BotInstance).all()
        print("API Key Analysis:")
        print("=" * 60)
        
        api_keys = {}
        
        for instance in instances:
            # Mask API key for security (show first 8 and last 4 chars)
            api_key = instance.api_key or "None"
            if len(api_key) > 12:
                masked_key = api_key[:8] + "..." + api_key[-4:]
            else:
                masked_key = api_key
            
            print(f"Instance {instance.id}: {instance.name}")
            print(f"  Exchange: {instance.exchange}")
            print(f"  API Key: {masked_key}")
            print(f"  Has Secret: {'Yes' if instance.api_secret else 'No'}")
            print(f"  Has Passphrase: {'Yes' if instance.api_passphrase else 'No'}")
            print(f"  Is Active: {instance.is_active}")
            print(f"  Trading Pair: {instance.trading_pair}")
            print("-" * 40)
            
            # Track duplicate API keys
            if api_key != "None":
                if api_key in api_keys:
                    api_keys[api_key].append(instance.id)
                else:
                    api_keys[api_key] = [instance.id]
        
        print("\nDuplicate API Key Analysis:")
        print("=" * 40)
        duplicates_found = False
        for api_key, instance_ids in api_keys.items():
            if len(instance_ids) > 1:
                duplicates_found = True
                masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key
                print(f"⚠️ API Key {masked_key} used by instances: {instance_ids}")
        
        if not duplicates_found:
            print("✅ No duplicate API keys found")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
