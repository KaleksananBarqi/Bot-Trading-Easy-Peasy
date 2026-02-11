
import os
import csv
import time
import pandas as pd
from datetime import datetime
from src.utils.helper import logger

class TradeJournal:
    def __init__(self, filepath=None):
        if filepath is None:
            # Absolute path relative to this file (src/modules/journal.py -> root -> streamlit/data)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.filepath = os.path.join(base_dir, 'streamlit', 'data', 'trade_history.csv')
        else:
            self.filepath = filepath
        self.headers = [
            'timestamp', 'symbol', 'side', 'type', 
            'entry_price', 'exit_price', 'size_usdt', 
            'pnl_usdt', 'pnl_percent', 'roi_percent',
            'fee', 'strategy_tag', 'result',
            'prompt', 'reason',
            'setup_at', 'filled_at'
        ]
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Memastikan file CSV ada beserta headernya."""
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        if not os.path.exists(self.filepath):
            try:
                with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.headers)
                logger.info(f"📂 Created new Trade Journal: {self.filepath}")
            except Exception as e:
                logger.error(f"❌ Failed to create Trade Journal CSV: {e}")

    def log_trade(self, data: dict):
        """
        Mencatat trade yang selesai ke CSV.
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
            if pnl_usdt > 0:
                result = 'WIN'
            elif pnl_usdt < 0:
                result = 'LOSS'
            else:
                result = 'BREAKEVEN'

            # 2. Prepare Row
            row = [
                data.get('timestamp', datetime.now().isoformat()), # timestamp (allow override)
                data.get('symbol', 'UNKNOWN'),      # symbol
                data.get('side', 'UNKNOWN'),        # side
                data.get('type', 'UNKNOWN'),        # type
                f"{float(data.get('entry_price', 0)):.8f}", # entry
                f"{float(data.get('exit_price', 0)):.8f}",  # exit
                f"{size_usdt:.2f}",                 # size
                f"{pnl_usdt:.4f}",                  # pnl_usdt
                f"{pnl_percent:.2f}",               # pnl_%
                f"{roi_percent:.2f}",               # roi_%
                f"{float(data.get('fee', 0)):.4f}", # fee
                data.get('strategy_tag', 'MANUAL'), # strategy
                result,                             # result
                data.get('prompt', '-').replace('\n', ' '), # prompt (oneline)
                data.get('reason', '-').replace('\n', ' '), # reason (oneline)
                data.get('setup_at', ''),                   # setup_at (timestamp/iso)
                data.get('filled_at', '')                   # filled_at (timestamp/iso)
            ]

            # 3. Append to CSV
            with open(self.filepath, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
            logger.info(f"📝 Trade Logged: {data.get('symbol')} ({result}) PnL: ${pnl_usdt:.2f}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to log trade to journal: {e}")
            return False

    def load_trades(self):
        """Memuat riwayat trade sebagai DataFrame."""
        try:
            if not os.path.exists(self.filepath):
                return pd.DataFrame(columns=self.headers)
            
            df = pd.read_csv(self.filepath)
            
            # Convert timestamp to datetime object
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
            return df
        except Exception as e:
            logger.error(f"❌ Error loading trade history: {e}")
            return pd.DataFrame()
