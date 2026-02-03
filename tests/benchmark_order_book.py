
import asyncio
import time
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add root and src to path to simulate app environment
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(repo_root)
sys.path.append(os.path.join(repo_root, 'src'))

# Mock config
import src.config as config
config.DAFTAR_KOIN = [{'symbol': f'COIN{i}/USDT'} for i in range(20)]
config.ORDERBOOK_RANGE_PERCENT = 0.02

from src.modules.market_data import MarketDataManager

class MockExchange:
    def __init__(self):
        self.options = {}

    async def fetch_order_book(self, symbol, limit=20):
        await asyncio.sleep(0.2) # Simulate 200ms network latency
        # Return dummy orderbook structure
        return {
            'bids': [[100.0 - i*0.1, 1.0] for i in range(20)],
            'asks': [[100.0 + i*0.1, 1.0] for i in range(20)]
        }

    # Mock other methods called by __init__
    async def fetch_ohlcv(self, *args, **kwargs): return []
    async def fetch_funding_rate(self, *args, **kwargs): return {}
    async def fetch_open_interest(self, *args, **kwargs): return {}
    async def fapiDataGetTopLongShortAccountRatio(self, *args, **kwargs): return []

async def benchmark():
    print(f"--- Benchmarking Order Book Fetch ---")
    print(f"Simulating 200ms latency per API call.")
    print(f"Processing {len(config.DAFTAR_KOIN)} coins sequentially (as in main loop).")

    mock_exchange = MockExchange()
    mgr = MarketDataManager(mock_exchange)

    # 1. Baseline: Cache is empty -> Should trigger API calls
    print("\n[Baseline] Cache Empty (API Fallback)...")
    start_time = time.time()
    for coin in config.DAFTAR_KOIN:
        await mgr.get_order_book_depth(coin['symbol'])

    baseline_duration = time.time() - start_time
    print(f"Sequential REST API Calls: {baseline_duration:.4f} seconds")

    # 2. Optimized: Simulated WS Update -> Cache Filled
    print("\n[Optimized] Cache Filled (Simulating WS updates)...")
    # Pre-fill cache to simulate WS updates having happened
    for coin in config.DAFTAR_KOIN:
        mgr.ob_cache[coin['symbol']] = {
            'bids': [[100.0 - i*0.1, 1.0] for i in range(20)],
            'asks': [[100.0 + i*0.1, 1.0] for i in range(20)]
        }

    start_time = time.time()
    for coin in config.DAFTAR_KOIN:
        await mgr.get_order_book_depth(coin['symbol'])

    optimized_duration = time.time() - start_time
    print(f"Cached Lookup: {optimized_duration:.6f} seconds")

    speedup = baseline_duration / optimized_duration if optimized_duration > 0 else 0
    print(f"\nSpeedup Factor: {speedup:.2f}x")

if __name__ == "__main__":
    asyncio.run(benchmark())
