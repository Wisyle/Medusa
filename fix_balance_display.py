#!/usr/bin/env python3
"""
Fix balance display issue by removing the active coin filtering
"""

import sys

print("🔧 FIXING BALANCE DISPLAY LOGIC...")
print("=" * 60)

# Read the current polling.py
with open('polling.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the format_balance_section
old_logic = '''        def format_balance_section(balance_data):
            """Format balance data for display - only active trading coin"""
            if not balance_data:
                return ""
            
            # Extract active coin from trading pair
            active_coin = self._get_active_coin_from_trading_pair()
            if not active_coin:
                return ""
            
            balance_lines = []
            balance_lines.append("\\n💰 **Account Balance:**")
            balance_lines.append("```")
            
            # Show only active coin and USDT (for context)
            priority_currencies = [active_coin, 'USDT']
            
            for currency in priority_currencies:
                if currency in balance_data:
                    amounts = balance_data[currency]
                    if isinstance(amounts, dict) and amounts.get('total', 0) > 0:
                        total = amounts.get('total', 0)
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
            
            # Show any other currencies with significant balances (>$0.01 equivalent)
            for currency, amounts in balance_data.items():
                if currency not in priority_currencies and isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    if total > 0.01:  # Show balances > 1 cent (was > 1)
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
            
            balance_lines.append("```")
            return "\\n".join(balance_lines) if len(balance_lines) > 3 else ""'''

new_logic = '''        def format_balance_section(balance_data):
            """Format balance data for display"""
            if not balance_data:
                return ""
            
            balance_lines = []
            balance_lines.append("\\n💰 **Account Balance:**")
            balance_lines.append("```")
            
            # Extract active coin from trading pair (if available)
            active_coin = self._get_active_coin_from_trading_pair()
            
            # Show active coin and USDT first (if they exist)
            priority_currencies = []
            if active_coin:
                priority_currencies.append(active_coin)
            priority_currencies.append('USDT')
            
            # Show priority currencies first
            shown_currencies = set()
            for currency in priority_currencies:
                if currency in balance_data:
                    amounts = balance_data[currency]
                    if isinstance(amounts, dict) and amounts.get('total', 0) > 0:
                        total = amounts.get('total', 0)
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
                        shown_currencies.add(currency)
            
            # Show any other currencies with balances > $0.01
            for currency, amounts in balance_data.items():
                if currency not in shown_currencies and isinstance(amounts, dict):
                    total = amounts.get('total', 0)
                    if total > 0.01:  # Show balances > 1 cent
                        free = amounts.get('free', 0)
                        used = amounts.get('used', 0)
                        balance_lines.append(f"• {currency}: {safe_float(total, 6)} (Free: {safe_float(free, 6)}, Used: {safe_float(used, 6)})")
            
            balance_lines.append("```")
            # Return balance even if we don't have active coin
            return "\\n".join(balance_lines) if len(balance_lines) > 2 else ""'''

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    with open('polling.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Fixed balance display logic!")
    print("   - Removed requirement for active coin to show balance")
    print("   - Balance will now show even if trading pair extraction fails")
else:
    print("❌ Could not find the old logic to replace")
    print("   The file may have been modified already") 