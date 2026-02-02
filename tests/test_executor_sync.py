import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.modules.executor import OrderExecutor

@pytest.mark.asyncio
async def test_sync_pending_orders_parallel():
    # 1. Setup Mock Exchange
    mock_exchange = MagicMock()
    mock_exchange.fetch_open_orders = AsyncMock(return_value=[]) # Return empty orders (simulating filled/cancelled)

    # 2. Setup Executor
    executor = OrderExecutor(mock_exchange)

    # Mock save_tracker to avoid file I/O and verify calls
    executor.save_tracker = AsyncMock()

    # Mock position cache to simulate filled orders
    # Let's verify Case A: Filled
    executor.position_cache = {
        'BTC': {'contracts': 1.0}
    }

    # Setup Tracker with multiple orders
    executor.safety_orders_tracker = {
        'BTC/USDT': {
            'status': 'WAITING_ENTRY',
            'entry_id': '123'
        },
        'ETH/USDT': {
            'status': 'WAITING_ENTRY',
            'entry_id': '456'
        }
    }

    # 3. Run Sync
    await executor.sync_pending_orders()

    # 4. Verify Results

    # BTC/USDT: entry_id '123' not in [], so missing.
    # BTC in position_cache -> Status should be PENDING.
    assert executor.safety_orders_tracker['BTC/USDT']['status'] == 'PENDING'

    # ETH/USDT: entry_id '456' not in [], so missing.
    # ETH not in position_cache -> Should be deleted.
    assert 'ETH/USDT' not in executor.safety_orders_tracker

    # Verify save_tracker called exactly once (optimization check)
    assert executor.save_tracker.call_count == 1

    # Verify fetch_open_orders called for both
    assert mock_exchange.fetch_open_orders.call_count == 2
