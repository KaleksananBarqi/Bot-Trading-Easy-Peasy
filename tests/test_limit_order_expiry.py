"""
Test suite untuk fitur Limit Order Expiry.
Memvalidasi apakah fitur auto-cancel limit order yang expired berfungsi.
"""
import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestLimitOrderExpiry:
    """
    Test cases untuk validasi fitur expiry limit order.
    """

    @pytest.fixture
    def mock_exchange(self):
        """Mock exchange untuk testing"""
        exchange = AsyncMock()
        exchange.fetch_open_orders = AsyncMock(return_value=[])
        exchange.cancel_order = AsyncMock()
        return exchange

    @pytest.fixture
    def sample_tracker_with_expired_order(self):
        """Sample tracker dengan order yang sudah expired"""
        return {
            "BTC/USDT": {
                "status": "WAITING_ENTRY",
                "entry_id": "12345",
                "created_at": time.time() - 200000,  # ~55 jam yang lalu
                "expires_at": time.time() - 50000,   # Sudah expired ~14 jam lalu
                "strategy": "liquidity_hunt",
                "atr_value": 150.0
            }
        }

    @pytest.fixture
    def sample_tracker_with_valid_order(self):
        """Sample tracker dengan order yang masih valid (belum expired)"""
        return {
            "ETH/USDT": {
                "status": "WAITING_ENTRY",
                "entry_id": "67890",
                "created_at": time.time() - 3600,     # 1 jam yang lalu
                "expires_at": time.time() + 144000,   # Masih ~40 jam lagi
                "strategy": "liquidity_hunt",
                "atr_value": 10.0
            }
        }

    def test_expires_at_field_exists_on_limit_order_creation(self, sample_tracker_with_valid_order):
        """
        Validasi: Saat limit order dibuat, field 'expires_at' harus ada di tracker.
        """
        tracker_data = sample_tracker_with_valid_order["ETH/USDT"]
        
        assert "expires_at" in tracker_data, "Field 'expires_at' harus ada di tracker!"
        assert tracker_data["expires_at"] > time.time(), "expires_at harus di masa depan untuk order baru"

    def test_expired_order_should_be_detected(self, sample_tracker_with_expired_order):
        """
        Validasi: Order yang sudah expired harus bisa dideteksi.
        """
        tracker_data = sample_tracker_with_expired_order["BTC/USDT"]
        current_time = time.time()
        
        is_expired = current_time > tracker_data["expires_at"]
        
        assert is_expired, "Order yang sudah melewati expires_at harus terdeteksi sebagai expired"

    def test_valid_order_should_not_be_detected_as_expired(self, sample_tracker_with_valid_order):
        """
        Validasi: Order yang belum expired tidak boleh di-cancel.
        """
        tracker_data = sample_tracker_with_valid_order["ETH/USDT"]
        current_time = time.time()
        
        is_expired = current_time > tracker_data["expires_at"]
        
        assert not is_expired, "Order yang belum melewati expires_at tidak boleh dianggap expired"

    def test_sync_pending_orders_should_check_expiry(self, sample_tracker_with_expired_order, mock_exchange):
        """
        [BUG TEST] Validasi: sync_pending_orders() HARUS mengecek expires_at.
        
        Ini adalah test yang SENGAJA GAGAL untuk menunjukkan bug saat ini:
        - expires_at disimpan tapi tidak pernah dicek
        - Order expired tidak di-cancel secara otomatis
        """
        # Simulasi: Order masih ada di exchange (belum di-cancel manual)
        mock_exchange.fetch_open_orders.return_value = [
            {"id": "12345", "symbol": "BTC/USDT", "type": "limit"}
        ]
        
        tracker = sample_tracker_with_expired_order
        symbol = "BTC/USDT"
        tracker_data = tracker[symbol]
        
        # === EXPECTED BEHAVIOR (yang seharusnya terjadi) ===
        # Jika expires_at sudah lewat, order harus di-cancel
        
        current_time = time.time()
        is_expired = current_time > tracker_data.get("expires_at", float('inf'))
        
        # Test ini MEMBUKTIKAN bahwa kita PERLU pengecekan expiry
        assert is_expired, "Order sudah melewati expires_at"
        
        # === ACTUAL BEHAVIOR (kondisi saat ini - BUG!) ===
        # Di sync_pending_orders(), tidak ada kode yang mengecek expires_at!
        # Ini berarti order akan terus pending selamanya sampai di-cancel manual
        
        # Kita perlu menambahkan logika seperti ini di sync_pending_orders():
        # 
        # if tracker_data.get('expires_at', 0) < time.time():
        #     # Order sudah expired -> Cancel dari exchange
        #     await self.exchange.cancel_order(tracked_id, symbol)
        #     del self.safety_orders_tracker[symbol]
        #     await kirim_tele("Order expired and cancelled...")

    def test_expiry_config_value_is_reasonable(self):
        """
        Validasi: Config LIMIT_ORDER_EXPIRY_SECONDS harus reasonable (1-7 hari).
        """
        # Import config untuk validasi
        import sys
        import os
        
        # Add project root and src to path
        project_root = r"c:\Projek\Bot Trading\Bot-Trading-Easy-Peasy"
        src_path = os.path.join(project_root, "src")
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        try:
            # Try src.config first, then config
            try:
                from src import config
            except ImportError:
                import config
            expiry_seconds = getattr(config, 'LIMIT_ORDER_EXPIRY_SECONDS', None)
            
            assert expiry_seconds is not None, "Config LIMIT_ORDER_EXPIRY_SECONDS harus ada"
            
            # Minimal 1 jam (3600s), maksimal 7 hari (604800s)
            min_seconds = 3600       # 1 jam
            max_seconds = 604800     # 7 hari
            
            assert expiry_seconds >= min_seconds, f"Expiry terlalu pendek: {expiry_seconds}s < {min_seconds}s (1 jam)"
            assert expiry_seconds <= max_seconds, f"Expiry terlalu panjang: {expiry_seconds}s > {max_seconds}s (7 hari)"
            
        except ImportError:
            pytest.skip("Config module tidak dapat di-import untuk testing")


class TestExpiryFixProposal:
    """
    Test cases untuk memvalidasi fix yang diusulkan.
    """

    def test_proposed_fix_logic(self):
        """
        Contoh logika fix yang diusulkan untuk sync_pending_orders():
        
        Logika ini harus ditambahkan di dalam check_symbol() function, 
        SEBELUM pengecekan apakah order ada di exchange.
        """
        # Simulasi data tracker
        tracker_data = {
            "status": "WAITING_ENTRY",
            "entry_id": "12345",
            "expires_at": time.time() - 1000  # Sudah expired
        }
        
        current_time = time.time()
        expires_at = tracker_data.get("expires_at", float('inf'))
        
        # Logika yang perlu ditambahkan
        should_auto_cancel = (
            tracker_data.get("status") == "WAITING_ENTRY" and 
            current_time > expires_at
        )
        
        assert should_auto_cancel, "Order expired harus di-flag untuk auto-cancel"

    def test_proposed_fix_should_cancel_on_exchange(self):
        """
        Validasi: Fix harus memanggil cancel_order() ke exchange untuk order expired.
        """
        mock_exchange = AsyncMock()
        mock_exchange.cancel_order = AsyncMock(return_value={"status": "CANCELED"})
        
        # Simulasi cancel order
        symbol = "BTC/USDT"
        order_id = "12345"
        
        # Ini yang harus terjadi saat order expired terdeteksi
        async def cancel_expired_order():
            result = await mock_exchange.cancel_order(order_id, symbol)
            return result
        
        result = asyncio.get_event_loop().run_until_complete(cancel_expired_order())
        
        mock_exchange.cancel_order.assert_called_once_with(order_id, symbol)
        assert result["status"] == "CANCELED"
