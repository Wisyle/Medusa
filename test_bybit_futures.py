#!/usr/bin/env python3
"""
Test the complete symbol matching fix for Bybit futures format
"""

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format for comparison (remove slashes, colons, convert to uppercase)"""
    # Remove common separators and suffixes used in different exchanges
    normalized = symbol.replace('/', '').replace('-', '').replace(':', '').upper()
    
    # Handle Bybit futures format: XRP/USDT:USDT -> XRPUSDT
    # Remove duplicate USDT if it appears due to :USDT suffix
    if normalized.endswith('USDTUSDT'):
        normalized = normalized[:-4]  # Remove the extra USDT
    elif normalized.endswith('BUSDBUSD'):
        normalized = normalized[:-4]  # Remove the extra BUSD
    elif normalized.endswith('BTCBTC'):
        normalized = normalized[:-3]  # Remove the extra BTC
    elif normalized.endswith('ETHETH'):
        normalized = normalized[:-3]  # Remove the extra ETH
        
    return normalized

def test_bybit_futures_matching():
    """Test Bybit futures symbol matching"""
    print("🎯 BYBIT FUTURES SYMBOL MATCHING TEST")
    print("=" * 60)
    
    # Test cases based on your actual logs
    test_cases = [
        # (configured, api_symbol, should_match)
        ("XRPUSDT", "XRP/USDT:USDT", True),
        ("XRP/USDT", "XRP/USDT:USDT", True),
        ("TONUSDT", "TON/USDT:USDT", True),
        ("TON/USDT", "TON/USDT:USDT", True),
        ("DOGEUSDT", "DOGE/USDT:USDT", True),
        ("DOGE/USDT", "DOGE/USDT:USDT", True),
        ("BTCUSDT", "BTC/USDT:USDT", True),
        ("ETHUSDT", "ETH/USDT:USDT", True),
        
        # Should NOT match
        ("XRPUSDT", "TON/USDT:USDT", False),
        ("BTCUSDT", "ETH/USDT:USDT", False),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for configured, api_symbol, should_match in test_cases:
        normalized_configured = normalize_symbol(configured)
        normalized_api = normalize_symbol(api_symbol)
        
        actual_match = normalized_configured == normalized_api
        test_passed = actual_match == should_match
        
        if test_passed:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
        
        expected_str = "MATCH" if should_match else "NO MATCH"
        actual_str = "MATCH" if actual_match else "NO MATCH"
        
        print(f"{status} '{configured}' vs '{api_symbol}'")
        print(f"    Normalized: '{normalized_configured}' vs '{normalized_api}'")
        print(f"    Expected: {expected_str}, Actual: {actual_str}")
        print()
    
    print(f"🏆 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Your symbol matching will work correctly!")
    else:
        print("❌ Some tests failed. Check the normalization logic.")

if __name__ == "__main__":
    test_bybit_futures_matching()
