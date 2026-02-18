
import sys
import os
import random
import time
from datetime import datetime, timedelta
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.modules.mongo_manager import MongoManager
from src.utils.helper import logger
from src import config

def generate_dummy_data(count=50):
    mongo = MongoManager()
    
    if mongo.db is None:
        logger.error("❌ Cannot generate dummy data: MongoDB not connected.")
        return

    logger.info(f"🔄 Generating {count} dummy trades...")
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT', 'DOGE/USDT']
    strategies = ['LIQUIDITY_REVERSAL_MASTER', 'PULLBACK_CONTINUATION', 'BREAKDOWN_FOLLOW']
    results = ['WIN', 'LOSS', 'BREAKEVEN']
    
    trades = []
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    for i in range(count):
        # Random timestamp within last 30 days
        random_seconds = random.randint(0, int((end_time - start_time).total_seconds()))
        setup_at = start_time + timedelta(seconds=random_seconds)
        filled_at = setup_at + timedelta(minutes=random.randint(1, 60)) # Entry fill 1-60 mins after setup
        closed_at = filled_at + timedelta(hours=random.randint(1, 48)) # Trade duration 1-48 hours
        
        symbol = random.choice(symbols)
        side = random.choice(['BUY', 'SELL'])
        entry_price = random.uniform(20000, 70000) if 'BTC' in symbol else random.uniform(10, 3000)
        
        # Determine Result
        outcome = random.choices(results, weights=[50, 40, 10])[0]
        
        if outcome == 'WIN':
            exit_price = entry_price * (1 + random.uniform(0.02, 0.10)) if side == 'BUY' else entry_price * (1 - random.uniform(0.02, 0.10))
            pnl_usdt = random.uniform(10, 500)
            roi = random.uniform(10, 150)
        elif outcome == 'LOSS':
            exit_price = entry_price * (1 - random.uniform(0.01, 0.05)) if side == 'BUY' else entry_price * (1 + random.uniform(0.01, 0.05))
            pnl_usdt = -random.uniform(5, 200)
            roi = -random.uniform(5, 50)
        else: # BREAKEVEN
            exit_price = entry_price
            pnl_usdt = 0
            roi = 0

        # Technical Data Dummy - Enhanced
        tech_data = {
            'rsi': round(random.uniform(30, 70), 2),
            'atr': round(random.uniform(10, 500) if 'BTC' in symbol else random.uniform(0.1, 5), 4),
            'adx': round(random.uniform(20, 50), 2),
            'price': round(entry_price, 2), # Snapshot price at entry
            'stoch_rsi_k': round(random.uniform(0, 100), 2),
            'stoch_rsi_d': round(random.uniform(0, 100), 2),
            'price_vs_ema': 'Above' if side == 'BUY' else 'Below',
            'btc_trend': 'BULLISH' if random.random() > 0.5 else 'BEARISH',
            'btc_correlation': round(random.uniform(0.5, 0.95), 2),
            'order_book_imbalance': round(random.uniform(-20, 20), 2)
        }
        
        # Config Snapshot Dummy - Enhanced
        conf_snap = {
            'leverage': 10,
            'risk_percent': 3,
            'ai_model': 'deepseek-v3', # Match dashboard key
            'model': 'deepseek-v3',    # Keep legacy key just in case
            'atr_multiplier_tp': random.choice([2.5, 3.0, 4.0]),
            'trap_safety_sl': random.choice([1.0, 1.5]),
            'ai_confidence': random.randint(75, 95),
            'timeframe_exec': '15m',
            'strategy_mode': 'AGGRESSIVE',
            'exec_mode': 'AUTO'
        }

        trade = {
            'timestamp': closed_at.isoformat(), # Main sorting timestamp (usually close time)
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'entry_price': round(entry_price, 4),
            'exit_price': round(exit_price, 4),
            'size_usdt': round(random.uniform(100, 1000), 2),
            'pnl_usdt': round(pnl_usdt, 2),
            'pnl_percent': round(roi / 10, 2), # Rough param
            'roi_percent': round(roi, 2),
            'fee': round(random.uniform(0.1, 2.0), 4),
            'strategy_tag': random.choice(strategies),
            'result': outcome,
            'prompt': 'Dummy AI Prompt... Analysis of market structure indicates bullish divergence...',
            'reason': 'Bullish Divergence on RSI with strong volume support.',
            'setup_at': setup_at.isoformat(),
            'filled_at': filled_at.isoformat(),
            'technical_data': json.dumps(tech_data), # Store as JSON string to match CSV behavior
            'config_snapshot': json.dumps(conf_snap) # Store as JSON string to match CSV behavior
        }
        
        trades.append(trade)
        mongo.insert_trade(trade)

    logger.info(f"✅ Successfully inserted {len(trades)} dummy trades into MongoDB.")

if __name__ == "__main__":
    generate_dummy_data()
