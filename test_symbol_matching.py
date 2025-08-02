#!/usr/bin/env python3
"""
Test script to check symbol format matching
"""

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format for comparison"""
    return symbol.replace('/', '').replace('-', '').upper()

def test_symbol_matching():
    """Test various symbol format combinations"""
    
    test_cases = [
        ("XRP/USDT", "XRPUSDT"),  # Your case
        ("XRP/USDT", "XRP-USDT"),
        ("BTC/USDT", "BTCUSDT"),
        ("ETH/USDT", "ETHUSDT"),
        ("BTC-USDT", "BTC/USDT"),
        ("btc/usdt", "BTCUSDT"),  # Case sensitivity
    ]
    
    print("🔍 Testing Symbol Format Matching")
    print("=" * 50)
    
    for configured, api_symbol in test_cases:
        normalized_configured = normalize_symbol(configured)
        normalized_api = normalize_symbol(api_symbol)
        
        match = normalized_configured == normalized_api
        status = "✅ MATCH" if match else "❌ NO MATCH"
        
        print(f"Configured: '{configured}' -> '{normalized_configured}'")
        print(f"API Symbol: '{api_symbol}' -> '{normalized_api}'")
        print(f"Result: {status}")
        print("-" * 30)

if __name__ == "__main__":
    test_symbol_matching()
