"""
Unit Test untuk fungsi calculate_trade_scenarios
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.utils.calc import calculate_trade_scenarios


def test_buy_trade_scenarios_basic():
    """Test skenario BUY dengan input dasar"""
    price = 100.0
    atr = 5.0
    side = 'BUY'
    precision = 4
    
    # Mock config values (ATR_MULTIPLIER_SL=1.0, ATR_MULTIPLIER_TP1=3.0, TRAP_SAFETY_SL=2.0)
    # Market scenario:
    #   entry = 100.0
    #   dist_sl = 5.0 * 1.0 = 5.0
    #   dist_tp = 5.0 * 3.0 = 15.0
    #   sl = 100.0 - 5.0 = 95.0
    #   tp = 100.0 + 15.0 = 115.0
    #   rr = 15.0 / 5.0 = 3.0
    # Liquidity Hunt scenario:
    #   entry_offset = 5.0 * 1.0 = 5.0
    #   sl_safety = 5.0 * 2.0 = 10.0
    #   tp_reward = 5.0 * 3.0 = 15.0
    #   entry = 100.0 - 5.0 = 95.0
    #   sl = 95.0 - 10.0 = 85.0
    #   tp = 95.0 + 15.0 = 110.0
    #   rr = 15.0 / 10.0 = 1.5
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Verify structure
    assert 'market' in result
    assert 'liquidity_hunt' in result
    
    # Verify market scenario
    assert result['market']['entry'] == 100.0
    assert result['market']['sl'] == 95.0
    assert result['market']['tp'] == 115.0
    assert result['market']['rr'] == 3.0
    
    # Verify liquidity hunt scenario
    assert result['liquidity_hunt']['entry'] == 95.0
    assert result['liquidity_hunt']['sl'] == 85.0
    assert result['liquidity_hunt']['tp'] == 110.0
    assert result['liquidity_hunt']['rr'] == 1.5
    
    print("[PASS] test_buy_trade_scenarios_basic PASSED")


def test_sell_trade_scenarios_basic():
    """Test skenario SELL dengan input dasar"""
    price = 100.0
    atr = 5.0
    side = 'SELL'
    precision = 4
    
    # Market scenario:
    #   entry = 100.0
    #   dist_sl = 5.0 * 1.0 = 5.0
    #   dist_tp = 5.0 * 3.0 = 15.0
    #   sl = 100.0 + 5.0 = 105.0
    #   tp = 100.0 - 15.0 = 85.0
    #   rr = 15.0 / 5.0 = 3.0
    # Liquidity Hunt scenario:
    #   entry_offset = 5.0 * 1.0 = 5.0
    #   sl_safety = 5.0 * 2.0 = 10.0
    #   tp_reward = 5.0 * 3.0 = 15.0
    #   entry = 100.0 + 5.0 = 105.0
    #   sl = 105.0 + 10.0 = 115.0
    #   tp = 105.0 - 15.0 = 90.0
    #   rr = 15.0 / 10.0 = 1.5
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Verify market scenario
    assert result['market']['entry'] == 100.0
    assert result['market']['sl'] == 105.0
    assert result['market']['tp'] == 85.0
    assert result['market']['rr'] == 3.0
    
    # Verify liquidity hunt scenario
    assert result['liquidity_hunt']['entry'] == 105.0
    assert result['liquidity_hunt']['sl'] == 115.0
    assert result['liquidity_hunt']['tp'] == 90.0
    assert result['liquidity_hunt']['rr'] == 1.5
    
    print("[PASS] test_sell_trade_scenarios_basic PASSED")


def test_case_insensitive_side():
    """Test case insensitivity untuk parameter side"""
    price = 100.0
    atr = 5.0
    precision = 4
    
    # Test lowercase 'buy'
    result_lower = calculate_trade_scenarios(price, atr, 'buy', precision)
    assert result_lower['market']['sl'] == 95.0  # BUY logic
    
    # Test lowercase 'sell'
    result_lower_sell = calculate_trade_scenarios(price, atr, 'sell', precision)
    assert result_lower_sell['market']['sl'] == 105.0  # SELL logic
    
    # Test mixed case
    result_mixed = calculate_trade_scenarios(price, atr, 'Buy', precision)
    assert result_mixed['market']['sl'] == 95.0
    
    print("[PASS] test_case_insensitive_side PASSED")


def test_different_precision_values():
    """Test dengan berbagai nilai precision"""
    price = 100.123456
    atr = 0.123456
    side = 'BUY'
    
    # Test precision 2
    result_2 = calculate_trade_scenarios(price, atr, side, precision=2)
    assert len(str(result_2['market']['entry']).split('.')[1]) <= 2
    
    # Test precision 6
    result_6 = calculate_trade_scenarios(price, atr, side, precision=6)
    assert len(str(result_6['market']['entry']).split('.')[1]) <= 6
    
    print("[PASS] test_different_precision_values PASSED")


def test_zero_atr_edge_case():
    """Test edge case dengan ATR = 0"""
    price = 100.0
    atr = 0.0
    side = 'BUY'
    
    result = calculate_trade_scenarios(price, atr, side)
    
    # With ATR = 0, all distances are 0
    assert result['market']['entry'] == 100.0
    assert result['market']['sl'] == 100.0
    assert result['market']['tp'] == 100.0
    assert result['market']['rr'] == 0.0  # Division by zero protection
    
    assert result['liquidity_hunt']['entry'] == 100.0
    assert result['liquidity_hunt']['sl'] == 100.0
    assert result['liquidity_hunt']['tp'] == 100.0
    assert result['liquidity_hunt']['rr'] == 0.0  # Division by zero protection
    
    print("[PASS] test_zero_atr_edge_case PASSED")


def test_very_small_atr():
    """Test dengan ATR yang sangat kecil"""
    price = 50000.0  # BTC price
    atr = 0.001
    side = 'BUY'
    precision = 4
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Verify calculations still work with small ATR
    assert result['market']['entry'] == 50000.0
    assert result['market']['sl'] < result['market']['entry']  # SL should be below entry for BUY
    assert result['market']['tp'] > result['market']['entry']  # TP should be above entry for BUY
    assert result['market']['rr'] == 3.0  # TP multiplier / SL multiplier = 3.0 / 1.0
    
    print("[PASS] test_very_small_atr PASSED")


def test_very_large_atr():
    """Test dengan ATR yang sangat besar"""
    price = 100.0
    atr = 50.0
    side = 'SELL'
    precision = 4
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Verify calculations work with large ATR
    assert result['market']['entry'] == 100.0
    assert result['market']['sl'] > result['market']['entry']  # SL should be above entry for SELL
    assert result['market']['tp'] < result['market']['entry']  # TP should be below entry for SELL
    
    print("[PASS] test_very_large_atr PASSED")


def test_btc_like_price_levels():
    """Test dengan harga mirip BTC ($50,000+)"""
    price = 50000.0
    atr = 500.0
    side = 'BUY'
    precision = 2
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Market scenario: sl = 50000 - 500 = 49500, tp = 50000 + 1500 = 51500
    assert result['market']['entry'] == 50000.0
    assert result['market']['sl'] == 49500.0
    assert result['market']['tp'] == 51500.0
    assert result['market']['rr'] == 3.0
    
    # Liquidity hunt: entry = 50000 - 500 = 49500, sl = 49500 - 1000 = 48500, tp = 49500 + 1500 = 51000
    assert result['liquidity_hunt']['entry'] == 49500.0
    assert result['liquidity_hunt']['sl'] == 48500.0
    assert result['liquidity_hunt']['tp'] == 51000.0
    assert result['liquidity_hunt']['rr'] == 1.5
    
    print("[PASS] test_btc_like_price_levels PASSED")


def test_low_price_crypto():
    """Test dengan harga kripto murah (< $1)"""
    price = 0.5
    atr = 0.01
    side = 'SELL'
    precision = 4
    
    result = calculate_trade_scenarios(price, atr, side, precision)
    
    # Verify calculations work with low prices
    assert result['market']['entry'] == 0.5
    assert result['market']['sl'] > result['market']['entry']  # SELL: SL above entry
    assert result['market']['tp'] < result['market']['entry']  # SELL: TP below entry
    
    print("[PASS] test_low_price_crypto PASSED")


def test_rr_calculation_mathematical_correctness():
    """Test kebenaran matematis perhitungan Risk/Reward ratio"""
    price = 1000.0
    atr = 20.0
    side = 'BUY'
    
    result = calculate_trade_scenarios(price, atr, side)
    
    # Manual calculation verification
    # Market: dist_sl = 20 * 1.0 = 20, dist_tp = 20 * 3.0 = 60
    # rr = 60 / 20 = 3.0
    expected_market_rr = (atr * 3.0) / (atr * 1.0)
    assert abs(result['market']['rr'] - expected_market_rr) < 0.01
    
    # Liquidity Hunt: dist_sl_safety = 20 * 2.0 = 40, dist_tp_reward = 20 * 3.0 = 60
    # rr = 60 / 40 = 1.5
    expected_hunt_rr = (atr * 3.0) / (atr * 2.0)
    assert abs(result['liquidity_hunt']['rr'] - expected_hunt_rr) < 0.01
    
    print("[PASS] test_rr_calculation_mathematical_correctness PASSED")


def test_default_precision_parameter():
    """Test default parameter precision"""
    price = 100.123456789
    atr = 5.0
    side = 'BUY'
    
    # Call without precision parameter (should default to 4)
    result = calculate_trade_scenarios(price, atr, side)
    
    # Verify values are rounded to 4 decimal places
    entry_decimal_places = len(str(result['market']['entry']).split('.')[1])
    assert entry_decimal_places <= 4
    
    print("[PASS] test_default_precision_parameter PASSED")


def test_both_scenarios_have_required_fields():
    """Test bahwa kedua skenario memiliki field yang diperlukan"""
    result = calculate_trade_scenarios(100.0, 5.0, 'BUY')
    
    required_fields = ['entry', 'sl', 'tp', 'rr']
    
    for scenario_name in ['market', 'liquidity_hunt']:
        assert scenario_name in result
        for field in required_fields:
            assert field in result[scenario_name], f"Missing field '{field}' in {scenario_name}"
            assert isinstance(result[scenario_name][field], (int, float)), \
                f"Field '{field}' in {scenario_name} should be numeric"
    
    print("[PASS] test_both_scenarios_have_required_fields PASSED")


def test_negative_price_atr_handling():
    """Test handling input negative (meskipun tidak realistis)"""
    # This tests the function's behavior with negative inputs
    price = -100.0
    atr = 5.0
    side = 'BUY'
    
    result = calculate_trade_scenarios(price, atr, side)
    
    # Function should still calculate (even though negative price doesn't make sense)
    assert 'market' in result
    assert 'liquidity_hunt' in result
    
    print("[PASS] test_negative_price_atr_handling PASSED")


if __name__ == '__main__':
    test_buy_trade_scenarios_basic()
    test_sell_trade_scenarios_basic()
    test_case_insensitive_side()
    test_different_precision_values()
    test_zero_atr_edge_case()
    test_very_small_atr()
    test_very_large_atr()
    test_btc_like_price_levels()
    test_low_price_crypto()
    test_rr_calculation_mathematical_correctness()
    test_default_precision_parameter()
    test_both_scenarios_have_required_fields()
    test_negative_price_atr_handling()
    print("\n[SUCCESS] All calculate_trade_scenarios tests passed!")
