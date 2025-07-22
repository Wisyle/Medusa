#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test the safe formatting functions
def test_safe_formatting():
    print("Testing safe formatting functions...")
    
    # Safe formatting functions to handle None values
    def safe_float(value, decimals=2, default='0'):
        if value is None:
            return default
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return default
    
    def safe_side(value):
        if value is None:
            return 'N/A'
        return str(value).upper()
    
    def safe_string(value, default='N/A'):
        return str(value) if value is not None else default
    
    # Test cases
    test_cases = [
        ("safe_float(None)", safe_float(None)),
        ("safe_float(12.345, 2)", safe_float(12.345, 2)),
        ("safe_float('invalid', 2)", safe_float('invalid', 2)),
        ("safe_side(None)", safe_side(None)),
        ("safe_side('buy')", safe_side('buy')),
        ("safe_string(None)", safe_string(None)),
        ("safe_string('test')", safe_string('test')),
    ]
    
    for desc, result in test_cases:
        print(f"{desc} = '{result}'")
    
    # Test problematic payload
    print("\nTesting problematic payload:")
    payload = {
        'side': None,
        'quantity': None,
        'entry_price': None,
        'unrealized_pnl': None,
        'order_id': None
    }
    
    try:
        message_part = f"""
• **Side:** {safe_side(payload.get('side'))}
• **Amount:** `{safe_float(payload.get('quantity'), 6)}`
• **Price:** `${safe_float(payload.get('entry_price'), 4)}`
• **PnL:** `${safe_float(payload.get('unrealized_pnl'), 2)}`
• **Order ID:** `{safe_string(payload.get('order_id'))}`
"""
        print("✅ Message formatting successful:")
        print(message_part)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_safe_formatting()
