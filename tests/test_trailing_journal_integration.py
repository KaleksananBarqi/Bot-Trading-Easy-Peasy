"""
Test integrasi fitur trailing stop dengan jurnal trade.

Test case:
1. Exit type detection dari order type
2. Trailing metadata dikirim ke journal
3. Journal menyimpan field trailing ke MongoDB
4. Backward compatibility: trade tanpa data trailing
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime

# 1. Setup Path to Project Root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. Mock 'config' MODULE
sys.modules['config'] = MagicMock()
import config

# 3. Configure Config Mock
config.COOLDOWN_IF_PROFIT = 300
config.COOLDOWN_IF_LOSS = 600
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
config.USE_NATIVE_TRAILING = False
config.ENABLE_TRAILING_STOP = True
config.TRAILING_ACTIVATION_THRESHOLD = 0.80
config.MONGO_URI = "mongodb://localhost:27017"
config.MONGO_DB_NAME = "test_db"
config.MONGO_COLLECTION_NAME = "test_trades"
config.COIN_LEVERAGE = {}

# 4. Import Modules Under Test
from src.modules.executor_impl.order_callbacks import OrderUpdateHandler


# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.safety_orders_tracker = {}
    executor.set_cooldown = MagicMock()
    executor.remove_from_tracker = AsyncMock()
    executor.sync_positions = AsyncMock()
    executor.save_tracker = AsyncMock()
    return executor


@pytest.fixture
def mock_journal():
    journal = MagicMock()
    journal.log_trade = MagicMock(return_value=True)
    return journal


@pytest.fixture
def handler(mock_executor, mock_journal):
    return OrderUpdateHandler(mock_executor, mock_journal)


# =====================================================
# TEST: EXIT TYPE DETECTION
# =====================================================

class TestExitTypeDetection:
    """Verifikasi mapping order type ke exit type."""

    def _make_ws_payload(self, symbol, order_type, realized_profit, side='SELL', price=60000, qty=0.01):
        raw_sym = symbol.replace('/', '')
        return {
            'o': {
                's': raw_sym,
                'X': 'FILLED',
                'S': side,
                'o': order_type,
                'ap': str(price),
                'q': str(qty),
                'rp': str(realized_profit),
                'n': '0.05',
                'i': '12345',
            }
        }

    @pytest.mark.parametrize("order_type,expected_exit_type", [
        ('STOP_MARKET', 'STOP_LOSS'),
        ('TAKE_PROFIT_MARKET', 'TAKE_PROFIT'),
        ('TRAILING_STOP_MARKET', 'TRAILING_STOP'),
        ('MARKET', 'MANUAL'),
        ('LIMIT', 'LIMIT'),
    ])
    def test_exit_type_mapping(self, handler, mock_journal, mock_executor, order_type, expected_exit_type):
        """Verifikasi setiap order type di-mapping ke exit type yang benar."""
        symbol = 'BTC/USDT'
        mock_executor.safety_orders_tracker[symbol] = {
            'side': 'LONG',
            'entry_price': 50000,
            'strategy': 'TEST',
            'ai_prompt': '-',
            'ai_reason': '-',
            'created_at': 0,
            'filled_at': 0,
            'technical_data': {},
            'config_snapshot': {},
            'order_type': 'MARKET',
            'trailing_active': False,
        }

        payload = self._make_ws_payload(symbol, order_type, 100.0)

        with patch('src.modules.executor_impl.order_callbacks.kirim_tele', new_callable=AsyncMock):
            with patch('src.modules.executor_impl.order_callbacks.get_coin_leverage', return_value=10):
                asyncio.run(handler.order_update_cb(payload))

        # Verify journal.log_trade was called
        mock_journal.log_trade.assert_called_once()
        trade_data = mock_journal.log_trade.call_args[0][0]

        assert trade_data['exit_type'] == expected_exit_type, \
            f"Expected exit_type '{expected_exit_type}' for order_type '{order_type}', got '{trade_data['exit_type']}'"


# =====================================================
# TEST: TRAILING METADATA IN JOURNAL
# =====================================================

class TestTrailingMetadataInJournal:
    """Verifikasi data trailing dikirim ke journal saat posisi ditutup."""

    def test_position_close_includes_trailing_data(self, handler, mock_journal, mock_executor):
        """Saat posisi ditutup dan trailing aktif, semua field trailing harus ada di trade_data."""
        symbol = 'ETH/USDT'
        mock_executor.safety_orders_tracker[symbol] = {
            'side': 'LONG',
            'entry_price': 3000,
            'strategy': 'AI_SCALP',
            'ai_prompt': 'test prompt',
            'ai_reason': 'test reason',
            'created_at': 1700000000,
            'filled_at': 1700000060,
            'technical_data': {'rsi': 55},
            'config_snapshot': {'leverage': 10},
            'order_type': 'LIMIT',
            # Trailing data
            'trailing_active': True,
            'trailing_sl': 3150.50,
            'trailing_high': 3300.00,
            'trailing_low': 0,
            'activation_price': 3250.00,
            'sl_price_initial': 2900.00,
        }

        payload = {
            'o': {
                's': 'ETHUSDT',
                'X': 'FILLED',
                'S': 'SELL',
                'o': 'TRAILING_STOP_MARKET',
                'ap': '3200',
                'q': '1.5',
                'rp': '300',
                'n': '0.12',
                'i': '99999',
            }
        }

        with patch('src.modules.executor_impl.order_callbacks.kirim_tele', new_callable=AsyncMock):
            with patch('src.modules.executor_impl.order_callbacks.get_coin_leverage', return_value=10):
                asyncio.run(handler.order_update_cb(payload))

        mock_journal.log_trade.assert_called_once()
        trade_data = mock_journal.log_trade.call_args[0][0]

        # Assert trailing fields
        assert trade_data['exit_type'] == 'TRAILING_STOP'
        assert trade_data['trailing_was_active'] is True
        assert trade_data['trailing_sl_final'] == 3150.50
        assert trade_data['trailing_high'] == 3300.00
        assert trade_data['trailing_low'] == 0
        assert trade_data['activation_price'] == 3250.00
        assert trade_data['sl_price_initial'] == 2900.00

    def test_position_close_without_trailing(self, handler, mock_journal, mock_executor):
        """Saat trailing tidak aktif, field trailing harus default values."""
        symbol = 'BTC/USDT'
        mock_executor.safety_orders_tracker[symbol] = {
            'side': 'SHORT',
            'entry_price': 60000,
            'strategy': 'AI_SWING',
            'ai_prompt': '-',
            'ai_reason': '-',
            'created_at': 0,
            'filled_at': 0,
            'technical_data': {},
            'config_snapshot': {},
            'order_type': 'MARKET',
            # No trailing data at all
        }

        payload = {
            'o': {
                's': 'BTCUSDT',
                'X': 'FILLED',
                'S': 'BUY',
                'o': 'TAKE_PROFIT_MARKET',
                'ap': '58000',
                'q': '0.01',
                'rp': '20',
                'n': '0.03',
                'i': '88888',
            }
        }

        with patch('src.modules.executor_impl.order_callbacks.kirim_tele', new_callable=AsyncMock):
            with patch('src.modules.executor_impl.order_callbacks.get_coin_leverage', return_value=10):
                asyncio.run(handler.order_update_cb(payload))

        mock_journal.log_trade.assert_called_once()
        trade_data = mock_journal.log_trade.call_args[0][0]

        # Assert trailing fields have default values
        assert trade_data['exit_type'] == 'TAKE_PROFIT'
        assert trade_data['trailing_was_active'] is False
        assert trade_data['trailing_sl_final'] == 0
        assert trade_data['trailing_high'] == 0
        assert trade_data['trailing_low'] == 0
        assert trade_data['activation_price'] == 0
        assert trade_data['sl_price_initial'] == 0


# =====================================================
# TEST: JOURNAL log_trade WITH TRAILING FIELDS
# =====================================================

class TestJournalTrailingFields:
    """Verifikasi journal.log_trade() menyimpan field trailing."""

    def test_journal_stores_trailing_fields(self):
        """Verifikasi trade_doc yang dikirim ke MongoDB mengandung field trailing."""
        with patch('src.modules.mongo_manager.MongoManager') as MockMongo:
            mock_mongo_instance = MagicMock()
            mock_mongo_instance.insert_trade.return_value = True
            MockMongo.return_value = mock_mongo_instance

            from src.modules.journal import TradeJournal
            journal = TradeJournal()
            journal.mongo = mock_mongo_instance

            trade_data = {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'type': 'MARKET',
                'entry_price': 50000,
                'exit_price': 55000,
                'size_usdt': 500,
                'pnl_usdt': 50,
                'strategy_tag': 'TEST',
                'prompt': 'test',
                'reason': 'test',
                'exit_type': 'TRAILING_STOP',
                'trailing_was_active': True,
                'trailing_sl_final': 54500.0,
                'trailing_high': 56000.0,
                'trailing_low': 0,
                'activation_price': 54000.0,
                'sl_price_initial': 48000.0,
            }

            result = journal.log_trade(trade_data)
            assert result is True

            # Verify MongoDB insert was called
            mock_mongo_instance.insert_trade.assert_called_once()
            stored_doc = mock_mongo_instance.insert_trade.call_args[0][0]

            assert stored_doc['exit_type'] == 'TRAILING_STOP'
            assert stored_doc['trailing_was_active'] is True
            assert stored_doc['trailing_sl_final'] == 54500.0
            assert stored_doc['trailing_high'] == 56000.0
            assert stored_doc['activation_price'] == 54000.0
            assert stored_doc['sl_price_initial'] == 48000.0

    def test_journal_backward_compat_no_trailing(self):
        """Trade tanpa field trailing masih bisa di-log (backward compatible)."""
        with patch('src.modules.mongo_manager.MongoManager') as MockMongo:
            mock_mongo_instance = MagicMock()
            mock_mongo_instance.insert_trade.return_value = True
            MockMongo.return_value = mock_mongo_instance

            from src.modules.journal import TradeJournal
            journal = TradeJournal()
            journal.mongo = mock_mongo_instance

            # Old-style trade data tanpa field trailing
            trade_data = {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'type': 'MARKET',
                'entry_price': 50000,
                'exit_price': 55000,
                'size_usdt': 500,
                'pnl_usdt': 50,
                'strategy_tag': 'OLD_STRATEGY',
                'prompt': 'old test',
                'reason': 'old reason',
                # NO trailing fields
            }

            result = journal.log_trade(trade_data)
            assert result is True

            stored_doc = mock_mongo_instance.insert_trade.call_args[0][0]

            # Should have default values
            assert stored_doc['exit_type'] == 'UNKNOWN'
            assert stored_doc['trailing_was_active'] is False
            assert stored_doc['trailing_sl_final'] == 0
            assert stored_doc['trailing_high'] == 0
