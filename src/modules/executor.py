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

    # --- PROPERTIES ---
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
    
    # --- RISK METHODS ---
    async def get_available_balance(self):
        return await self.risk.get_available_balance()
    
    async def calculate_dynamic_amount_usdt(self, symbol, leverage):
        return await self.risk.calculate_dynamic_amount_usdt(symbol, leverage)
    
    def set_cooldown(self, symbol, duration_seconds):
        self.risk.set_cooldown(symbol, duration_seconds)
    
    def is_under_cooldown(self, symbol):
        return self.risk.is_under_cooldown(symbol)

    def has_active_or_pending_trade(self, symbol):
        """
        Cek apakah simbol ini 'bersih' atau sedang ada trade (Active / Pending).
        Re-implemented facade logic combining Position and Tracker.
        """
        # 1. Cek Position Cache
        if self.positions.has_position(symbol):
            return True

        # 2. Cek Tracker (Pending Orders)
        tracker_data = self.tracker.get(symbol)
        if tracker_data:
            status = tracker_data.get('status', 'NONE')
            if status in ['WAITING_ENTRY', 'PENDING']:
                return True
        
        return False

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
        # Exposed if needed, but primarily internal to safety
        return await self.safety._amend_sl_order(symbol, new_sl, side)

    async def install_native_trailing_stop(self, symbol, side, quantity, callback_rate):
        return await self.safety.install_native_trailing_stop(symbol, side, quantity, callback_rate)

    # --- PENDING ORDERS SYNC (Was in Executor, now delegated/re-implemented here) ---
    async def sync_pending_orders(self):
        """
        Sync open orders to detect manual cancellations.
        Only checks symbols that are in 'WAITING_ENTRY' status.
        """
        # Logic originally in executor.py. 
        # Since it's complex and touches Exchange + Tracker, we can implement it here or in Orders/Tracker.
        # Implemented here to orchestrate.

        # 1. Identify symbols to check
        symbols_to_check = [
            sym for sym, data in self.tracker.data.items()
            if data.get('status') == 'WAITING_ENTRY'
        ]
        
        if not symbols_to_check:
            return

        # 2. Check symbols in parallel
        sem = asyncio.Semaphore(getattr(config, 'CONCURRENCY_LIMIT', 10))
        
        # Run all checks and collect results
        results = await asyncio.gather(*[
            self._check_symbol(sym, sem) for sym in symbols_to_check
        ])
        
        # 3. Save tracker if any changes were made
        if any(results):
            await self.tracker.save()

    async def _check_symbol(self, symbol: str, sem: asyncio.Semaphore) -> bool:
        """
        Check status of a single symbol's pending order.
        Returns True if tracker was modified, False otherwise.
        """
        async with sem:
            try:
                # Fetch Open Orders from Binance
                open_orders = await self.exchange.fetch_open_orders(symbol)
                open_order_ids = [str(o['id']) for o in open_orders]
                
                if not self.tracker.exists(symbol):
                    return False

                tracker_data = self.tracker.get(symbol)
                tracked_id = str(tracker_data.get('entry_id', ''))
                
                # [NEW] Check Expiry Time First
                current_time = time.time()
                expires_at = tracker_data.get('expires_at', float('inf'))

                if current_time > expires_at:
                    # Order expired -> Cancel & Cleanup
                    logger.info(f"⏰ Limit Order {symbol} expired after timeout. Cancelling...")
                    try:
                        await self.exchange.cancel_order(tracked_id, symbol)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to cancel expired order {symbol} (might be already gone): {e}")

                    # Clean tracker
                    self.tracker.delete(symbol)
                    
                    await kirim_tele(
                        f"⏰ <b>ORDER EXPIRED</b>\n"
                        f"Limit Order {symbol} dibatalkan karena timeout > 2 jam.\n"
                        f"Tracker cleaned."
                    )
                    return True  # Skip further checks since we removed it
                
                if tracked_id not in open_order_ids:
                    # Order is missing! Either Filled or Cancelled.
                    
                    # Case A: Filled? (Check Position Cache)
                    # We need to rely on PositionManager, but it might not be synced yet if we run this concurrently.
                    # Best effort: check cache first.
                    if self.positions.has_position(symbol):
                        # It is filled! Update tracker.
                        logger.info(f"✅ Order {symbol} found filled during sync. Queuing for Safety Orders (PENDING).")
                        self.tracker.update(symbol, {
                            'status': 'PENDING',
                            'last_check': time.time()
                        })
                        return True
                    
                    # Case B: Cancelled/Expired?
                    else:
                        # Not active, not in open orders -> Cancelled manually
                        logger.info(f"🗑️ Found Stale/Cancelled Order for {symbol}. Removing from tracker.")
                        self.tracker.delete(symbol)

                        await kirim_tele(
                            f"🗑️ <b>ORDER SYNC</b>\n"
                            f"Order for {symbol} was cancelled manually/expired.\n"
                            f"Tracker cleaned."
                        )
                        return True

                return False

            except Exception as e:
                logger.error(f"⚠️ Sync Pending Error for {symbol}: {e}")
                return False
