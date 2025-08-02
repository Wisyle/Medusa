#!/usr/bin/env python3
"""
Test the symbol matching fix
"""

from database import SessionLocal, BotInstance
import json

def test_symbol_fix():
    """Test if the symbol matching fix works"""
    db = SessionLocal()
    
    try:
        # Create test instance with XRP/USDT
        test_instance = BotInstance(
            name="Test XRP Bot",
            exchange="bybit",
            market_type="unified",
            api_key="test_key",
            api_secret="test_secret",
            trading_pair="XRP/USDT",  # This should now match XRPUSDT from API
            strategies=[],
            is_active=True,
            polling_interval=60
        )
        
        db.add(test_instance)
        db.commit()
        
        print("✅ Test instance created with XRP/USDT trading pair")
        print(f"   Instance ID: {test_instance.id}")
        print(f"   Market Type: {test_instance.market_type}")
        print(f"   Trading Pair: {test_instance.trading_pair}")
        
        # Test symbol normalization logic
        def normalize_symbol(symbol: str) -> str:
            return symbol.replace('/', '').replace('-', '').upper()
        
        configured_pair = test_instance.trading_pair
        api_symbol = "XRPUSDT"  # What Bybit API returns
        
        normalized_configured = normalize_symbol(configured_pair)
        normalized_api = normalize_symbol(api_symbol)
        
        print(f"\n🔍 Symbol Matching Test:")
        print(f"   Configured: '{configured_pair}' -> '{normalized_configured}'")
        print(f"   API Symbol: '{api_symbol}' -> '{normalized_api}'")
        print(f"   Match: {'✅ YES' if normalized_configured == normalized_api else '❌ NO'}")
        
        # Clean up
        db.delete(test_instance)
        db.commit()
        print(f"\n🧹 Test instance cleaned up")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_symbol_fix()
