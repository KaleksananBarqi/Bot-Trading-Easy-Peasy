
import pandas as pd
from datetime import datetime
import json
from src.utils.helper import logger
from src.modules.mongo_manager import MongoManager

class TradeJournal:
    def __init__(self):
        # Initialize MongoManager
        self.mongo = MongoManager()
        
    def log_trade(self, data: dict):
        """
        Mencatat trade yang selesai ke MongoDB.
        Expected data keys: symbol, side, type, entry_price, exit_price, 
                          size_usdt, pnl_usdt, strategy_tag, prompt, reason
        """
        try:
            # 1. Hitung Derived Metrics
            pnl_usdt = float(data.get('pnl_usdt', 0))
            size_usdt = float(data.get('size_usdt', 0))
            
            # PnL % based on Size (Not Margin) - Net Movement
            pnl_percent = (pnl_usdt / size_usdt * 100) if size_usdt > 0 else 0
            
            # ROI % (Data biasanya sudah dikirim, kalau tidak hitung manual)
            roi_percent = float(data.get('roi_percent', 0))
            
            # Result Label
            result = data.get('result', None)
            
            if result is None:
                # Auto-detect if not provided
                if pnl_usdt > 0:
                    result = 'WIN'
                elif pnl_usdt < 0:
                    result = 'LOSS'
                else:
                    result = 'BREAKEVEN'
            
            # Special handling for non-filled trades
            if result in ['CANCELLED', 'TIMEOUT', 'EXPIRED']:
                pnl_usdt = 0.0
                pnl_percent = 0.0
                roi_percent = 0.0
                size_usdt = 0.0
                # Entry price is still relevant (the setup price)


            # 2. Serialize Technical & Config Data (JSON String for compatibility)
            # MongoDB can store dicts directly, but to maintain compatibility with existing Streamlit
            # that expects JSON strings in these columns, we will stringify them.
            # Alternatively, we could store as dict and convert in load_trades. 
            # Let's stringify here to match CSV behavior exactly for now.
            tech_data_raw = data.get('technical_data', {})
            config_snap_raw = data.get('config_snapshot', {})
            
            try:
                tech_json = json.dumps(tech_data_raw, ensure_ascii=False) if isinstance(tech_data_raw, dict) else tech_data_raw
            except (TypeError, ValueError):
                tech_json = '{}'
            
            try:
                config_json = json.dumps(config_snap_raw, ensure_ascii=False) if isinstance(config_snap_raw, dict) else config_snap_raw
            except (TypeError, ValueError):
                config_json = '{}'

            # 3. Prepare Document
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            trade_doc = {
                'timestamp': timestamp,
                'symbol': data.get('symbol', 'UNKNOWN'),
                'side': data.get('side', 'UNKNOWN'),
                'type': data.get('type', 'UNKNOWN'),
                'entry_price': float(data.get('entry_price', 0)),
                'exit_price': float(data.get('exit_price', 0)),
                'size_usdt': float(size_usdt),
                'pnl_usdt': float(pnl_usdt),
                'pnl_percent': float(pnl_percent),
                'roi_percent': float(roi_percent),
                'fee': float(data.get('fee', 0)),
                'strategy_tag': data.get('strategy_tag', 'MANUAL'),
                'result': result,
                'prompt': data.get('prompt', '-').replace('\n', ' '),
                'reason': data.get('reason', '-').replace('\n', ' '),
                'setup_at': data.get('setup_at', ''),
                'filled_at': data.get('filled_at', ''),
                'technical_data': tech_json,
                'config_snapshot': config_json
            }

            # 3. Insert to MongoDB
            success = self.mongo.insert_trade(trade_doc)
            
            if success:
                logger.info(f"📝 Trade Logged to MongoDB: {trade_doc.get('symbol')} ({result}) PnL: ${pnl_usdt:.2f}")
                return True
            else:
                logger.error("❌ Failed to insert trade to MongoDB")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to log trade to journal: {e}")
            return False

    def load_trades(self, limit=1000):
        """Memuat riwayat trade sebagai DataFrame dari MongoDB."""
        try:
            # Fetch from MongoDB
            trades = self.mongo.get_trades(limit=limit)
            
            if not trades:
                # Return empty DataFrame with expected columns if no data
                return pd.DataFrame(columns=[
                    'timestamp', 'symbol', 'side', 'type', 
                    'entry_price', 'exit_price', 'size_usdt', 
                    'pnl_usdt', 'pnl_percent', 'roi_percent',
                    'fee', 'strategy_tag', 'result',
                    'prompt', 'reason',
                    'setup_at', 'filled_at',
                    'technical_data', 'config_snapshot'
                ])
            
            # Convert to DataFrame
            df = pd.DataFrame(trades)
            
            # Drop MongoDB ID
            if '_id' in df.columns:
                df = df.drop(columns=['_id'])
            
            # Convert timestamp to datetime object
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
            return df
        except Exception as e:
            logger.error(f"❌ Error loading trade history from MongoDB: {e}")
            return pd.DataFrame()
