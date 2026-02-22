"""
Script migrasi untuk mengisi field `exit_type` pada trade lama di MongoDB.

Logika:
- PnL > 0 -> TAKE_PROFIT
- PnL < 0 -> STOP_LOSS
- PnL == 0 -> BREAKEVEN

Hanya mengupdate dokumen yang BELUM punya field `exit_type` atau nilainya `UNKNOWN`.

Usage:
    python scripts/migrate_exit_type.py
    python scripts/migrate_exit_type.py --dry-run   # Preview tanpa mengubah data
"""

import sys
import os

# Setup path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import config
from src.modules.mongo_manager import MongoManager


def migrate_exit_type(dry_run=False):
    """Migrasi field exit_type untuk trade lama."""
    mongo = MongoManager()
    
    # Cari dokumen yang belum punya exit_type atau exit_type = UNKNOWN
    query = {
        '$or': [
            {'exit_type': {'$exists': False}},
            {'exit_type': 'UNKNOWN'},
            {'exit_type': None},
        ]
    }
    
    trades = list(mongo.trades_collection.find(query))
    total = len(trades)
    
    if total == 0:
        print("✅ Tidak ada trade yang perlu dimigrasi. Semua sudah punya exit_type.")
        return
    
    print(f"📋 Ditemukan {total} trade yang perlu dimigrasi.")
    
    updated = 0
    skipped = 0
    
    for trade in trades:
        pnl = float(trade.get('pnl_usdt', 0))
        result = trade.get('result', '')
        
        # Tentukan exit_type berdasarkan data yang ada
        if result in ['CANCELLED', 'TIMEOUT', 'EXPIRED']:
            exit_type = result 
        elif pnl > 0:
            exit_type = 'TAKE_PROFIT'
        elif pnl < 0:
            exit_type = 'STOP_LOSS'
        else:
            exit_type = 'BREAKEVEN'
        
        symbol = trade.get('symbol', '?')
        ts = trade.get('timestamp', '?')
        
        if dry_run:
            print(f"  [DRY-RUN] {ts} | {symbol} | PnL: ${pnl:.2f} | -> {exit_type}")
        else:
            # Update dokumen
            update_fields = {
                'exit_type': exit_type,
                'trailing_was_active': trade.get('trailing_was_active', False),
                'trailing_sl_final': float(trade.get('trailing_sl_final', 0)),
                'trailing_high': float(trade.get('trailing_high', 0)),
                'trailing_low': float(trade.get('trailing_low', 0)),
                'activation_price': float(trade.get('activation_price', 0)),
                'sl_price_initial': float(trade.get('sl_price_initial', 0)),
            }
            
            mongo.trades_collection.update_one(
                {'_id': trade['_id']},
                {'$set': update_fields}
            )
            print(f"  ✅ {ts} | {symbol} | PnL: ${pnl:.2f} | -> {exit_type}")
        
        updated += 1
    
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"\n{mode}Migrasi selesai: {updated} trade diperbarui, {skipped} di-skip.")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("🔍 Mode DRY-RUN: Tidak ada perubahan yang akan disimpan.\n")
    else:
        print("🚀 Mode LIVE: Data akan diperbarui di MongoDB.\n")
    
    migrate_exit_type(dry_run=dry_run)
