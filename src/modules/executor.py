import asyncio
import time
import json
import os
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele

class OrderExecutor:
    def __init__(self, exchange):
        self.exchange = exchange
        self.safety_orders_tracker = {}
        self.position_cache = {}
        self.symbol_cooldown = {}
        self._safety_lock = asyncio.Lock()  # Prevent race condition on safety orders
        self._trailing_last_update = {} # [NEW] Throttle for Trailing SL Update to Exchange
        self.load_tracker()

    # --- TRACKER MANAGEMENT ---
    def load_tracker(self):
        if os.path.exists(config.TRACKER_FILENAME):
            try:
                with open(config.TRACKER_FILENAME, 'r') as f:
                    self.safety_orders_tracker = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tracker: {e}")
                self.safety_orders_tracker = {}
        else:
            self.safety_orders_tracker = {}

    # --- [NEW] REALTIME TRAILING CHECK (CALLED BY WEBSOCKET) ---
    async def check_trailing_on_price(self, symbol, current_price):
        """
        Dipanggil setiap ada update harga dari WebSocket (Realtime).
        Menggunakan throttling agar tidak spam API saat update order.
        """
        if symbol not in self.safety_orders_tracker:
            return
            
        tracker = self.safety_orders_tracker[symbol]
        if tracker['status'] != 'SECURED':
            return
            
        # 1. Cek Aktivasi (Jika belum aktif)
        if not tracker.get('trailing_active', False):
            await self.activate_trailing_mode(symbol, current_price)
            return

        # 2. Update Trailing SL
        # Logic Throttling dipindah ke dalam update_trailing_sl agar high/low tetap terupdate realtime.
        await self.update_trailing_sl(symbol, current_price)

    async def save_tracker(self):
        """Non-blocking save tracker ke file."""
        try:
            await asyncio.to_thread(self._save_tracker_sync)
        except Exception as e:
            logger.error(f"⚠️ Gagal save tracker: {e}")

    def _save_tracker_sync(self):
        """Sync helper untuk save tracker (dijalankan di thread pool)."""
        with open(config.TRACKER_FILENAME, 'w') as f:
            json.dump(self.safety_orders_tracker, f, indent=2, sort_keys=True)

    # --- RISK & SIZING HELPERS ---
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

    def get_open_positions_count_by_category(self, target_category):
        """Hitung jumlah posisi aktif di kategori tertentu"""
        count = 0
        cat_map = {c['symbol']: c['category'] for c in config.DAFTAR_KOIN}
        
        for base, pos in self.position_cache.items():
            sym = pos['symbol']
            cat = cat_map.get(sym, 'UNKNOWN')
            if cat == target_category:
                count += 1
        return count

    def has_active_or_pending_trade(self, symbol):
        """
        Cek apakah simbol ini 'bersih' atau sedang ada trade (Active / Pending).
        Return True jika ADA trade (harus di-skip).
        """
        # 1. Cek Position Cache (Real Active Data)
        base = symbol.split('/')[0]
        if base in self.position_cache:
            return True

        # 2. Cek Tracker (Pending Orders: WAITING_ENTRY / PENDING)
        if symbol in self.safety_orders_tracker:
            status = self.safety_orders_tracker[symbol].get('status', 'NONE')
            if status in ['WAITING_ENTRY', 'PENDING']:
                return True
        
        return False

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

    # --- EXECUTION LOGIC ---
    async def execute_entry(self, symbol, side, order_type, price, amount_usdt, leverage, strategy_tag, atr_value=0):
        """
        Eksekusi open posisi (Market/Limit).
        """
        # 1. Cek Cooldown
        if self.is_under_cooldown(symbol):
            remaining = int(self.symbol_cooldown[symbol] - time.time())
            logger.info(f"🛑 {symbol} is in Cooldown ({remaining}s remaining). Skip Entry.")
            return

        try:
            # 2. Set Leverage & Margin
            try:
                await self.exchange.set_leverage(leverage, symbol)
                await self.exchange.set_margin_mode(config.DEFAULT_MARGIN_TYPE, symbol)
            except ccxt.BaseError as e:
                err_msg = str(e).lower()
                if "already set" not in err_msg and "no need to change" not in err_msg:
                    logger.warning(f"⚠️ Leverage/Margin setup skipped for {symbol}: {e}")

            # 3. Hitung Qty
            if price is None or price == 0:
                ticker = await self.exchange.fetch_ticker(symbol)
                price_exec = ticker['last']
            else:
                price_exec = price

            qty = (amount_usdt * leverage) / price_exec
            qty = self.exchange.amount_to_precision(symbol, qty)

            logger.info(f"🚀 EXECUTING: {symbol} | {side} | ${amount_usdt} | x{leverage} | ATR: {atr_value}")

            # 4. Create Order
            if order_type.lower() == 'limit':
                order = await self.exchange.create_order(symbol, 'limit', side, qty, price_exec)
                # Save to tracker as WAITING_ENTRY
                self.safety_orders_tracker[symbol] = {
                    "status": "WAITING_ENTRY",
                    "entry_id": str(order['id']),
                    "created_at": time.time(),
                    "expires_at": time.time() + config.LIMIT_ORDER_EXPIRY_SECONDS,
                    "strategy": strategy_tag,
                    "atr_value": atr_value # Save ATR for Safety Calculation
                }
                await self.save_tracker()
                await kirim_tele(f"⏳ <b>LIMIT PLACED ({strategy_tag})</b>\n{symbol} {side} @ {price_exec:.4f}\n(Trap SL set by ATR: {atr_value:.4f})")

            else: # MARKET
                # [FIX RACE CONDITION]
                # Simpan metadata SEBELUM order dilempar supaya Safety Monitor
                # langsung punya data ATR saat mendeteksi posisi baru.
                self.safety_orders_tracker[symbol] = {
                    "status": "PENDING", 
                    "strategy": strategy_tag,
                    "atr_value": atr_value,
                    "created_at": time.time()
                }
                await self.save_tracker()

                try:
                    order = await self.exchange.create_order(symbol, 'market', side, qty)
                    await kirim_tele(f"✅ <b>MARKET FILLED</b>\n{symbol} {side} (Size: ${amount_usdt*leverage:.2f})")
                except Exception as e:
                    # [ROLLBACK] Jika order gagal, hapus dari tracker
                    logger.error(f"❌ Market Order Failed {symbol}, rolling back tracker...")
                    if symbol in self.safety_orders_tracker:
                        del self.safety_orders_tracker[symbol]
                        await self.save_tracker()
                    raise e

        except Exception as e:
            logger.error(f"❌ Entry Failed {symbol}: {e}")
            await kirim_tele(f"❌ <b>ENTRY ERROR</b>\n{symbol}: {e}", alert=True)

    # --- SAFETY ORDERS (SL/TP) ---
    async def install_safety_orders(self, symbol, pos_data):
        """
        Pasang SL dan TP untuk posisi yang sudah terbuka.
        """
        async with self._safety_lock:  # Prevent race condition
            entry_price = float(pos_data['entryPrice'])
            quantity = float(pos_data['contracts'])
            side = pos_data['side']
            
            # 1. Cancel Old Orders
            try:
                await self.exchange.fapiPrivateDeleteAllOpenOrders({'symbol': symbol.replace('/', '')})
            except ccxt.BaseError as e:
                logger.debug(f"Cancel old orders for {symbol}: {e}")
            
            # 2. Hitung Jarak SL/TP
            # Cek apakah kita punya data ATR dari tracker (saat entry)
            tracker_data = self.safety_orders_tracker.get(symbol, {})
            atr_val = tracker_data.get('atr_value', 0)
            
            sl_price = 0
            tp_price = 0
            
            if atr_val > 0:
                # --- DYNAMIC ATR LOGIC (LIQUIDITY HUNT / TREND TRAP) ---
                # SL = Configured ATR (TRAP_SAFETY_SL)
                # TP = Configured ATR (ATR_MULTIPLIER_TP1)
                dist_sl = atr_val * config.TRAP_SAFETY_SL
                dist_tp = atr_val * config.ATR_MULTIPLIER_TP1
                
                if side == "LONG":
                    sl_price = entry_price - dist_sl
                    tp_price = entry_price + dist_tp
                else:
                    sl_price = entry_price + dist_sl
                    tp_price = entry_price - dist_tp
                    
                logger.info(f"🛡️ Safety Calc (ATR {atr_val}): SL dist {dist_sl}, TP dist {dist_tp}")
            
            else:
                # --- FALLBACK PERCENTAGE ---
                sl_percent = config.DEFAULT_SL_PERCENT
                tp_percent = config.DEFAULT_TP_PERCENT
                
                if side == "LONG":
                    sl_price = entry_price * (1 - sl_percent)
                    tp_price = entry_price * (1 + tp_percent)
                else:
                    sl_price = entry_price * (1 + sl_percent)
                    tp_price = entry_price * (1 - tp_percent)
            
            if side == "LONG": side_api = 'sell'
            else: side_api = 'buy'

            p_sl = self.exchange.price_to_precision(symbol, sl_price)
            p_tp = self.exchange.price_to_precision(symbol, tp_price)

            try:
                # A. STOP LOSS (STOP_MARKET)
                await self.exchange.create_order(symbol, 'STOP_MARKET', side_api, None, None, {
                    'stopPrice': p_sl, 'closePosition': True, 'workingType': 'MARK_PRICE'
                })
                # B. TAKE PROFIT (TAKE_PROFIT_MARKET)
                await self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side_api, None, None, {
                    'stopPrice': p_tp, 'closePosition': True, 'workingType': 'CONTRACT_PRICE'
                })
                
                logger.info(f"✅ Safety Orders Installed: {symbol} | SL {p_sl} | TP {p_tp}")

                # [UPDATE] Save TP/SL info to tracker for Trailing Logic
                if symbol in self.safety_orders_tracker:
                    self.safety_orders_tracker[symbol].update({
                        "status": "SECURED", # Ensure status is updated
                        "entry_price": entry_price,
                        "tp_price": tp_price,
                        "sl_price_initial": sl_price,
                        "side": side, # LONG/SHORT
                        "trailing_active": False 
                    })
                    await self.save_tracker()

                return True
            except Exception as e:
                logger.error(f"❌ Install Safety Failed {symbol}: {e}")
                return False

    # --- TRAILING STOP LOSS LOGIC ---
    def calculate_tp_progress(self, symbol, current_price):
        """
        Hitung progress harga menuju TP (0.0 - 1.0).
        Return: float (e.g., 0.8 for 80%)
        """
        tracker = self.safety_orders_tracker.get(symbol)
        if not tracker or 'entry_price' not in tracker or 'tp_price' not in tracker:
            return 0.0
            
        entry = tracker['entry_price']
        tp = tracker['tp_price']
        side = tracker.get('side', 'LONG')
        
        if side == 'LONG':
            total_dist = tp - entry
            if total_dist <= 0: return 0.0
            current_dist = current_price - entry
            progress = current_dist / total_dist
        else: # SHORT
            total_dist = entry - tp
            if total_dist <= 0: return 0.0
            current_dist = entry - current_price
            progress = current_dist / total_dist
            
        return progress

    async def activate_trailing_mode(self, symbol, current_price):
        """
        Aktifkan mode trailing stop. 
        Set initial Trailing SL based on callback rate & min profit lock.
        """
        tracker = self.safety_orders_tracker.get(symbol)
        if not tracker: return

        entry = tracker['entry_price']
        side = tracker.get('side', 'LONG')
        
        # 1. Hitung SL Baru (Trailing)
        new_sl = 0
        
        if side == 'LONG':
            # Base Callback SL: High (Current) - Callback%
            callback_sl = current_price * (1 - config.TRAILING_CALLBACK_RATE)
            # Min Profit Lock: Entry + MinProfit%
            min_profit_sl = entry * (1 + config.TRAILING_MIN_PROFIT_LOCK)
            
            # Kita ambil yang LEBIH TINGGI (Lebih aman/ketat)
            new_sl = max(callback_sl, min_profit_sl)
            
            # Init High/Low tracks
            tracker['trailing_high'] = current_price
            
        else: # SHORT
            # Base Callback SL: Low (Current) + Callback%
            callback_sl = current_price * (1 + config.TRAILING_CALLBACK_RATE)
            # Min Profit Lock: Entry - MinProfit%
            min_profit_sl = entry * (1 - config.TRAILING_MIN_PROFIT_LOCK)
            
            # Kita ambil yang LEBIH RENDAH (Lebih aman/ketat untuk short)
            new_sl = min(callback_sl, min_profit_sl)
            
            tracker['trailing_low'] = current_price

        # 2. Update Tracker
        tracker['trailing_active'] = True
        tracker['trailing_sl'] = new_sl
        await self.save_tracker()
        
        logger.info(f"🔄 Trailing Mode ACTIVATED for {symbol} @ {current_price} | SL: {new_sl:.4f}")
        await kirim_tele(f"🔄 <b>TRAILING ACTIVE</b>\n{symbol}\nPrice: {current_price}\nInitial SL: {new_sl:.4f} (Locked)")
        
        # 3. Apply to Exchange
        await self._amend_sl_order(symbol, new_sl, side)

    async def update_trailing_sl(self, symbol, current_price):
        """
        Cek apakah harga membuat High/Low baru, jika ya, geser SL.
        Optimized: Update Internal High/Low Always -> Throttle API/Save.
        """
        tracker = self.safety_orders_tracker.get(symbol)
        if not tracker or not tracker.get('trailing_active'): return

        side = tracker.get('side', 'LONG')
        current_sl = tracker.get('trailing_sl', 0)
        
        need_update = False
        new_sl = current_sl
        
        # 1. Update Internal High/Low & Calculate Candidate SL
        if side == 'LONG':
            trailing_high = tracker.get('trailing_high', 0)
            
            # A. Update High (ALWAYS Capture Peak)
            if current_price > trailing_high:
                tracker['trailing_high'] = current_price
                trailing_high = current_price # Update local var for calc below

            # B. Calculate New SL Candidate based on (possibly new) High
            candidate_sl = trailing_high * (1 - config.TRAILING_CALLBACK_RATE)

            # C. Check if we need to move SL UP
            if candidate_sl > current_sl:
                new_sl = candidate_sl
                need_update = True
                    
        else: # SHORT
            trailing_low = tracker.get('trailing_low', float('inf'))
            
            # A. Update Low (ALWAYS Capture Bottom)
            if current_price < trailing_low:
                tracker['trailing_low'] = current_price
                trailing_low = current_price
                
            # B. Calculate New SL Candidate
            candidate_sl = trailing_low * (1 + config.TRAILING_CALLBACK_RATE)

            # C. Check if we need to move SL DOWN
            if candidate_sl < current_sl:
                new_sl = candidate_sl
                need_update = True

        # 2. Execute Update (Throttled)
        if need_update:
            # Check Throttling
            now = time.time()
            last_update = self._trailing_last_update.get(symbol, 0)

            if now - last_update < config.TRAILING_SL_UPDATE_COOLDOWN:
                # Still in cooldown, skip Saving & API call.
                return False

            # Passed Cooldown -> Execute
            tracker['trailing_sl'] = new_sl
            self._trailing_last_update[symbol] = now

            # Save Logic (Heavy I/O)
            await self.save_tracker()
            
            logger.info(f"📈 Trailing SL Updated {symbol}: {current_sl:.4f} -> {new_sl:.4f}")
            # Execute on Exchange (Heavy Network)
            await self._amend_sl_order(symbol, new_sl, side)
            return True

        return False

    async def _amend_sl_order(self, symbol, new_sl_price, side):
        """
        Helper: Cancel old SL and create new one (or use modifyOrder if supported, 
        but Cancel+Replace is safer/standard for simple bots).
        Note: Since we use STOP_MARKET with closePosition=True, we just need to update trigger price.
        """
        try:
             # Binance Futures allows cancelling generic orders. 
             # To be robust, let's Cancel All Open Orders for this symbol (TP is static, but SL moves).
             # Wait! If we cancel ALL, we lose the TP order too.
             # Ideally we should identify the SL order ID. But to keep it simple and robust:
             # We can just Cancel ALL and Re-Place TP + New SL. 
             # Or better: Fetch open orders, find STOP_MARKET, cancel it.
             
             orders = await self.exchange.fetch_open_orders(symbol)
             sl_order_id = None
             
             for o in orders:
                 if o['type'] == 'stop_market' or o['type'] == 'STOP_MARKET':
                     sl_order_id = o['id']
                     break
            
             if sl_order_id:
                 try:
                     await self.exchange.cancel_order(sl_order_id, symbol)
                 except Exception as e:
                     logger.warning(f"Failed to cancel old SL {sl_order_id}: {e}")

             # Place New SL
             p_sl = self.exchange.price_to_precision(symbol, new_sl_price)
             side_api = 'sell' if side == 'LONG' else 'buy'
             
             await self.exchange.create_order(symbol, 'STOP_MARKET', side_api, None, None, {
                    'stopPrice': p_sl, 'closePosition': True, 'workingType': 'MARK_PRICE'
             })
             
        except Exception as e:
            logger.error(f"❌ Failed to Amend SL {symbol}: {e}")

    async def remove_from_tracker(self, symbol):
        """Async remove symbol from safety tracker and save."""
        if symbol in self.safety_orders_tracker:
            del self.safety_orders_tracker[symbol]
            await self.save_tracker()
            logger.info(f"🗑️ Tracker cleaned for {symbol}")

    async def sync_positions(self):
        """Fetch real-time positions from Exchange"""
        try:
            positions = await self.exchange.fetch_positions()
            # [FIX] Rebuild cache from scratch to remove closed positions
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
            
            self.position_cache = new_cache
            return count
        except Exception as e:
            logger.error(f"Sync Pos Error: {e}")
            return 0
            
    async def sync_pending_orders(self):
        """
        [NEW] Sync open orders to detect manual cancellations.
        Only checks symbols that are in 'WAITING_ENTRY' status.
        """
        # 1. Identify symbols to check
        symbols_to_check = []
        for sym, data in self.safety_orders_tracker.items():
            if data.get('status') == 'WAITING_ENTRY':
                symbols_to_check.append(sym)
                
        if not symbols_to_check:
            return

        # 2. Check symbols in parallel
        sem = asyncio.Semaphore(getattr(config, 'CONCURRENCY_LIMIT', 10))
        changes_made = False

        async def check_symbol(symbol):
            nonlocal changes_made
            async with sem:
                try:
                    # Fetch Open Orders from Binance
                    open_orders = await self.exchange.fetch_open_orders(symbol)
                    open_order_ids = [str(o['id']) for o in open_orders]
                    
                    # Check if our tracked order exists
                    # (Re-check existence in case it was modified concurrently - rare but safe)
                    if symbol not in self.safety_orders_tracker:
                        return

                    tracker_data = self.safety_orders_tracker[symbol]
                    tracked_id = str(tracker_data.get('entry_id', ''))
                    
                    if tracked_id not in open_order_ids:
                        # Order is missing! Either Filled or Cancelled.
                        
                        # Case A: Filled? (Check Position Cache)
                        base = symbol.split('/')[0]
                        if base in self.position_cache:
                            # It is filled! Update tracker.
                            logger.info(f"✅ Order {symbol} found filled during sync. Queuing for Safety Orders (PENDING).")
                            self.safety_orders_tracker[symbol]['status'] = 'PENDING'
                            self.safety_orders_tracker[symbol]['last_check'] = time.time()
                            changes_made = True
                        
                        # Case B: Cancelled/Expired?
                        else:
                            # Not active, not in open orders -> Cancelled manually
                            logger.info(f"🗑️ Found Stale/Cancelled Order for {symbol}. Removing from tracker.")
                            if symbol in self.safety_orders_tracker:
                                del self.safety_orders_tracker[symbol]
                                changes_made = True

                            await kirim_tele(
                                f"🗑️ <b>ORDER SYNC</b>\n"
                                f"Order for {symbol} was cancelled manually/expired.\n"
                                f"Tracker cleaned."
                            )

                except Exception as e:
                    logger.error(f"⚠️ Sync Pending Error for {symbol}: {e}")

        # Run all checks
        await asyncio.gather(*[check_symbol(sym) for sym in symbols_to_check])

        # 3. Save only if needed
        if changes_made:
            await self.save_tracker()
