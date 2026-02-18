
import time
from datetime import datetime
from typing import Optional
import aiohttp
import config
from src.utils.helper import logger

class OnChainAnalyzer:
    def __init__(self):
        # Dict per-symbol: {"BTC/USDT": [...], "SOL/USDT": [...]}
        self.whale_transactions: dict[str, list[str]] = {}
        self.stablecoin_inflow = "Neutral"  # Neutral, Positive, Negative
        
        # De-duplication state per symbol
        self._last_whale_key: dict[str, str] = {}
        self._last_whale_time: dict[str, float] = {}
        self._dedup_window_seconds: int = 5  # Skip transaksi identik dalam 5 detik

    def detect_whale(self, symbol: str, size_usdt: float, side: str) -> None:
        """
        Called by WebSocket AggTrade or OrderUpdate to record big trades.
        Stores whale activity per-symbol for filtered retrieval.
        Includes de-duplication to prevent logging identical transactions.
        """
        if size_usdt >= config.WHALE_THRESHOLD_USDT:
            current_time = time.time()
            
            # De-duplication: Skip jika transaksi identik dalam window waktu (per-symbol)
            whale_key = f"{side}_{symbol}_{int(size_usdt)}"
            last_key = self._last_whale_key.get(symbol)
            last_time = self._last_whale_time.get(symbol, 0)
            
            if whale_key == last_key and (current_time - last_time) < self._dedup_window_seconds:
                logger.debug(f"🐋 Skipped duplicate whale: {whale_key}")
                return  # Skip duplicate
            
            # Update de-duplication state
            self._last_whale_key[symbol] = whale_key
            self._last_whale_time[symbol] = current_time
            
            # Format message dengan timestamp untuk clarity
            timestamp = datetime.now().strftime("%H:%M")
            msg = f"🐋 [{timestamp}] {side} {symbol} worth ${size_usdt:,.0f}"
            
            # Initialize list jika belum ada
            if symbol not in self.whale_transactions:
                self.whale_transactions[symbol] = []
            
            self.whale_transactions[symbol].append(msg)
            
            # Keep only last N transactions per symbol
            limit = getattr(config, 'WHALE_HISTORY_LIMIT', 10)
            if len(self.whale_transactions[symbol]) > limit:
                self.whale_transactions[symbol].pop(0)
            
            #logger.info(f"🐋 Whale detected: {msg}")



    async def fetch_stablecoin_inflows(self):
        try:
            url = config.DEFILLAMA_STABLECOIN_URL
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=config.API_REQUEST_TIMEOUT)) as resp:
                    data = await resp.json()
            
            if data and len(data) > 2:
                # Structure: [{'date': 1600..., 'totalCirculating': {'peggedUSD': 100...}}, ...]
                # Note: "totalCirculatingUSD" key represents aggregated mcap
                
                # Get last two records
                curr = data[-1]
                prev = data[-2]
                
                # Check for 'totalCirculatingUSD' key directly
                # It is a dict: {'peggedUSD': ..., 'peggedEUR': ...}
                curr_dict = curr.get('totalCirculatingUSD', {})
                prev_dict = prev.get('totalCirculatingUSD', {})
                
                curr_val = curr_dict.get('peggedUSD', 0)
                prev_val = prev_dict.get('peggedUSD', 0)
                
                if curr_val and prev_val:
                    change_pct = ((curr_val - prev_val) / prev_val) * 100
                    
                    if change_pct > config.STABLECOIN_INFLOW_THRESHOLD_PERCENT:
                        self.stablecoin_inflow = "Positive"
                    elif change_pct < -config.STABLECOIN_INFLOW_THRESHOLD_PERCENT:
                        self.stablecoin_inflow = "Negative"
                    else:
                        self.stablecoin_inflow = "Neutral"
                        
                    logger.info(f"🪙 Stablecoin Inflow: {self.stablecoin_inflow} ({change_pct:.2f}%)")
                else:
                    self.stablecoin_inflow = "Neutral"
            else:
                 logger.warning("CoinLlama Data Insufficient")
                 
        except Exception as e:
            logger.error(f"❌ Failed fetch Stablecoin Inflow: {e}")
            self.stablecoin_inflow = "Neutral" # Fallback

    def get_latest(self, symbol: Optional[str] = None) -> dict:
        """
        Get latest on-chain data.
        
        Args:
            symbol: Optional symbol to filter whale activity. 
                    If None, returns empty whale list (untuk global sentiment).
        
        Returns:
            dict with whale_activity (filtered) and stablecoin_inflow
        """
        whale_list = []
        
        if symbol and symbol in self.whale_transactions:
            whale_list = self.whale_transactions[symbol].copy()
        
        return {
            "whale_activity": whale_list,
            "stablecoin_inflow": self.stablecoin_inflow
        }

