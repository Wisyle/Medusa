#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test the strategy logic
class MockInstance:
    def __init__(self):
        self.trading_pair = "BCHUSDT"
        self.strategies = ["Combo"]

class MockPoller:
    def __init__(self):
        self.instance = MockInstance()
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for comparison (remove slashes, colons, convert to uppercase)"""
        # Remove common separators and suffixes used in different exchanges
        normalized = symbol.replace('/', '').replace('-', '').replace(':', '').upper()
        
        # Handle futures contracts with :USDT suffix (like XRP/USDT:USDT -> XRPUSDT)
        if ':USDT' in normalized:
            base_part = normalized.split(':')[0]  # Get part before ':'
            if base_part.endswith('USDT'):
                normalized = base_part  # Already ends with USDT
            else:
                normalized = base_part + 'USDT'  # Add USDT
        
        # Clean up duplicates
        if normalized.endswith('USDTUSDT'):
            normalized = normalized[:-4]  # Remove the extra USDT
        elif normalized.endswith('BUSDBUSD'):
            normalized = normalized[:-4]  # Remove the extra BUSD
        elif normalized.endswith('BTCBTC'):
            normalized = normalized[:-3]  # Remove the extra BTC
        elif normalized.endswith('ETHETH'):
            normalized = normalized[:-3]  # Remove the extra ETH
            
        return normalized

    def _detect_strategy_type(self, symbol: str, data: dict) -> str:
        """Get strategy type from instance configuration, not from symbol detection"""
        
        # Use configured strategies if available
        if self.instance.strategies:
            # If multiple strategies configured, return the first one
            # In practice, most instances will have one primary strategy
            return self.instance.strategies[0]
        
        # Fallback: try to infer from symbol name (legacy behavior)
        symbol_lower = symbol.lower()
        
        if 'dca' in symbol_lower:
            return 'DCA' if 'futures' not in symbol_lower else 'DCA Futures'
        elif 'grid' in symbol_lower:
            return 'Grid'
        elif 'combo' in symbol_lower:
            return 'Combo'
        elif 'loop' in symbol_lower:
            return 'Loop'
        elif 'btd' in symbol_lower:
            return 'BTD'
        elif 'ais' in symbol_lower:
            return 'AIS Assisted'
        
        return 'Unknown'

    def _should_process_symbol(self, symbol: str) -> bool:
        """Check if symbol should be processed based on configured trading pair and strategies"""
        print(f"[SYMBOL_CHECK] Checking symbol: {symbol}")
        print(f"[SYMBOL_CHECK] Configured trading_pair: {self.instance.trading_pair}")
        print(f"[SYMBOL_CHECK] Configured strategies: {self.instance.strategies}")
        
        if self.instance.trading_pair:
            normalized_symbol = self._normalize_symbol(symbol)
            normalized_trading_pair = self._normalize_symbol(self.instance.trading_pair)
            print(f"[SYMBOL_CHECK] Normalized symbol: {normalized_symbol}")
            print(f"[SYMBOL_CHECK] Normalized trading_pair: {normalized_trading_pair}")
            
            if normalized_symbol != normalized_trading_pair:
                print(f"[SYMBOL_CHECK] ❌ {symbol} filtered out - doesn't match trading pair {self.instance.trading_pair}")
                return False
            else:
                print(f"[SYMBOL_CHECK] ✅ {symbol} matches trading pair {self.instance.trading_pair}")
        
        # Strategy filtering: if strategies are configured, all matching symbols use those strategies
        if not self.instance.strategies:
            print(f"[SYMBOL_CHECK] ✅ {symbol} will be processed - no strategy filter")
            return True
        
        # If strategies are configured, the symbol passes (since trading pair already matched)
        # The configured strategies will be used for this symbol
        configured_strategies = ', '.join(self.instance.strategies)
        print(f"[SYMBOL_CHECK] ✅ {symbol} will be processed - using configured strategies: {configured_strategies}")
        return True

def main():
    poller = MockPoller()
    
    print("Testing BCH/USDT:USDT symbol with Combo strategy configured:")
    print("=" * 60)
    
    # Test 1: BCH symbol should pass
    result1 = poller._should_process_symbol("BCH/USDT:USDT")
    print(f"Result: {result1}")
    print()
    
    # Test 2: Strategy detection should return Combo
    strategy = poller._detect_strategy_type("BCH/USDT:USDT", {})
    print(f"Detected strategy: {strategy}")
    print()
    
    # Test 3: XRP symbol should be filtered out
    print("Testing XRP/USDT:USDT symbol (should be filtered out):")
    print("-" * 60)
    result2 = poller._should_process_symbol("XRP/USDT:USDT")
    print(f"Result: {result2}")

if __name__ == "__main__":
    main()
