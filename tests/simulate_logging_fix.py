
import asyncio
import time
from datetime import datetime

# Mock objects to simulate the environment
class MockTracker:
    def __init__(self):
        self.data = {
            "BTC/USDT": {
                "status": "SECURED",
                "entry_price": 50000.0,
                "side": "LONG",
                "order_type": "LIMIT", # This is what we want to test!
                "strategy": "TEST_STRATEGY",
                "created_at": time.time(),
                "filled_at": time.time(),
            }
        }
    
    def get(self, symbol, default=None):
        return self.data.get(symbol, default)

class MockJournal:
    def log_trade(self, data):
        print(f"\n[JOURNAL LOG] Trade Logged:")
        print(f"Symbol: {data['symbol']}")
        print(f"Type: {data['type']} <--- CHECK THIS VALUE")
        print(f"Entry Price: {data['entry_price']}")
        print(f"Exit Price: {data['exit_price']}")
        
async def simulate_logging():
    print("--- START SIMULATION ---")
    
    symbol = "BTC/USDT"
    tracker = MockTracker().get(symbol)
    
    # Simulate Order Update Payload (Closing Order - MARKET)
    # in main.py this matches 'o' variable
    order_info = {
        's': 'BTCUSDT',
        'S': 'SELL',
        'o': 'MARKET', # Closing order is MARKET
        'ap': 51000.0, # Exit Price
        'q': 0.01,
        'n': 0.5 # Fee
    }
    
    price = 51000.0
    size_closed_usdt = 510.0
    pnl = 10.0
    roi_percent = 2.0
    
    # --- LOGIC COPIED FROM main.py (Updated) ---
    
    # [FIX] Get Order Type from Tracker (Entry Type), not Closing Order Type
    entry_order_type = tracker.get('order_type', 'MARKET')

    trade_data = {
        'symbol': symbol,
        'side': tracker.get('side', 'LONG' if order_info['S'] == 'SELL' else 'SHORT'), 
        'type': entry_order_type,
        'entry_price': tracker.get('entry_price', 0), # Ambil dari tracker
        'exit_price': price,
        'size_usdt': size_closed_usdt,
        'pnl_usdt': pnl,
        'roi_percent': roi_percent,
        'fee': float(order_info.get('n', 0)), # Commission Asset
        'strategy_tag': tracker.get('strategy', 'UNKNOWN'),
        # ... other fields ignored for test
    }
    
    # --- END LOGIC ---
    
    journal = MockJournal()
    journal.log_trade(trade_data)
    
    if trade_data['type'] == 'LIMIT':
        print("\n✅ SUCCESS: Order Type is LIMIT (taken from tracker)")
    else:
        print(f"\n❌ FAILED: Order Type is {trade_data['type']} (expected LIMIT)")

if __name__ == "__main__":
    asyncio.run(simulate_logging())
