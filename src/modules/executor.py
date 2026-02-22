import asyncio
import time
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele

# IMPORTS FROM IMPLEMENTATION MODULES
from src.modules.executor_impl.tracker import TradeTracker
from src.modules.executor_impl.positions import PositionManager
from src.modules.executor_impl.risk import RiskManager
from src.modules.executor_impl.safety import SafetyManager
from src.modules.executor_impl.orders import OrderManager
from src.modules.executor_impl.sync import OrderSyncManager

class OrderExecutor:
    """
    FACADE class for Execution Module.
    Delegates functionality to specialized sub-components.
    Maintains backward compatibility with src/main.py.
    """
    def __init__(self, exchange):
        self.exchange = exchange
        
        # Initialize Components
        self.tracker = TradeTracker()
        self.positions = PositionManager(exchange)
        self.risk = RiskManager(exchange, self.positions)
        self.safety = SafetyManager(exchange, self.tracker)
        self.orders = OrderManager(exchange, self.tracker, self.risk)
        self.sync = OrderSyncManager(exchange, self.tracker, self.positions)

    # --- PROPERTIES (Backward Compatibility) ---
    @property
    def safety_orders_tracker(self):
        """Expose tracker data directly for backward compatibility"""
        return self.tracker.data
    
    @safety_orders_tracker.setter
    def safety_orders_tracker(self, value):
        self.tracker.data = value

    @property
    def position_cache(self):
        return self.positions.cache
    
    @position_cache.setter
    def position_cache(self, value):
        self.positions.cache = value

    @property
    def symbol_cooldown(self):
        return self.risk.symbol_cooldown

    @property
    def _trailing_last_update(self):
        """Expose SafetyManager's trailing throttle state for backward compatibility"""
        return self.safety._trailing_last_update

    # --- TRACKER METHODS ---
    def load_tracker(self):
        self.tracker.load()

    async def save_tracker(self):
        await self.tracker.save()

    async def remove_from_tracker(self, symbol):
        self.tracker.delete(symbol)
        await self.tracker.save()
        logger.info(f"🗑️ Tracker cleaned for {symbol}")

    # --- POSITION METHODS ---
    async def sync_positions(self):
        return await self.positions.sync()

    def get_open_positions_count_by_category(self, target_category):
        return self.positions.get_open_positions_count_by_category(target_category)
    
    def has_active_or_pending_trade(self, symbol):
        """
        Cek apakah simbol ini 'bersih' atau sedang ada trade (Active / Pending).
        Delegates to PositionManager with tracker injection.
        """
        return self.positions.has_active_or_pending_trade(symbol, self.tracker)

    # --- RISK METHODS ---
    async def get_available_balance(self):
        return await self.risk.get_available_balance()
    
    async def calculate_dynamic_amount_usdt(self, symbol, leverage):
        return await self.risk.calculate_dynamic_amount_usdt(symbol, leverage)
    
    def set_cooldown(self, symbol, duration_seconds):
        self.risk.set_cooldown(symbol, duration_seconds)
    
    def is_under_cooldown(self, symbol):
        return self.risk.is_under_cooldown(symbol)

    # --- EXECUTION METHODS ---
    async def execute_entry(self, *args, **kwargs):
        return await self.orders.execute_entry(*args, **kwargs)

    # --- SAFETY METHODS ---
    async def install_safety_orders(self, symbol, pos_data):
        return await self.safety.install_safety_orders(symbol, pos_data)

    async def check_trailing_on_price(self, symbol, current_price):
        return await self.safety.check_trailing_on_price(symbol, current_price)
    
    async def activate_trailing_mode(self, symbol, current_price):
        return await self.safety.activate_trailing_mode(symbol, current_price)

    async def update_trailing_sl(self, symbol, current_price):
        return await self.safety.update_trailing_sl(symbol, current_price)

    async def _amend_sl_order(self, symbol, new_sl, side):
        return await self.safety._amend_sl_order(symbol, new_sl, side)

    async def install_native_trailing_stop(self, symbol, side, quantity, callback_rate, activation_price=None):
        return await self.safety.install_native_trailing_stop(symbol, side, quantity, callback_rate, activation_price)

    # --- SYNC METHODS ---
    async def sync_pending_orders(self):
        """Delegates to OrderSyncManager."""
        return await self.sync.sync_pending_orders()
