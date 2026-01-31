
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# --- SETUP PATHS ---
# Agar script ini bisa mengimpor modul 'src' dan 'config' dengan benar
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, 'src')

sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

from src.modules.onchain import OnChainAnalyzer
import config

class TestOnChainInflow(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = OnChainAnalyzer()
        
    @patch('src.modules.onchain.requests.get')
    def test_inflow_positive(self, mock_get):
        """
        Skenario: Market Cap Stablecoin NAIK signifikan (> Threshold)
        Harapan: Status menjadi 'Positive'
        """
        # Simulasi Data: Perlu > 2 item. 
        mock_data = [
            {'date': 1500000000, 'totalCirculatingUSD': {'peggedUSD': 100.0}}, # Dummy Data terlama
            {'date': 1600000000, 'totalCirculatingUSD': {'peggedUSD': 1000.0}}, # Data H-1
            {'date': 1600086400, 'totalCirculatingUSD': {'peggedUSD': 1100.0}}  # Data Terakhir (Naik)
        ]
        
        # Setup Mock
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response
        
        # Eksekusi
        self.analyzer.fetch_stablecoin_inflows()
        
        # Assert / Verifikasi
        print(f"\n[TEST] Positive Case: Inflow Status = {self.analyzer.stablecoin_inflow}")
        self.assertEqual(self.analyzer.stablecoin_inflow, "Positive")

    @patch('src.modules.onchain.requests.get')
    def test_inflow_negative(self, mock_get):
        """
        Skenario: Market Cap Stablecoin TURUN signifikan (< -Threshold)
        Harapan: Status menjadi 'Negative'
        """
        # Simulasi Data
        mock_data = [
             {'date': 1500000000, 'totalCirculatingUSD': {'peggedUSD': 100.0}},
             {'date': 1600000000, 'totalCirculatingUSD': {'peggedUSD': 1000.0}},
             {'date': 1600086400, 'totalCirculatingUSD': {'peggedUSD': 900.0}} # Turun
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response
        
        self.analyzer.fetch_stablecoin_inflows()
        
        print(f"[TEST] Negative Case: Inflow Status = {self.analyzer.stablecoin_inflow}")
        self.assertEqual(self.analyzer.stablecoin_inflow, "Negative")

    @patch('src.modules.onchain.requests.get')
    def test_inflow_neutral(self, mock_get):
        """
        Skenario: Perubahan kecil (Datar/Sideways)
        Harapan: Status menjadi 'Neutral'
        """
        # Simulasi Data
        mock_data = [
             {'date': 1500000000, 'totalCirculatingUSD': {'peggedUSD': 100.0}},
             {'date': 1600000000, 'totalCirculatingUSD': {'peggedUSD': 1000.0}},
             {'date': 1600086400, 'totalCirculatingUSD': {'peggedUSD': 1000.1}} # Naik tipis
        ]
        
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response
        
        self.analyzer.fetch_stablecoin_inflows()
        
        print(f"[TEST] Neutral Case:  Inflow Status = {self.analyzer.stablecoin_inflow}")
        self.assertEqual(self.analyzer.stablecoin_inflow, "Neutral")

    @patch('src.modules.onchain.requests.get')
    def test_api_failure(self, mock_get):
        """
        Skenario: API Error / Timeout
        Harapan: Status Default 'Neutral' dan tidak crash
        """
        mock_get.side_effect = Exception("API Timeout")
        
        self.analyzer.fetch_stablecoin_inflows()
        
        print(f"[TEST] Error Case:    Inflow Status = {self.analyzer.stablecoin_inflow}")
        self.assertEqual(self.analyzer.stablecoin_inflow, "Neutral")

    def test_real_connection(self):
        """
        Skenario: Test Koneksi ASLI (Integration Test).
        Akan melakukan request sungguhan ke DefiLlama.
        """
        print("\n--- [REAL DATA CHECK] Fetching from DefiLlama... ---")
        real_analyzer = OnChainAnalyzer()
        try:
            real_analyzer.fetch_stablecoin_inflows()
            print(f"✅ Real Data Fetch Success!")
            print(f"👉 Current Status: {real_analyzer.stablecoin_inflow}")
            # Kita tidak assert value spesifik karena data selalu berubah,
            # tapi kita assert tidak crash dan value valid string
            self.assertIn(real_analyzer.stablecoin_inflow, ["Positive", "Negative", "Neutral"])
        except Exception as e:
            self.fail(f"Real connection failed: {e}")


class TestWhaleActivityPerSymbol(unittest.TestCase):
    """Test untuk whale activity filtering per-symbol"""
    
    def setUp(self):
        self.analyzer = OnChainAnalyzer()
    
    def test_whale_stored_per_symbol(self):
        """Whale activity harus disimpan per-symbol dalam dict"""
        # Simulasi whale BTC
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")
        # Simulasi whale SOL
        self.analyzer.detect_whale("SOL/USDT", 2000000, "SELL")
        
        # Assert structure is dict per-symbol
        self.assertIsInstance(self.analyzer.whale_transactions, dict)
        self.assertIn("BTC/USDT", self.analyzer.whale_transactions)
        self.assertIn("SOL/USDT", self.analyzer.whale_transactions)
    
    def test_get_latest_returns_filtered_by_symbol(self):
        """get_latest(symbol) harus return whale hanya untuk symbol tsb"""
        # Simulasi whale BTC
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")
        # Simulasi whale SOL
        self.analyzer.detect_whale("SOL/USDT", 2000000, "SELL")
        
        # Get BTC data
        btc_data = self.analyzer.get_latest(symbol="BTC/USDT")
        self.assertEqual(len(btc_data['whale_activity']), 1)
        self.assertIn("BTC/USDT", btc_data['whale_activity'][0])
        
        # Get SOL data
        sol_data = self.analyzer.get_latest(symbol="SOL/USDT")
        self.assertEqual(len(sol_data['whale_activity']), 1)
        self.assertIn("SOL/USDT", sol_data['whale_activity'][0])
        
        # SOL data tidak boleh ada BTC
        self.assertFalse(any("BTC" in w for w in sol_data['whale_activity']))
    
    def test_get_latest_without_symbol_returns_empty(self):
        """get_latest() tanpa symbol harus return empty list (untuk global sentiment)"""
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")
        
        data = self.analyzer.get_latest()  # No symbol
        self.assertEqual(data['whale_activity'], [])
    
    def test_get_latest_unknown_symbol_returns_empty(self):
        """get_latest(unknown_symbol) harus return empty list"""
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")
        
        data = self.analyzer.get_latest(symbol="ETH/USDT")  # Unknown symbol
        self.assertEqual(data['whale_activity'], [])
    
    def test_deduplication_per_symbol(self):
        """De-duplication harus bekerja per-symbol"""
        import time
        
        # Whale BTC (akan di-skip karena identik)
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")
        time.sleep(0.1)  # Less than dedup window
        self.analyzer.detect_whale("BTC/USDT", 1500000, "BUY")  # Duplicate
        
        btc_data = self.analyzer.get_latest(symbol="BTC/USDT")
        self.assertEqual(len(btc_data['whale_activity']), 1, 
                        "Duplicate whale harus di-skip")


if __name__ == '__main__':
    unittest.main()

