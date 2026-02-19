import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# --- MOCK DEPENDENCIES BEFORE IMPORT ---
# We need to mock 'config' because market_data.py imports it and uses attributes 
# in function defaults (e.g. CORRELATION_PERIOD) which are evaluated at import time.
mock_config = MagicMock()
mock_config.MIN_BARS_MARKET_STRUCTURE = 5
mock_config.CORRELATION_PERIOD = 20
mock_config.EMA_FAST = 9
mock_config.EMA_SLOW = 21
mock_config.RSI_PERIOD = 14
mock_config.ADX_PERIOD = 14
mock_config.STOCHRSI_LEN = 14
mock_config.STOCHRSI_K = 3
mock_config.STOCHRSI_D = 3
mock_config.BB_LENGTH = 20
mock_config.BB_STD = 2.0
mock_config.ATR_PERIOD = 14
mock_config.VOL_MA_PERIOD = 20
mock_config.EMA_TREND_MAJOR = 200
mock_config.BTC_SYMBOL = "BTC/USDT"
mock_config.WS_URL_FUTURES_TESTNET = "wss://..."
mock_config.WS_URL_FUTURES_LIVE = "wss://..."
mock_config.PAKAI_DEMO = True
mock_config.DAFTAR_KOIN = []
mock_config.TIMEFRAME_EXEC = '1m'
mock_config.TIMEFRAME_TREND = '1h'
mock_config.TIMEFRAME_SETUP = '1d'
mock_config.LIMIT_EXEC = 100
mock_config.LIMIT_TREND = 100
mock_config.LIMIT_SETUP = 100
mock_config.CONCURRENCY_LIMIT = 5
mock_config.WS_KEEP_ALIVE_INTERVAL = 60
mock_config.WHALE_THRESHOLD_USDT = 100000
mock_config.WICK_REJECTION_MIN_BODY_RATIO = 0.1
mock_config.WICK_REJECTION_MIN_BODY_REF = 0.1
mock_config.WICK_REJECTION_MULTIPLIER = 2.0
mock_config.DEFAULT_CORRELATION_HIGH = 0.8

sys.modules['config'] = mock_config

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.market_data import _calculate_market_structure_static

class TestMarketStructure(unittest.TestCase):
    
    def setUp(self):
        # Setup common mock data if needed
        pass

    def create_bars(self, prices, volume=100.0, base_ts=1000):
        """Helper to create bars list from a list of Close prices.
        Assumes Open=Close, High=Close+1, Low=Close-1 for simplicity, 
        unless specific patterns are needed for High/Low."""
        bars = []
        for i, p in enumerate(prices):
            # [timestamp, open, high, low, close, volume]
            # Structure logic uses High and Low.
            # So we typically pass (High, Low) or just use logic to set them.
            # To make it simple, let's allow passing tuples (High, Low) or just Close.
            
            if isinstance(p, (tuple, list)):
                h, l = p
                o = c = (h + l) / 2
            else:
                c = p
                h = p
                l = p
                o = p
                
            bars.append([base_ts + i*60, o, h, l, c, volume])
        return bars

    def test_insufficient_data(self):
        """Test returning INSUFFICIENT_DATA if bars count < config limit"""
        # Config default is likely 50 based on original code check
        # Let's mock config.MIN_BARS_MARKET_STRUCTURE to be sure or use a very small list
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            bars = self.create_bars([10] * 5) # Only 5 bars
            result = _calculate_market_structure_static(bars)
            self.assertEqual(result, "INSUFFICIENT_DATA")

    def test_bullish_structure(self):
        """Test HH + HL pattern"""
        # We need enough bars. Let's say 20 bars.
        # We need swings.
        # Swing Highs: A, B (B > A)
        # Swing Lows: X, Y (Y > X)
        
        # Pattern: Low -> High -> Higher Low -> Higher High
        # Let's verify with indices.
        # 0..4: Low base
        # 5: High (A) = 100
        # 8: Low (X) = 50
        # 12: High (B) = 110 (Higher High)
        # 15: Low (Y) = 60 (Higher Low)
        # 16..19: Current price action
        
        # Need config.MIN_BARS_MARKET_STRUCTURE to be met.
        # Let's assume we patch it to 10 for easier testing.
        
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            # Construct a wave
            # Indices:  0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18
            highs =   [10, 20, 30, 40, 50,100, 90, 80, 50, 60, 70, 80,110, 90, 80, 60, 70, 75, 80]
            # HH at 12 (110) > HH at 5 (100)
            
            lows =    [ 5, 15, 25, 35, 45, 95, 85, 45, 50, 55, 65, 75,105, 85, 55, 60, 65, 70, 75]
            # HL at 15 (60) > HL at 8 (50)
            
            # Combine into bars
            bars = []
            for h, l in zip(highs, lows):
                bars.append([1000, 100, h, l, 100, 100])
                
            # Lookback is default 5.
            # argrelextrema checks 5 points either side.
            # Index 5 is order 5 max? 0..5..10. 
            # Sub-sequence: [10, 20, 30, 40, 50, 100, 90, 80, 50, 60, 70]
            # 100 is max.
            
            # Use smaller lookback for easier manual construction
            result = _calculate_market_structure_static(bars, lookback=2)
            
            # Debug helps if test fails
            # Swing Highs expected at index 5 (100) and 12 (110). 110 > 100 -> HH
            # Swing Lows expected at index 8 (50) and 15 (60). 60 > 50 -> HL
            
            self.assertEqual(result, "BULLISH (HH + HL)")

    def test_bearish_structure(self):
        """Test LH + LL pattern"""
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            # Indices: 0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16
            highs =   [50, 60, 70,100, 90, 80, 70, 60, 90, 80, 70, 60, 50, 40, 30, 20, 10]
            # Lower Highs needed.
            # Let's try simpler manually crafted peaks with lookback=2
            
            # Values:
            # 5: High=100
            # 8: Low=50
            # 11: High=90 (Lower High)
            # 14: Low=40 (Lower Low)
            
            # H: 50,60,70,80,90,100,90,80,90,80,70,90,80,70,50,40,50
            # Wait, let's be precise.
            
            # Trend Down:
            # P1 (High): 100 (idx 3)
            # T1 (Low): 50 (idx 6)
            # P2 (High): 80 (idx 9) -> LH
            # T2 (Low): 30 (idx 12) -> LL
            
            highs = [50, 60, 80, 100, 80, 70, 60, 70, 80, 90, 80, 70, 60, 40, 30, 40, 50]
            lows =  [40, 50, 60,  90, 60, 50, 50, 60, 70, 80, 60, 50, 30, 20, 20, 30, 40]
            
            # idx 3 (100) is > 1,2 and 4,5 (lookback 2) -> Peak
            # idx 9 (90) is > 7,8 and 10,11 -> Peak
            # 90 < 100 -> Lower High
            
            # idx 6 (50) is < 4,5 and 7,8 -> Trough
            # idx 13 (20) is < 11,12 and 14,15 -> Trough
            # 20 < 50 -> Lower Low
            
            bars = []
            for h, l in zip(highs, lows):
                bars.append([1000, 100, h, l, 100, 100])
                
            result = _calculate_market_structure_static(bars, lookback=2)
            self.assertEqual(result, "BEARISH (LH + LL)")

    def test_expanding_structure_megaphone(self):
        """Test Higher High + Lower Low"""
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            # HH + LL
            # Peak 1: 100
            # Peak 2: 110 (Higher)
            # Trough 1: 50
            # Trough 2: 40 (Lower)
            
            # Structure: 
            # Up to 100, Down to 50, Up to 110, Down to 40
            
            # idx 3: 100 (Peak)
            # idx 6: 50 (Trough)
            # idx 9: 110 (Peak)
            # idx 12: 40 (Trough)
            
            highs = [80, 90, 95, 100, 90, 80, 60, 80, 90, 110, 90, 80, 50, 45, 50, 60]
            lows =  [70, 80, 85,  95, 80, 70, 50, 70, 80, 100, 80, 70, 40, 35, 40, 50]
            
            bars = []
            for h, l in zip(highs, lows):
                bars.append([1000, 100, h, l, 100, 100])
                
            result = _calculate_market_structure_static(bars, lookback=2)
            self.assertEqual(result, "EXPANDING (Megaphone)")

    def test_consolidation_structure_triangle(self):
        """Test Lower High + Higher Low"""
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            # LH + HL
            # Peak 1: 100
            # Peak 2: 90 (Lower)
            # Trough 1: 50
            # Trough 2: 60 (Higher)
            
            # idx 3: 100
            # idx 6: 50
            # idx 9: 90
            # idx 12: 60
            
            highs = [80, 90, 95, 100, 90, 80, 60, 80, 85, 90, 85, 80, 70, 65, 70, 75, 75, 75]
            lows =  [70, 80, 85,  95, 80, 70, 50, 70, 75, 85, 75, 70, 60, 55, 60, 65, 65, 65]
            
            bars = []
            for h, l in zip(highs, lows):
                bars.append([1000, 100, h, l, 100, 100])
                
            result = _calculate_market_structure_static(bars, lookback=2)
            self.assertEqual(result, "CONSOLIDATION (Triangle)")

    def test_unclear_few_swings(self):
        """Test return UNCLEAR if swings found < 2"""
        with patch('config.MIN_BARS_MARKET_STRUCTURE', 10):
            # Straight line up, no swings
            highs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            lows =  [ 5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
            
            bars = []
            for h, l in zip(highs, lows):
                bars.append([1000, 100, h, l, 100, 100])
                
            result = _calculate_market_structure_static(bars, lookback=2)
            self.assertEqual(result, "UNCLEAR")
            
    def test_error_handling(self):
        """Test graceful error handling"""
        # Malformed bars (e.g., None)
        bars = None
        result = _calculate_market_structure_static(bars)
        # Should catch exception and return ERROR or handle len() check crash?
        # The code calculates len(bars) first. if bars is None -> TypeError
        # The function wraps in try-except and returns "ERROR" or similar?
        
        # Checking code:
        # try:
        #   if len(bars) < ...
        # except Exception as e: return "ERROR"
        
        # So passing None should trigger TypeError on len(), caught by except -> "ERROR"
        self.assertEqual(result, "ERROR")

if __name__ == '__main__':
    unittest.main()
