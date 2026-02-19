import asyncio
import time
import config
from src.utils.helper import logger, kirim_tele


class OrderSyncManager:
    """
    Manages synchronization of pending orders with the exchange.
    Responsibilities:
    - Detect manually cancelled orders.
    - Auto-cancel expired limit orders.
    - Update tracker state accordingly.
    """
    def __init__(self, exchange, tracker, positions):
        self.exchange = exchange
        self.tracker = tracker
        self.positions = positions

    async def sync_pending_orders(self):
        """
        Sync open orders to detect manual cancellations.
        Only checks symbols that are in 'WAITING_ENTRY' status.
        """
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
