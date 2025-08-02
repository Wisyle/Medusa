#!/usr/bin/env python3
"""
Debug script to test the decision engine and trading bot functionality.
This script allows testing various scenarios without real trading.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Import the bot modules
import config
import utils
from deriv_api import DerivAPI
from decision_engine import RefinedDecisionEngine, TradingMode
from trading_state import TradingState

# Initialize logger
logger = utils.setup_logging()


class MockAPI:
    """Mock API for testing without real connections."""
    
    def __init__(self):
        self.connected = False
        self.balance = 100.0  # Mock balance
    
    async def connect(self):
        self.connected = True
        return True
    
    async def disconnect(self):
        self.connected = False
    
    async def fetch_balance(self):
        return {"balance": self.balance, "currency": "XRP"}
    
    async def place_trade(self, symbol, amount, growth_rate, currency, take_profit):
        # Mock trade placement
        from deriv_api import Trade
        trade = Trade(
            contract_id=f"mock_{int(datetime.now().timestamp())}",
            symbol=symbol,
            stake=amount,
            growth_rate=growth_rate / 100,
            currency=currency,
            entry_price=1.0,
            take_profit=take_profit
        )
        return trade
    
    async def get_trade_outcome(self, contract_id):
        # Mock trade outcome - 60% win rate
        import random
        is_win = random.random() < 0.6
        profit = random.uniform(0.1, 0.3) if is_win else random.uniform(-0.5, -0.1)
        return {
            "profit": profit,
            "buy_price": 1.0,
            "sell_price": 1.0 + profit,
            "status": "won" if is_win else "lost"
        }


class MockBot:
    """Mock Telegram bot for testing."""
    
    def __init__(self):
        self.messages = []
    
    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(text)
        print(f"[MOCK BOT] {text}")
        # Return a mock message object
        return type('Message', (), {'message_id': len(self.messages)})()
    
    async def edit_message_text(self, chat_id, message_id, text, **kwargs):
        print(f"[MOCK BOT EDIT] {text}")
    
    async def delete_message(self, chat_id, message_id):
        print(f"[MOCK BOT DELETE] Message {message_id}")
    
    async def pin_chat_message(self, chat_id, message_id, **kwargs):
        print(f"[MOCK BOT PIN] Message {message_id}")


async def test_decision_engine_trigger():
    """Test decision engine triggering on max drawdown."""
    print("=== Testing Decision Engine Trigger ===")
    
    # Create mock instances
    api = MockAPI()
    bot = MockBot()
    
    # Create decision engine
    engine = RefinedDecisionEngine(api, telegram_bot=bot)
    
    # Test trigger
    await engine.trigger_drawdown_analysis(
        current_balance=99.0,
        max_drawdown=1.0,
        trading_pair="R_10",
        trade_history=[]
    )
    
    # Wait a bit for the analysis to run
    await asyncio.sleep(5)
    
    print(f"Engine state: {engine.analysis_data.state.value}")
    print(f"Engine mode: {engine.analysis_data.current_mode.value}")
    
    return engine


async def test_continuous_mode_conditions():
    """Test continuous mode conditions."""
    print("=== Testing Continuous Mode Conditions ===")
    
    api = MockAPI()
    bot = MockBot()
    engine = RefinedDecisionEngine(api, telegram_bot=bot)
    
    # Test consecutive wins
    result = await engine.check_continuous_mode_conditions(
        consecutive_wins=10,
        current_balance=105.0,
        session_start_balance=100.0
    )
    
    print(f"Should reduce risk: {result['should_reduce_risk']}")
    print(f"Message: {result['message']}")
    
    return result


async def test_trading_state_integration():
    """Test full trading state integration."""
    print("=== Testing Trading State Integration ===")
    
    api = MockAPI()
    bot = MockBot()
    state = TradingState(api, bot=bot)
    
    # Set up mock parameters
    state.params = {
        "index": "R_10",
        "stake": 1.0,
        "growth_rate": 1.0,
        "take_profit": 50.0,
        "currency": "XRP"
    }
    state.max_loss_amount = 1.0
    state.initial_balance = 100.0
    state.cumulative_loss = 1.5  # Trigger max drawdown
    
    # Test limit checking (should trigger decision engine)
    await state.check_trading_limits()
    
    print(f"Trading enabled: {state.trading_enabled}")
    print(f"Engine active: {state.decision_engine.is_active()}")
    
    return state


async def test_export_functionality():
    """Test enhanced export functionality."""
    print("=== Testing Export Functionality ===")
    
    # Create mock trade data
    trade_records = [
        {
            "timestamp": "2024-01-15 10:00:00",
            "contract_id": "123456",
            "symbol": "R_10",
            "stake": 1.0,
            "profit_loss": 0.5,
            "win": True,
            "balance": 100.5,
            "trading_mode": "continuous"
        },
        {
            "timestamp": "2024-01-15 10:05:00",
            "contract_id": "123457",
            "symbol": "R_25",
            "stake": 1.8,
            "profit_loss": -1.0,
            "win": False,
            "balance": 99.5,
            "trading_mode": "recovery"
        }
    ]
    
    summary_data = [
        ["Total Trades", 2],
        ["Net P/L", "-0.50 XRP"]
    ]
    
    # Test enhanced PDF export
    from utils import export_trade_history_pdf
    
    # Mock engine and mode data
    engine_data = {
        "state": "inactive",
        "recovery_failures": 1,
        "recovery_risk_reduction": 0.85,
        "volatility_data": {
            "symbol": "R_25",
            "volatility_percentage": 8.5,
            "volatility_score": 75,
            "data_points": 300,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    mode_data = {
        "current_mode": "recovery",
        "consecutive_wins": 0,
        "daily_profit_target": 4.5,
        "session_start_balance": 100.0
    }
    
    pdf_path = config.DATA_DIR / "debug_export_test.pdf"
    export_trade_history_pdf(trade_records, summary_data, pdf_path, engine_data, mode_data)
    
    print(f"Test PDF generated: {pdf_path}")
    return pdf_path.exists()


async def test_parameter_flow():
    """Test parameter flow from decision engine to trading state."""
    print("=== Testing Parameter Flow ===")
    
    api = MockAPI()
    bot = MockBot()
    state = TradingState(api, bot=bot)
    
    # Manually set some proposed parameters in the engine
    from decision_engine import ProposedParameters, TradingMode
    
    state.decision_engine.analysis_data.proposed_params = ProposedParameters(
        stake=2.0,
        take_profit=45.0,
                        growth_rate=1.0,  # Use valid API rate (1%)
        frequency="medium",
        account_percentage=2.0,
        volatility_reasoning="Test parameters",
        trading_mode=TradingMode.RECOVERY
    )
    state.decision_engine.analysis_data.params_confirmed = True
    
    # Test parameter retrieval
    params = state.decision_engine.get_proposed_parameters()
    print(f"Retrieved parameters: {params}")
    
    # Test parameter application
    if params:
        state.params.update({
            "index": params["index"],
            "stake": params["stake"],
            "growth_rate": params["growth_rate"],
            "take_profit": params["take_profit"]
        })
        print(f"Applied parameters: {state.params}")
    
    return params is not None


async def run_all_tests():
    """Run all debug tests."""
    print("🔍 Starting Decter 001 Debug Tests")
    print("=" * 50)
    
    results = {}
    
    try:
        # Test 1: Decision engine trigger
        engine = await test_decision_engine_trigger()
        results["engine_trigger"] = engine.is_active()
        
        await asyncio.sleep(2)
        
        # Test 2: Continuous mode conditions
        continuous_result = await test_continuous_mode_conditions()
        results["continuous_mode"] = continuous_result["should_reduce_risk"]
        
        await asyncio.sleep(1)
        
        # Test 3: Trading state integration
        state = await test_trading_state_integration()
        results["trading_integration"] = not state.trading_enabled  # Should be disabled due to max drawdown
        
        await asyncio.sleep(1)
        
        # Test 4: Parameter flow
        param_flow = await test_parameter_flow()
        results["parameter_flow"] = param_flow
        
        await asyncio.sleep(1)
        
        # Test 5: Export functionality
        export_success = await test_export_functionality()
        results["export_functionality"] = export_success
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["error"] = str(e)
    
    # Print results
    print("\n" + "=" * 50)
    print("🧪 Debug Test Results:")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} : {status}")
    
    overall_success = all(results.values()) and "error" not in results
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return results


async def interactive_debug():
    """Interactive debug mode."""
    print("🔧 Interactive Debug Mode")
    print("Available commands:")
    print("1. trigger - Test decision engine trigger")
    print("2. continuous - Test continuous mode")
    print("3. export - Test export functionality")
    print("4. all - Run all tests")
    print("5. quit - Exit")
    
    while True:
        try:
            cmd = input("\nEnter command: ").strip().lower()
            
            if cmd == "quit":
                break
            elif cmd == "1" or cmd == "trigger":
                await test_decision_engine_trigger()
            elif cmd == "2" or cmd == "continuous":
                await test_continuous_mode_conditions()
            elif cmd == "3" or cmd == "export":
                await test_export_functionality()
            elif cmd == "4" or cmd == "all":
                await run_all_tests()
            else:
                print("Unknown command")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Debug session ended.")


def main():
    """Main debug function."""
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        asyncio.run(interactive_debug())
    else:
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main() 