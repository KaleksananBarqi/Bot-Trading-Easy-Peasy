
import asyncio
import sys
import os
import pytest
from collections import deque
from unittest.mock import MagicMock

# Add root and src to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.append(repo_root)
if os.path.join(repo_root, 'src') not in sys.path:
    sys.path.append(os.path.join(repo_root, 'src'))

import src.config as config
from src.modules.market_data import MarketDataManager

@pytest.mark.asyncio
async def test_verify_limits():
    # Mock Exchange
    exchange = MagicMock()
    mgr = MarketDataManager(exchange)

    # Check initial types
    print(f"Testing Symbol: {config.BTC_SYMBOL}")
    print(f"Timeframe: {config.TIMEFRAME_EXEC}, Limit: {config.LIMIT_EXEC}")

    store = mgr.market_store[config.BTC_SYMBOL][config.TIMEFRAME_EXEC]
    assert isinstance(store, deque), "Store is not a deque"
    assert store.maxlen == config.LIMIT_EXEC, f"Maxlen mismatch. Expected {config.LIMIT_EXEC}, got {store.maxlen}"

    # Push data beyond limit
    limit = config.LIMIT_EXEC
    symbol = config.BTC_SYMBOL
    interval = config.TIMEFRAME_EXEC

    # Fill up
    for i in range(limit + 10):
        payload = {
            's': 'BTCUSDT',
            'k': {
                'i': interval,
                't': i * 1000,
                'o': 100, 'h': 105, 'l': 95, 'c': 100, 'v': 1000
            }
        }
        await mgr._handle_kline(payload)

    # Check length
    current_len = len(mgr.market_store[symbol][interval])
    assert current_len == limit, f"Length {current_len} != Limit {limit}"

    # Check content (should contain latest)
    last_item = mgr.market_store[symbol][interval][-1]
    expected_ts = (limit + 9) * 1000
    assert last_item[0] == expected_ts, f"Last TS mismatch. Got {last_item[0]}, expected {expected_ts}"
