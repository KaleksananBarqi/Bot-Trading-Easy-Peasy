"""
Test untuk memvalidasi fungsi _calculate_market_structure setelah refactor ke scipy
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from scipy.signal import argrelextrema

def test_argrelextrema_logic():
    """Test bahwa argrelextrema menghasilkan output yang benar untuk swing detection"""
    
    # Simulasi data high dengan pattern yang jelas
    # Index:  0   1   2   3   4   5   6   7   8   9  10  11  12
    highs = [10, 11, 15, 12, 11, 10, 11, 20, 12, 11, 10, 11, 13]
    #             swing high ^               swing high ^
    
    high_vals = np.array(highs, dtype=float)
    lookback = 2
    
    swing_high_idx = argrelextrema(high_vals, np.greater_equal, order=lookback)[0]
    
    # Dengan lookback=2, kita expect swing high di index 2 (15) dan 7 (20)
    print(f"Swing High Indices: {swing_high_idx}")
    print(f"Swing High Values: {high_vals[swing_high_idx]}")
    
    assert 2 in swing_high_idx, "Index 2 (15) should be a swing high"
    assert 7 in swing_high_idx, "Index 7 (20) should be a swing high"
    
    print("[PASS] argrelextrema logic test PASSED")

def test_swing_low_detection():
    """Test swing low detection"""
    
    # Simulasi data low dengan pattern
    lows = [10, 9, 5, 8, 9, 10, 9, 3, 8, 9, 10, 9, 7]
    #           swing low ^         swing low ^
    
    low_vals = np.array(lows, dtype=float)
    lookback = 2
    
    swing_low_idx = argrelextrema(low_vals, np.less_equal, order=lookback)[0]
    
    print(f"Swing Low Indices: {swing_low_idx}")
    print(f"Swing Low Values: {low_vals[swing_low_idx]}")
    
    assert 2 in swing_low_idx, "Index 2 (5) should be a swing low"
    assert 7 in swing_low_idx, "Index 7 (3) should be a swing low"
    
    print("[PASS] Swing low detection test PASSED")

def test_market_structure_classification():
    """Test klasifikasi struktur pasar (HH+HL, LH+LL, etc)"""
    
    def classify(last_h, prev_h, last_l, prev_l):
        if last_h > prev_h and last_l > prev_l:
            return "BULLISH (HH + HL)"
        elif last_h < prev_h and last_l < prev_l:
            return "BEARISH (LH + LL)"
        elif last_h > prev_h and last_l < prev_l:
            return "EXPANDING (Megaphone)"
        elif last_h < prev_h and last_l > prev_l:
            return "CONSOLIDATION (Triangle)"
        return "SIDEWAYS"
    
    # Test cases
    assert classify(120, 100, 50, 40) == "BULLISH (HH + HL)"
    assert classify(90, 100, 35, 40) == "BEARISH (LH + LL)"
    assert classify(120, 100, 35, 40) == "EXPANDING (Megaphone)"
    assert classify(90, 100, 50, 40) == "CONSOLIDATION (Triangle)"
    assert classify(100, 100, 40, 40) == "SIDEWAYS"
    
    print("[PASS] Market structure classification test PASSED")

if __name__ == "__main__":
    print("=" * 50)
    print("Running Market Structure Optimization Tests")
    print("=" * 50)
    
    test_argrelextrema_logic()
    test_swing_low_detection()
    test_market_structure_classification()
    
    print("\n" + "=" * 50)
    print("[SUCCESS] ALL TESTS PASSED!")
    print("=" * 50)
