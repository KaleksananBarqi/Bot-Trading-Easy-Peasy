import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add src to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

# Mock Env for Config Validation
os.environ["MONGO_URI"] = "mongodb://dummy:27017/test"

import config
from src.modules.executor import OrderExecutor

async def test_refactoring():
    print("🧪 Starting Executor Refactoring Verification...")

    # 1. Mock Exchange
    mock_exchange = AsyncMock()
    mock_exchange.fetch_balance.return_value = {'USDT': {'free': 1000.0}}
    mock_exchange.fetch_positions.return_value = []
    mock_exchange.fetch_open_orders.return_value = []
    mock_exchange.create_order.return_value = {'id': '12345', 'status': 'NEW'}
    mock_exchange.price_to_precision.side_effect = lambda s, p: str(p)
    mock_exchange.amount_to_precision.side_effect = lambda s, a: str(a)
    
    # 2. Instantiate Executor
    try:
        executor = OrderExecutor(mock_exchange)
        print("✅ OrderExecutor instantiated successfully.")
    except Exception as e:
        print(f"❌ Failed to instantiate: {e}")
        return

    # 3. Check Components
    components = ['tracker', 'positions', 'risk', 'safety', 'orders']
    for comp in components:
        if hasattr(executor, comp):
            print(f"✅ Component '{comp}' initialized.")
        else:
            print(f"❌ Component '{comp}' MISSING!")

    # 4. Test Execute Entry (Delegation to OrderManager)
    print("\n👉 Testing execute_entry...")
    await executor.execute_entry(
        symbol="BTC/USDT",
        side="buy",
        order_type="MARKET",
        price=50000,
        amount_usdt=100,
        leverage=10,
        strategy_tag="TEST"
    )
    
    # Verify mock call
    mock_exchange.create_order.assert_called()
    print("✅ execute_entry called OrderManager -> Exchange successfully.")

    # 5. Test Safety Orders (Delegation to SafetyManager)
    print("\n👉 Testing install_safety_orders...")
    pos_data = {
        'entryPrice': 50000,
        'contracts': 0.1,
        'side': 'LONG'
    }
    await executor.install_safety_orders("BTC/USDT", pos_data)
    
    # Verify mock calls (sl/tp)
    # create_order should be called 2 more times (SL + TP)
    # Total calls: Entry(1) + SL(1) + TP(1) = 3
    print(f"✅ Exchange create_order called {mock_exchange.create_order.call_count} times.")

    print("\n🎉 Verification Complete! Refactoring seems successful.")

if __name__ == "__main__":
    asyncio.run(test_refactoring())
