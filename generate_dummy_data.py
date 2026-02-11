
import random
import time
from datetime import datetime, timedelta
from src.modules.journal import TradeJournal

def generate_dummy_data():
    journal = TradeJournal()
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT']
    strategies = ['AI_Standard_Market', 'AI_Liquidity_Hunt_Limit', 'AI_Trend_Following']
    sides = ['BUY', 'SELL']
    reasons = [
        "RSI Oversold + Bullish Divergence detected",
        "Breakout of key resistance level with volume",
        "Golden Cross on EMA 50/200",
        "Whale accumulation detected on-chain",
        "Sentiment analysis shows extreme greed",
        "Rejecting support zone with bullish engulfing"
    ]
    
    print("🚀 Generating 50 dummy trades...")
    
    start_time = datetime.now() - timedelta(days=30)
    
    for i in range(50):
        # Randomize Trade
        symbol = random.choice(symbols)
        side = random.choice(sides)
        strategy = random.choice(strategies)
        is_win = random.random() > 0.4 # 60% Winrate simulation
        
        entry_price = random.uniform(2000, 60000) if 'BTC' in symbol else random.uniform(10, 3000)
        size_usdt = random.uniform(50, 200)
        leverage = 20
        
        # PnL Calculation
        if is_win:
            pnl_percent = random.uniform(5, 50) # 5% to 50% profit
            pnl_usdt = (pnl_percent / 100) * size_usdt
        else:
            pnl_percent = random.uniform(-20, -5) # -5% to -20% loss
            pnl_usdt = (pnl_percent / 100) * size_usdt
            
        exit_price = entry_price * (1 + (pnl_percent/100/leverage)) if side == 'BUY' else entry_price * (1 - (pnl_percent/100/leverage))

        # Fee
        fee = size_usdt * leverage * 0.0004 # 0.04% fee
        pnl_usdt -= fee # Net PnL
        
        # [NEW] Timestamps for Durations
        # timestamp is close time (approx)
        timestamp_dt = start_time + timedelta(days=i*0.5 + random.uniform(0, 0.5))
        
        # setup -> filled (1-120 mins)
        filled_at_dt = timestamp_dt - timedelta(minutes=random.randint(5, 120))
        setup_at_dt = filled_at_dt - timedelta(minutes=random.randint(1, 15))
        
        setup_at = setup_at_dt.isoformat()
        filled_at = filled_at_dt.isoformat()

        trade_data = {
            'timestamp': timestamp_dt.isoformat(), # [NEW] Pass Valid Timestamp
            'symbol': symbol,
            'side': side,
            'type': 'MARKET' if 'Market' in strategy else 'LIMIT',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size_usdt': size_usdt,
            'pnl_usdt': pnl_usdt,
            'fee': fee,
            'roi_percent': pnl_percent, # Simplified ROI
            'strategy_tag': strategy,
            'prompt': f"Analyze {symbol} on 15m timeframe...",
            'reason': random.choice(reasons),
            'setup_at': setup_at,
            'filled_at': filled_at
        }
        
        # Log to CSV
        journal.log_trade(trade_data)
        
        # Hack timestamp to simulate history (Journal default uses now())
        # We need to manually overwrite the timestamp in CSV if we want history,
        # but for simplicity, let's just log them now as "Recent Trades".
        # Or better, let's manually build the CSV row if we want backdated.
        # But TradeJournal.log_trade uses datetime.now(). 
        # For dashboard test, "Just Now" data is fine, or we can tweak Journal class to accept timestamp.
        # Let's keep it simple: Real-time generation.
        
    print("✅ Done! 50 Trades generated.")
    print("👉 Now run: streamlit run dashboard.py")

if __name__ == "__main__":
    generate_dummy_data()
