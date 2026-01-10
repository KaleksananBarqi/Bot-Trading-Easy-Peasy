
import asyncio
import time
import json
import os
import config
from src.utils.helper import logger, kirim_tele

class OrderExecutor:
    def __init__(self, exchange):
        self.exchange = exchange
        self.safety_orders_tracker = {}
        self.position_cache = {}
        self.symbol_cooldown = {}
        self.load_tracker()

    # --- TRACKER MANAGEMENT ---
    def load_tracker(self):
        if os.path.exists(config.TRACKER_FILENAME):
            try:
                with open(config.TRACKER_FILENAME, 'r') as f:
                    self.safety_orders_tracker = json.load(f)
                logger.info(f"📂 Tracker loaded: {len(self.safety_orders_tracker)} data.")
            except: self.safety_orders_tracker = {}
        else: self.safety_orders_tracker = {}

    def save_tracker(self):
        try:
            with open(config.TRACKER_FILENAME, 'w') as f:
                json.dump(self.safety_orders_tracker, f, indent=2, sort_keys=True)
        except Exception as e: logger.error(f"⚠️ Gagal save tracker: {e}")

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
        
        # Logika Tambahan: Kalau leverage gede, apakah size dikecilkan? 
        # Untuk sekarang kita anggap Risk Unit = Base Margin (Cost).
        # Jadi kalau Balance $1000, Risk 5% = $50.
        # Kita akan buka posisi dengan Initial Margin $50.
        # Total Position Size = $50 * Leverage.
        
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
            except: pass

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
                self.save_tracker()
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
                self.save_tracker()

                try:
                    order = await self.exchange.create_order(symbol, 'market', side, qty)
                    await kirim_tele(f"✅ <b>MARKET FILLED</b>\n{symbol} {side} (Size: ${amount_usdt*leverage:.2f})")
                except Exception as e:
                    # [ROLLBACK] Jika order gagal, hapus dari tracker
                    logger.error(f"❌ Market Order Failed {symbol}, rolling back tracker...")
                    if symbol in self.safety_orders_tracker:
                        del self.safety_orders_tracker[symbol]
                        self.save_tracker()
                    raise e

        except Exception as e:
            logger.error(f"❌ Entry Failed {symbol}: {e}")
            await kirim_tele(f"❌ <b>ENTRY ERROR</b>\n{symbol}: {e}", alert=True)

    # --- SAFETY ORDERS (SL/TP) ---
    async def install_safety_orders(self, symbol, pos_data):
        """
        Pasang SL dan TP untuk posisi yang sudah terbuka.
        """
        entry_price = float(pos_data['entryPrice'])
        quantity = float(pos_data['contracts'])
        side = pos_data['side']
        
        # 1. Cancel Old Orders
        try:
            await self.exchange.fapiPrivateDeleteAllOpenOrders({'symbol': symbol.replace('/', '')})
        except: pass
        
        # 2. Hitung Jarak SL/TP
        # Cek apakah kita punya data ATR dari tracker (saat entry)
        tracker_data = self.safety_orders_tracker.get(symbol, {})
        atr_val = tracker_data.get('atr_value', 0)
        
        sl_price = 0
        tp_price = 0
        
        if atr_val > 0:
            # --- DYNAMIC ATR LOGIC (LIQUIDITY HUNT / TREND TRAP) ---
            # SL = 1.0 ATR (TRAP_SAFETY_SL)
            # TP = 2.2 ATR (ATR_MULTIPLIER_TP1)
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
            return True
        except Exception as e:
            logger.error(f"❌ Install Safety Failed {symbol}: {e}")
            return False

    async def sync_positions(self):
        """Fetch real-time positions from Exchange"""
        try:
            positions = await self.exchange.fetch_positions()
            count = 0
            for pos in positions:
                amt = float(pos['contracts'])
                if amt > 0:
                    sym = pos['symbol']
                    base = sym.split('/')[0]
                    self.position_cache[base] = {
                        'symbol': sym,
                        'contracts': amt,
                        'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                        'entryPrice': float(pos['entryPrice'])
                    }
                    count += 1
            # Clean cache for closed positions
            # (Simplifikasi: di versi full kita bandingkan keys)
            return count
        except Exception as e:
            logger.error(f"Sync Pos Error: {e}")
            return 0
