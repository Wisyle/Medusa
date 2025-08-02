#!/usr/bin/env python3
"""
Add debug logging to the polling process to see why symbols are filtered
"""

def add_debug_logging():
    """Add debug logging to _should_process_symbol function"""
    
    # Read the current polling.py file
    with open('polling.py', 'r') as f:
        content = f.read()
    
    # Find the _should_process_symbol function and add debug logging
    old_function = '''    def _should_process_symbol(self, symbol: str) -> bool:
        """Check if symbol should be processed based on configured trading pair and strategies"""
        if self.instance.trading_pair and symbol != self.instance.trading_pair:
            return False
            
        if not self.instance.strategies:
            return True
        
        strategy_type = self._detect_strategy_type(symbol, {})
        return strategy_type in self.instance.strategies'''
    
    new_function = '''    def _should_process_symbol(self, symbol: str) -> bool:
        """Check if symbol should be processed based on configured trading pair and strategies"""
        logger.debug(f"[DEBUG] Checking symbol: {symbol}")
        logger.debug(f"[DEBUG] Configured trading_pair: {self.instance.trading_pair}")
        logger.debug(f"[DEBUG] Configured strategies: {self.instance.strategies}")
        
        if self.instance.trading_pair and symbol != self.instance.trading_pair:
            logger.debug(f"[DEBUG] ❌ {symbol} filtered out - doesn't match trading pair {self.instance.trading_pair}")
            return False
            
        if not self.instance.strategies:
            logger.debug(f"[DEBUG] ✅ {symbol} will be processed - no strategy filter")
            return True
        
        strategy_type = self._detect_strategy_type(symbol, {})
        result = strategy_type in self.instance.strategies
        if result:
            logger.debug(f"[DEBUG] ✅ {symbol} will be processed - strategy {strategy_type} matches")
        else:
            logger.debug(f"[DEBUG] ❌ {symbol} filtered out - strategy {strategy_type} not in {self.instance.strategies}")
        return result'''
    
    if old_function in content:
        content = content.replace(old_function, new_function)
        
        with open('polling.py', 'w') as f:
            f.write(content)
        
        print("✅ Debug logging added to polling.py")
        print("Now run your bot and check the logs for [DEBUG] messages")
    else:
        print("❌ Could not find the function to modify")

if __name__ == "__main__":
    add_debug_logging()
