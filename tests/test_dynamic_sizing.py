import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

sys.modules['config'] = MagicMock()
import config

config.TRACKER_FILENAME = "dummy_tracker.json"
config.LOG_FILENAME = "test_bot.log"
config.DAFTAR_KOIN = []

from src.modules.executor import OrderExecutor


@pytest.fixture
def mock_exchange():
    exchange = MagicMock()
    exchange.price_to_precision = MagicMock(side_effect=lambda s, p: f"{float(p):.4f}")
    exchange.create_order = AsyncMock()
    exchange.fapiPrivateDeleteAllOpenOrders = AsyncMock()
    exchange.fetch_open_orders = AsyncMock(return_value=[])
    exchange.cancel_order = AsyncMock()
    return exchange


@pytest.fixture
def executor(mock_exchange):
    with patch('src.utils.helper.logger'):
        OrderExecutor.load_tracker = MagicMock()
        OrderExecutor.save_tracker = AsyncMock()
        exc = OrderExecutor(mock_exchange)
        exc.safety_orders_tracker = {}
        return exc


def test_calculate_dynamic_amount_usdt_disabled(executor, mock_exchange):
    """When USE_DYNAMIC_SIZE is False, should return None"""
    config.USE_DYNAMIC_SIZE = False
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    assert result is None


def test_calculate_dynamic_amount_usdt_zero_balance(executor, mock_exchange):
    """When balance is 0, should return None"""
    config.USE_DYNAMIC_SIZE = True
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': 0.0}})
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    assert result is None


def test_calculate_dynamic_amount_usdt_negative_balance(executor, mock_exchange):
    """When balance is negative, should return None"""
    config.USE_DYNAMIC_SIZE = True
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': -100.0}})
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    assert result is None


def test_calculate_dynamic_amount_usdt_above_minimum(executor, mock_exchange):
    """When calculated risk amount >= MIN_ORDER_USDT, return calculated amount"""
    config.USE_DYNAMIC_SIZE = True
    config.RISK_PERCENT_PER_TRADE = 3
    config.MIN_ORDER_USDT = 5
    
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': 1000.0}})
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    expected = 1000.0 * (3 / 100)
    assert result == expected
    assert result == 30.0


def test_calculate_dynamic_amount_usdt_below_minimum(executor, mock_exchange):
    """When calculated risk amount < MIN_ORDER_USDT, return MIN_ORDER_USDT"""
    config.USE_DYNAMIC_SIZE = True
    config.RISK_PERCENT_PER_TRADE = 3
    config.MIN_ORDER_USDT = 5
    
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': 100.0}})
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    assert result == config.MIN_ORDER_USDT
    assert result == 5


def test_calculate_dynamic_amount_usdt_boundary_case(executor, mock_exchange):
    """Test boundary where risk equals MIN_ORDER_USDT exactly"""
    config.USE_DYNAMIC_SIZE = True
    config.RISK_PERCENT_PER_TRADE = 5
    config.MIN_ORDER_USDT = 5
    
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': 100.0}})
    
    result = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 10))
    
    expected = 100.0 * (5 / 100)
    assert result == expected
    assert result == 5.0


def test_calculate_dynamic_amount_usdt_leverage_not_used(executor, mock_exchange):
    """Verify leverage parameter doesn't affect calculation"""
    config.USE_DYNAMIC_SIZE = True
    config.RISK_PERCENT_PER_TRADE = 2
    config.MIN_ORDER_USDT = 5
    
    mock_exchange.fetch_balance = AsyncMock(return_value={'USDT': {'free': 1000.0}})
    
    result_leverage_1 = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 1))
    result_leverage_100 = asyncio.run(executor.calculate_dynamic_amount_usdt('BTC/USDT', 100))
    
    assert result_leverage_1 == result_leverage_100
    assert result_leverage_1 == 20.0
