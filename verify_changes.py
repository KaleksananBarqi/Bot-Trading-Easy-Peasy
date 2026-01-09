import sys
import os
import time
import asyncio
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.utils.helper import parse_timeframe_to_seconds
from src.modules.executor import OrderExecutor

def test_helper():
    print("--- Testing Helper ---")
    inputs = {
        '1m': 60,
        '5m': 300,
        '1h': 3600,
        '1s': 1,
        'invalid': 60, # Default
        None: 60       # Default
    }
    
    for k, v in inputs.items():
        res = parse_timeframe_to_seconds(k)
        status = "✅" if res == v else f"❌ (Expected {v})"
        print(f"Input '{k}': Result {res} {status}")

def test_executor():
    print("\n--- Testing Executor Cooldown ---")
    mock_exchange = MagicMock()
    executor = OrderExecutor(mock_exchange)
    
    symbol = "BTC/USDT"
    
    # 1. Check initial state
    print(f"Initial Cooldown: {executor.is_under_cooldown(symbol)} (Expected False)")
    
    # 2. Set Cooldown 2 seconds
    print("Setting 2s Cooldown...")
    executor.set_cooldown(symbol, 2)
    
    # 3. Check immediately
    print(f"Immediate Check: {executor.is_under_cooldown(symbol)} (Expected True)")
    
    # 4. Wait 2.1s
    print("Sleeping 2.1s...")
    time.sleep(2.1)
    
    # 5. Check again
    print(f"After Wait Check: {executor.is_under_cooldown(symbol)} (Expected False)")

if __name__ == "__main__":
    test_helper()
    test_executor()
