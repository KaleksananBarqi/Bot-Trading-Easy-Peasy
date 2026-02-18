import sys
import os
import unittest
from unittest.mock import MagicMock

# --- MOCK DEPENDENCIES ---
# Internet is unreachable, so we mock libraries used in market_data.py
mock_modules = [
    'numpy', 'pandas', 'pandas_ta', 'ccxt', 'ccxt.async_support',
    'websockets', 'scipy', 'scipy.signal', 'dotenv', 'requests'
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Mock src.utils.helper to avoid its internal imports/logic
sys.modules['src.utils.helper'] = MagicMock()

# --- SETUP PATH ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Now we can import the function
from src.modules.market_data import _calculate_pivot_points_static

class TestPivotPoints(unittest.TestCase):
    def test_calculate_pivot_points_success(self):
        # Format: [timestamp, open, high, low, close, volume]
        bars = [
            [1000, 100, 110, 90, 105, 1000], # Previous candle (index -2)
            [2000, 105, 115, 100, 110, 1100]  # Current candle (index -1)
        ]

        # Calculation:
        # prev_candle = bars[-2] = [1000, 100, 110, 90, 105, 1000]
        # high = 110, low = 90, close = 105
        # pivot = (110 + 90 + 105) / 3 = 305 / 3 = 101.66666666666667
        # r1 = (2 * 101.66666666666667) - 90 = 203.33333333333334 - 90 = 113.33333333333334
        # s1 = (2 * 101.66666666666667) - 110 = 203.33333333333334 - 110 = 93.33333333333334
        # r2 = 101.66666666666667 + (110 - 90) = 121.66666666666667
        # s2 = 101.66666666666667 - (110 - 90) = 81.66666666666667

        result = _calculate_pivot_points_static(bars)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["P"], 101.66666666666667)
        self.assertAlmostEqual(result["R1"], 113.33333333333334)
        self.assertAlmostEqual(result["S1"], 93.33333333333334)
        self.assertAlmostEqual(result["R2"], 121.66666666666667)
        self.assertAlmostEqual(result["S2"], 81.66666666666667)

    def test_calculate_pivot_points_insufficient_data(self):
        # Only 1 bar
        bars = [[1000, 100, 110, 90, 105, 1000]]
        result = _calculate_pivot_points_static(bars)
        self.assertIsNone(result)

        # Empty list
        result = _calculate_pivot_points_static([])
        self.assertIsNone(result)

    def test_calculate_pivot_points_invalid_format(self):
        # Bar has only 2 elements, but index 2, 3, 4 are accessed
        bars = [
            [1000, 100],
            [2000, 105]
        ]
        result = _calculate_pivot_points_static(bars)
        self.assertIsNone(result)

    def test_calculate_pivot_points_with_multiple_bars(self):
        # Ensure it correctly picks the second-to-last bar
        bars = [
            [0, 50, 60, 40, 55, 500],
            [1000, 100, 110, 90, 105, 1000], # This one should be used (index -2)
            [2000, 105, 115, 100, 110, 1100]
        ]
        result = _calculate_pivot_points_static(bars)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["P"], 101.66666666666667)

if __name__ == "__main__":
    unittest.main()
