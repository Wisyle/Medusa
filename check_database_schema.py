#!/usr/bin/env python3
"""
Script to check database schema and verify all required columns exist
This can be run on Render to verify the migration worked
"""

from database import SessionLocal, BotInstance
from sqlalchemy import inspect, text
import json

def check_database_schema():
    """Check database schema and report status"""
    try:
        db = SessionLocal()
        
        # Get table columns using SQLAlchemy inspector
        engine = db.get_bind()
        inspector = inspect(engine)
        
        # Check bot_instances table
        if 'bot_instances' in inspector.get_table_names():
            columns = inspector.get_columns('bot_instances')
            column_names = [col['name'] for col in columns]
            
            print("🗄️ bot_instances table schema:")
            print("=" * 50)
            
            required_columns = [
                'id', 'name', 'exchange', 'market_type', 'api_key', 'api_secret',
                'api_passphrase', 'strategies', 'polling_interval', 'webhook_url',
                'telegram_bot_token', 'telegram_chat_id', 'telegram_topic_id',
                'trading_pair', 'is_active', 'last_poll', 'last_error',
                'created_at', 'updated_at'
            ]
            
            for col_name in required_columns:
                status = "✅" if col_name in column_names else "❌ MISSING"
                print(f"  {col_name}: {status}")
            
            print(f"\nTotal columns: {len(column_names)}")
            print(f"All columns: {column_names}")
            
            # Test if we can query the table
            try:
                instances = db.query(BotInstance).all()
                print(f"\n📊 Database status:")
                print(f"  Total instances: {len(instances)}")
                
                for instance in instances:
                    market_type = getattr(instance, 'market_type', 'NOT SET')
                    print(f"  Instance '{instance.name}': market_type = {market_type}")
                    
            except Exception as e:
                print(f"❌ Error querying instances: {e}")
        
        else:
            print("❌ bot_instances table not found!")
        
        # Check users table
        if 'users' in inspector.get_table_names():
            print(f"\n✅ users table exists")
        else:
            print(f"\n❌ users table missing")
            
        db.close()
        
    except Exception as e:
        print(f"❌ Error checking database schema: {e}")

def test_symbol_normalization():
    """Test the symbol normalization logic"""
    print(f"\n🔍 Testing Symbol Normalization:")
    print("=" * 50)
    
    def normalize_symbol(symbol: str) -> str:
        return symbol.replace('/', '').replace('-', '').upper()
    
    test_cases = [
        ("XRP/USDT", "XRPUSDT"),
        ("BTC/USDT", "BTCUSDT"),
        ("ETH-USDT", "ETHUSDT"),
        ("btc/usdt", "BTCUSDT"),
    ]
    
    for configured, api_symbol in test_cases:
        normalized_configured = normalize_symbol(configured)
        normalized_api = normalize_symbol(api_symbol)
        match = normalized_configured == normalized_api
        status = "✅ MATCH" if match else "❌ NO MATCH"
        print(f"  '{configured}' vs '{api_symbol}': {status}")

if __name__ == "__main__":
    print("🔍 Database Schema Verification")
    print("=" * 50)
    check_database_schema()
    test_symbol_normalization()
    print("\n✅ Schema check completed!")
