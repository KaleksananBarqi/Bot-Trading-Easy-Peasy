import unittest
import sys
import os

# Add project root to sys.path to simulate environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Config Object
class MockConfig:
    TRAP_SAFETY_SL = 1.0       # 1x ATR
    ATR_MULTIPLIER_TP1 = 2.0   # 2x ATR

class TestNotificationLogic(unittest.TestCase):
    def setUp(self):
        self.config = MockConfig()
        
    def calculate_tp_sl(self, side_filled, price_filled, atr_val):
        """
        Replikasi persis logika yang ada di main.py untuk pengujian.
        """
        tp_str = "-"
        sl_str = "-"
        rr_str = "-"
        
        if atr_val > 0:
            dist_sl = atr_val * self.config.TRAP_SAFETY_SL
            dist_tp = atr_val * self.config.ATR_MULTIPLIER_TP1
            
            if side_filled.upper() == 'BUY':
                sl_p = price_filled - dist_sl
                tp_p = price_filled + dist_tp
            else: # SELL
                sl_p = price_filled + dist_sl
                tp_p = price_filled - dist_tp
                
            tp_str = f"{tp_p:.4f}"
            sl_str = f"{sl_p:.4f}"
            
            rr = dist_tp / dist_sl if dist_sl > 0 else 0
            rr_str = f"1:{rr:.2f}"
            
        return tp_str, sl_str, rr_str

    def test_buy_scenario(self):
        """Test perhitungan untuk posisi BUY"""
        logger_name = "TEST_BUY"
        print(f"\n--- {logger_name} ---")
        
        price = 50000.0
        atr = 100.0
        side = 'BUY'
        
        # Expectation:
        # SL = 50000 - (100 * 1.0) = 49900
        # TP = 50000 + (100 * 2.0) = 50200
        # RR = 2.0 / 1.0 = 2.0
        
        tp, sl, rr = self.calculate_tp_sl(side, price, atr)
        
        print(f"Input: Price={price}, ATR={atr}, Side={side}")
        print(f"Output: TP={tp}, SL={sl}, RR={rr}")
        
        self.assertEqual(tp, "50200.0000")
        self.assertEqual(sl, "49900.0000")
        self.assertEqual(rr, "1:2.00")

    def test_sell_scenario(self):
        """Test perhitungan untuk posisi SELL"""
        logger_name = "TEST_SELL"
        print(f"\n--- {logger_name} ---")
        
        price = 2000.0
        atr = 10.0
        side = 'SELL'
        
        # Expectation:
        # SL = 2000 + (10 * 1.0) = 2010
        # TP = 2000 - (10 * 2.0) = 1980
        
        tp, sl, rr = self.calculate_tp_sl(side, price, atr)
        
        print(f"Input: Price={price}, ATR={atr}, Side={side}")
        print(f"Output: TP={tp}, SL={sl}, RR={rr}")
        
        self.assertEqual(tp, "1980.0000")
        self.assertEqual(sl, "2010.0000")
        self.assertEqual(rr, "1:2.00")

    def test_no_atr_scenario(self):
        """Test jika ATR tidak ada (0 atau None)"""
        logger_name = "TEST_NO_ATR"
        print(f"\n--- {logger_name} ---")
        
        price = 100.0
        atr = 0
        side = 'BUY'
        
        tp, sl, rr = self.calculate_tp_sl(side, price, atr)
        
        print(f"Input: Price={price}, ATR={atr} (Missing)")
        print(f"Output: TP={tp}, SL={sl}, RR={rr}")
        
        self.assertEqual(tp, "-")
        self.assertEqual(sl, "-")
        self.assertEqual(rr, "-")

if __name__ == '__main__':
    unittest.main()
