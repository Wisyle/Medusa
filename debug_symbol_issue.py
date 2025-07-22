#!/usr/bin/env python3
"""
Quick test script to debug symbol matching issues
"""

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format for comparison (remove slashes, convert to uppercase)"""
    return symbol.replace('/', '').replace('-', '').upper()

def test_current_issue():
    """Test the current XRP/USDT vs XRPUSDT issue"""
    
    configured_pair = "XRP/USDT"
    api_symbols = ["XRPUSDT", "XRP/USDT", "xrpusdt", "XRP-USDT"]
    
    print("🔍 Testing Current Issue: XRP/USDT Configuration")
    print("=" * 60)
    print(f"Configured trading pair: '{configured_pair}'")
    print(f"Normalized configured: '{normalize_symbol(configured_pair)}'")
    print()
    
    for api_symbol in api_symbols:
        normalized_api = normalize_symbol(api_symbol)
        normalized_configured = normalize_symbol(configured_pair)
        
        match = normalized_api == normalized_configured
        status = "✅ MATCH" if match else "❌ NO MATCH"
        
        print(f"API Symbol: '{api_symbol}'")
        print(f"  Normalized: '{normalized_api}'")
        print(f"  Result: {status}")
        print()

def test_validation_formats():
    """Test the new validation logic"""
    print("🔍 Testing Validation Logic")
    print("=" * 60)
    
    test_pairs = [
        ("XRP/USDT", "Should be valid"),
        ("XRPUSDT", "Should be valid"),
        ("BTC/USDT", "Should be valid"),
        ("BTCUSDT", "Should be valid"),
        ("ETH-USDT", "Should be valid"),
        ("INVALID", "Should be invalid"),
        ("XRP/", "Should be invalid"),
        ("/USDT", "Should be invalid"),
    ]
    
    for pair, expected in test_pairs:
        # Simulate validation logic
        is_valid = True
        error = None
        
        if pair and pair.strip():
            pair_clean = pair.strip().upper()
            # Check if it's in BASE/QUOTE format
            if '/' in pair_clean:
                parts = pair_clean.split('/')
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    is_valid = False
                    error = "Invalid BASE/QUOTE format"
            # Check if it's in BASEUSDT format (no slash)
            elif not pair_clean.endswith(('USDT', 'BUSD', 'BTC', 'ETH', 'USD', 'EUR')):
                is_valid = False
                error = "Invalid quote currency"
            elif len(pair_clean) < 4:
                is_valid = False
                error = "Too short"
        
        status = "✅ VALID" if is_valid else f"❌ INVALID ({error})"
        print(f"'{pair}': {status} - {expected}")

if __name__ == "__main__":
    test_current_issue()
    print()
    test_validation_formats()
