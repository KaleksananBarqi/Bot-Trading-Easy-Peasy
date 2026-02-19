import ccxt.async_support as ccxt
from src.utils.helper import logger
import config

class PositionManager:
    """
    Manages active positions formatting and caching.
    Responsibilities:
    - Sync positions from exchange.
    - Maintain a cache of open positions.
    - Check for active positions.
    """
    def __init__(self, exchange):
        self.exchange = exchange
        self.cache = {}

    async def sync(self):
        """
        Fetch real-time positions from Exchange and update cache.
        Returns: Number of active positions.
        """
        try:
            positions = await self.exchange.fetch_positions()
            # Rebuild cache from scratch to remove closed positions
            new_cache = {}
            count = 0
            for pos in positions:
                amt = float(pos['contracts'])
                if amt > 0:
                    sym = pos['symbol'].replace(':USDT', '')
                    base = sym.split('/')[0]
                    new_cache[base] = {
                        'symbol': sym,
                        'contracts': amt,
                        'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                        'entryPrice': float(pos['entryPrice'])
                    }
                    count += 1
            
            self.cache = new_cache
            return count
        except Exception as e:
            logger.error(f"Sync Pos Error: {e}")
            return 0

    def get_position(self, base_currency):
        """Get position details by base currency (e.g. 'BTC')."""
        return self.cache.get(base_currency)
    
    def has_position(self, symbol):
        """Check if we have an active position for this symbol on exchange."""
        base = symbol.split('/')[0]
        return base in self.cache

    def get_open_positions_count_by_category(self, target_category):
        """Hitung jumlah posisi aktif di kategori tertentu"""
        count = 0
        cat_map = {c['symbol']: c['category'] for c in config.DAFTAR_KOIN}
        
        for base, pos in self.cache.items():
            sym = pos['symbol']
            cat = cat_map.get(sym, 'UNKNOWN')
            if cat == target_category:
                count += 1
        return count
