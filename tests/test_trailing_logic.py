import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# 1. Setup Path to Project Root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. Mock 'config' MODULE
sys.modules['config'] = MagicMock()
import config

# 3. Configure Config Mock
config.ENABLE_TRAILING_STOP = True
config.TRAILING_ACTIVATION_THRESHOLD = 0.80
config.TRAILING_CALLBACK_RATE = 0.01
config.TRAILING_MIN_PROFIT_LOCK = 0.005
config.TRACKER_FILENAME = "dummy_tracker.json"
config.LOG_FILENAME = "test_bot.log"
config.USE_DYNAMIC_SIZE = False
config.MIN_ORDER_USDT = 5
config.RISK_PERCENT_PER_TRADE = 1
config.DAFTAR_KOIN = []
config.TRAP_SAFETY_SL = 2.0
config.ATR_MULTIPLIER_TP1 = 3.0
config.DEFAULT_SL_PERCENT = 0.015
config.DEFAULT_TP_PERCENT = 0.025
config.LIMIT_ORDER_EXPIRY_SECONDS = 3600
config.DEFAULT_MARGIN_TYPE = 'isolated'
config.TRAILING_SL_UPDATE_COOLDOWN = 3
config.NATIVE_TRAILING_MIN_RATE = 0.1
config.NATIVE_TRAILING_MAX_RATE = 5.0
config.TRAILING_ACTIVATION_DELAY = 60
config.USE_NATIVE_TRAILING = True

# 4. Import Module Under Test
from src.modules.executor import OrderExecutor

@pytest.fixture
def executor():
    exchange = MagicMock()
    exchange.price_to_precision = MagicMock(side_effect=lambda s, p: f"{float(p):.4f}")
    exchange.create_order = AsyncMock()
    exchange.fapiPrivatePostOrder = AsyncMock()
    exchange.fapiPrivatePostAlgoOrder = AsyncMock()
    exchange.fapiPrivateDeleteAllOpenOrders = AsyncMock()
    exchange.fetch_open_orders = AsyncMock(return_value=[])
    exchange.cancel_order = AsyncMock()
    
    with patch('src.utils.helper.logger'):
        OrderExecutor.load_tracker = MagicMock()
        OrderExecutor.save_tracker = AsyncMock()
        
        exc = OrderExecutor(exchange)
        exc.safety_orders_tracker = {} 
        return exc

# NOTE: test_calculate_tp_progress_long / _short removed
# — fungsi calculate_tp_progress tidak pernah didefinisikan (dead reference).

def test_activate_trailing_mode_long(executor):
    symbol = "BTC/USDT"
    current_price = 58000
    
    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "entry_price": 50000,
        "tp_price": 60000,
        "side": "LONG"
    }
    
    asyncio.run(executor.activate_trailing_mode(symbol, current_price))
    
    tracker = executor.safety_orders_tracker[symbol]
    assert tracker['trailing_active'] is True
    assert tracker['trailing_high'] == 58000
    assert tracker['trailing_sl'] == 57420
    
    executor.exchange.create_order.assert_called()

def test_update_trailing_sl_long_logic(executor):
    symbol = "BTC/USDT"
    
    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "entry_price": 50000,
        "side": "LONG",
        "trailing_active": True,
        "trailing_high": 58000,
        "trailing_sl": 57420
    }
    
    # 1. Price Moves UP to 59000
    asyncio.run(executor.update_trailing_sl(symbol, 59000))
    tracker = executor.safety_orders_tracker[symbol]
    
    assert tracker['trailing_high'] == 59000
    assert tracker['trailing_sl'] == 58410
    
    # 2. Price Moves DOWN to 58500
    executor.exchange.create_order.reset_mock()
    
    asyncio.run(executor.update_trailing_sl(symbol, 58500))
    
    tracker = executor.safety_orders_tracker[symbol]
    assert tracker['trailing_high'] == 59000
    assert tracker['trailing_sl'] == 58410
    
    # Verify NO call to exchange (Because SL 58410 didn't change, 59000 high still same)
    executor.exchange.create_order.assert_not_called()

def test_throttling_logic(executor):
    symbol = "BTC/USDT"
    config.TRAILING_SL_UPDATE_COOLDOWN = 3
    
    # Setup Active Trailing
    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "entry_price": 50000,
        "side": "LONG",
        "trailing_active": True,
        "trailing_high": 58000,
        "trailing_sl": 57420
    }
    
    # Mock internal API call on SafetyManager to verify throttling
    executor.safety._amend_sl_order = AsyncMock()
    
    with patch('time.time') as mock_time:
        # Time 100: First Call -> Should Proceed
        # Price 60000 > 58000. New SL = 59400 > 57420.
        mock_time.return_value = 100
        asyncio.run(executor.check_trailing_on_price(symbol, 60000))

        executor.safety._amend_sl_order.assert_called()
        assert executor._trailing_last_update[symbol] == 100
        assert executor.safety_orders_tracker[symbol]['trailing_high'] == 60000
        
        executor.safety._amend_sl_order.reset_mock()
        
        # Time 101: Second Call (diff 1s < 3s)
        # Price 61000. New High 61000. New SL 60390.
        # Should be Throttled (API Call Skipped)
        # But INTERNAL State (High) should be UPDATED!
        mock_time.return_value = 101
        asyncio.run(executor.check_trailing_on_price(symbol, 61000))
        
        executor.safety._amend_sl_order.assert_not_called() # Throttled!
        assert executor.safety_orders_tracker[symbol]['trailing_high'] == 61000 # Updated!
        assert executor._trailing_last_update[symbol] == 100 # Last update unchanged

        # Time 104: Third Call (diff 4s > 3s)
        # Price 60500. High stays 61000. SL Candidate 60390.
        # Current SL in tracker is still 59400 (from T=100).
        # Should Update!
        mock_time.return_value = 104
        asyncio.run(executor.check_trailing_on_price(symbol, 60500))

        executor.safety._amend_sl_order.assert_called()
        assert executor._trailing_last_update[symbol] == 104
        assert executor.safety_orders_tracker[symbol]['trailing_sl'] == 61000 * (1 - config.TRAILING_CALLBACK_RATE)


# =====================================================
# --- NATIVE TRAILING STOP WITH ACTIVATION PRICE ---
# =====================================================

def test_native_trailing_activation_price_long(executor):
    """Verifikasi activationPrice dikirim ke API untuk posisi LONG (80% menuju TP)"""
    symbol = "BTC/USDT"
    entry = 67777.78
    tp = 68294.76
    qty = 0.029
    callback_rate = config.TRAILING_CALLBACK_RATE  # 0.01

    # Setup tracker
    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "entry_price": entry,
        "tp_price": tp,
        "side": "LONG",
        "tp_order_id": "tp_123"
    }

    # Mock exchange fapiPrivatePostOrder explicitly
    executor.exchange.fapiPrivatePostOrder = AsyncMock(return_value={'orderId': 'trailing_001'})

    # Hitung expected activation price: entry + (distance * 0.80)
    distance = abs(tp - entry)
    expected_activation = entry + (distance * 0.80)  # 68191.364

    asyncio.run(executor.install_native_trailing_stop(
        symbol, 'LONG', qty, callback_rate, activation_price=expected_activation
    ))

    # Verifikasi API dipanggil dengan activationPrice & callbackRate sesuai config
    call_args = executor.exchange.fapiPrivatePostOrder.call_args
    params = call_args.kwargs.get('params') or call_args[0][0]
    assert 'activationPrice' in params
    expected_rate = round(config.TRAILING_CALLBACK_RATE * 100, 1)
    assert params['callbackRate'] == str(expected_rate), f"Expected {expected_rate}, got {params['callbackRate']}"


def test_native_trailing_activation_price_short(executor):
    """Verifikasi activationPrice dikirim ke API untuk posisi SHORT"""
    symbol = "ETH/USDT"
    entry = 3500.00
    tp = 3400.00
    qty = 2.5
    callback_rate = config.TRAILING_CALLBACK_RATE

    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "entry_price": entry,
        "tp_price": tp,
        "side": "SHORT"
    }

    executor.exchange.fapiPrivatePostOrder = AsyncMock(return_value={'orderId': 'trailing_002'})

    # Hitung expected: entry - (distance * 0.80)
    distance = abs(entry - tp)
    expected_activation = entry - (distance * 0.80)  # 3420.00

    asyncio.run(executor.install_native_trailing_stop(
        symbol, 'SHORT', qty, callback_rate, activation_price=expected_activation
    ))

    # Verifikasi side_api = 'buy' untuk SHORT & callbackRate sesuai config
    call_args = executor.exchange.fapiPrivatePostOrder.call_args
    params = call_args.kwargs.get('params') or call_args[0][0]
    assert params.get('side') == 'BUY'
    assert 'activationPrice' in params
    expected_rate = round(config.TRAILING_CALLBACK_RATE * 100, 1)
    assert params['callbackRate'] == str(expected_rate), f"Expected {expected_rate}, got {params['callbackRate']}"


def test_native_trailing_without_activation_price(executor):
    """Backward compatibility: tanpa activation_price, activationPrice TIDAK dikirim"""
    symbol = "BTC/USDT"
    qty = 0.029
    callback_rate = config.TRAILING_CALLBACK_RATE

    executor.safety_orders_tracker[symbol] = {
        "status": "SECURED",
        "side": "LONG"
    }

    executor.exchange.fapiPrivatePostOrder = AsyncMock(return_value={'orderId': 'trailing_003'})

    asyncio.run(executor.install_native_trailing_stop(
        symbol, 'LONG', qty, callback_rate
    ))

    call_args = executor.exchange.fapiPrivatePostOrder.call_args
    params = call_args.kwargs.get('params') or call_args[0][0]
    assert 'activationPrice' not in params
    expected_rate = round(config.TRAILING_CALLBACK_RATE * 100, 1)
    assert params['callbackRate'] == str(expected_rate), f"Expected {expected_rate}, got {params['callbackRate']}"
