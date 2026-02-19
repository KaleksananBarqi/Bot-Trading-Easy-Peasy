import time
import config
from src.utils.helper import logger

class RiskManager:
    """
    Manages risk calculations, position sizing, and cooldowns.
    Responsibilities:
    - Calculation of dynamic trade size.
    - Symbol cooldown management.
    """
    def __init__(self, exchange, position_manager):
        self.exchange = exchange
        self.positions = position_manager
        self.symbol_cooldown = {}

    async def get_available_balance(self):
        """Fetch USDT Available Balance"""
        try:
            bal = await self.exchange.fetch_balance()
            return float(bal['USDT']['free'])
        except Exception as e:
            logger.error(f"❌ Failed fetch balance: {e}")
            return 0.0

    async def calculate_dynamic_amount_usdt(self, symbol, leverage):
        """
        Hitung entry size berdasarkan % Risk dari Saldo Available.
        Return: Amount dalam USDT.
        """
        if not config.USE_DYNAMIC_SIZE:
            return None # Use Default / Manual
        
        balance = await self.get_available_balance()
        if balance <= 0: return None
        
        # Rumus: Pakai sekian % dari saldo
        risk_amount = balance * (config.RISK_PERCENT_PER_TRADE / 100)
        
        # Cek minimum
        if risk_amount < config.MIN_ORDER_USDT:
            return config.MIN_ORDER_USDT
            
        return risk_amount

    def set_cooldown(self, symbol, duration_seconds):
        """Set cooldown for a symbol"""
        end_time = time.time() + duration_seconds
        self.symbol_cooldown[symbol] = end_time
        logger.info(f"❄️ Cooldown set for {symbol} until {time.strftime('%H:%M:%S', time.localtime(end_time))} ({duration_seconds}s)")

    def is_under_cooldown(self, symbol):
        """Check if symbol is under cooldown"""
        if symbol in self.symbol_cooldown:
            if time.time() < self.symbol_cooldown[symbol]:
                return True
            else:
                del self.symbol_cooldown[symbol] # Cleanup
        return False
        
    def get_remaining_cooldown(self, symbol):
         if symbol in self.symbol_cooldown:
            return int(self.symbol_cooldown[symbol] - time.time())
         return 0
