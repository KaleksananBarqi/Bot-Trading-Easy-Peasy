import unittest
import sys
import os
import asyncio

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock Config before importing modules
import config
config.TIMEFRAME_EXEC = '15m'
config.PAKAI_DEMO = False # Avoid creating CCXT instance

from modules.market_data import MarketDataManager

class TestWickRejection(unittest.TestCase):
    def setUp(self):
        # Initialize with dummy exchange (None is fine as we don't call network methods)
        self.md = MarketDataManager(exchange=None)
        
    def test_bullish_rejection(self):
        # Scenario: Candle with long lower wick (Hammer-like)
        # Open=100, High=101, Low=90, Close=100.5
        # Body = 0.5
        # Upper Wick = 101 - 100.5 = 0.5
        # Lower Wick = 100 - 90 = 10.0
        # Ratio = 10.0 / 0.5 = 20x -> Strong Rejection
        
        # Format: [timestamp, open, high, low, close, volume]
        candle = [1000, 100.0, 101.0, 90.0, 100.5, 500.0]
        
        # Fill store manually
        self.md.market_store['BTC/USDT'] = {
            '15m': [candle] * 5 # Fill with candidate candles
        }
        
        res = self.md._calculate_wick_rejection('BTC/USDT', lookback=5)
        
        self.assertEqual(res['recent_rejection'], 'BULLISH_REJECTION')
        self.assertGreater(res['rejection_strength'], 5.0)
        self.assertEqual(res['rejection_candles'], 4) # 5 candles total, looks at last 4 candidates if we exclude current? 
        # Logic matches lookback logic in code.

    def test_bearish_rejection(self):
        # Scenario: Candle with long upper wick (Shooting Star)
        # Open=100, High=110, Low=99, Close=99.5
        # Body = 0.5
        # Upper Wick = 110 - 100 = 10.0
        # Lower Wick = 99.5 - 99 = 0.5
        # Upper > Body*2 -> YES
        
        candle = [1000, 100.0, 110.0, 99.0, 99.5, 500.0]
        self.md.market_store['BTC/USDT'] = {
            '15m': [candle] * 5
        }
        
        res = self.md._calculate_wick_rejection('BTC/USDT', lookback=5)
        self.assertEqual(res['recent_rejection'], 'BEARISH_REJECTION')

    def test_no_rejection_solid_body(self):
        # Scenario: Strong Bullish Candle
        # Open=100, High=110, Low=100, Close=110
        # Body = 10
        # Wicks = 0
        
        candle = [1000, 100.0, 110.0, 100.0, 110.0, 500.0]
        self.md.market_store['BTC/USDT'] = {
            '15m': [candle] * 5
        }
        
        res = self.md._calculate_wick_rejection('BTC/USDT', lookback=5)
        self.assertEqual(res['recent_rejection'], 'NONE')
        self.assertEqual(res['rejection_strength'], 0.0)

    def test_insufficient_data(self):
        self.md.market_store['BTC/USDT'] = {
            '15m': []
        }
        res = self.md._calculate_wick_rejection('BTC/USDT', lookback=5)
        self.assertEqual(res['recent_rejection'], 'NONE')

if __name__ == '__main__':
    unittest.main()
