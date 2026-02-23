import asyncio
import time
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele

class SafetyManager:
    """
    Manages Safety Orders (SL/TP) and Trailing Stop Logic.
    Responsibilities:
    - Install SL/TP.
    - Monitor realtime price for trailing stop.
    - Native Trailing Stop.
    """
    def __init__(self, exchange, tracker):
        self.exchange = exchange
        self.tracker = tracker
        self._safety_lock = asyncio.Lock()
        self._trailing_last_update = {} # Throttle for Trailing SL Update

    # --- SAFETY ORDERS (SL/TP) ---
    async def install_safety_orders(self, symbol, pos_data):
        """
        Pasang SL dan TP untuk posisi yang sudah terbuka.
        """
        async with self._safety_lock:  # Prevent race condition
            entry_price = float(pos_data['entryPrice'])
            side = pos_data['side']
            
            # 1. Cancel Old Orders
            try:
                await self.exchange.fapiPrivateDeleteAllOpenOrders({'symbol': symbol.replace('/', '')})
            except ccxt.BaseError as e:
                logger.debug(f"Cancel old orders for {symbol}: {e}")
            
            # 2. Hitung Jarak SL/TP
            # Cek apakah kita punya data ATR dari tracker (saat entry)
            tracker_data = self.tracker.get(symbol) or {}
            atr_val = tracker_data.get('atr_value', 0)
            
            sl_price = 0
            tp_price = 0
            
            if atr_val > 0:
                # --- DYNAMIC ATR LOGIC ---
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
                sl_order = await self.exchange.create_order(symbol, 'STOP_MARKET', side_api, None, None, {
                    'stopPrice': p_sl, 'closePosition': True, 'workingType': 'MARK_PRICE'
                })
                # B. TAKE PROFIT (TAKE_PROFIT_MARKET)
                tp_order = await self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side_api, None, None, {
                    'stopPrice': p_tp, 'closePosition': True, 'workingType': 'CONTRACT_PRICE'
                })
                
                logger.info(f"✅ Safety Orders Installed: {symbol} | SL {p_sl} | TP {p_tp}")

                # [UPDATE] Save TP/SL info to tracker
                if self.tracker.exists(symbol):
                    self.tracker.update(symbol, {
                        "status": "SECURED",
                        "entry_price": entry_price,
                        "tp_price": tp_price,
                        "sl_price_initial": sl_price,
                        "sl_order_id": str(sl_order['id']),
                        "tp_order_id": str(tp_order['id']),
                        "side": side,
                        "trailing_active": False 
                    })
                    await self.tracker.save()
                else:
                     # Create if not exists (e.g., manual position)
                    self.tracker.set(symbol, {
                        "status": "SECURED",
                        "entry_price": entry_price,
                        "tp_price": tp_price,
                        "sl_price_initial": sl_price,
                        "sl_order_id": str(sl_order['id']),
                        "tp_order_id": str(tp_order['id']),
                        "side": side,
                        "trailing_active": False,
                        "created_at": time.time()
                    })
                    await self.tracker.save()

                return True
            except Exception as e:
                logger.error(f"❌ Install Safety Failed {symbol}: {e}")
                return False

    # --- TRAILING STOP LOSS LOGIC ---
    async def check_trailing_on_price(self, symbol, current_price):
        """
        Dipanggil setiap ada update harga dari WebSocket.
        """
        tracker_data = self.tracker.get(symbol)
        if not tracker_data:
            return
            
        if tracker_data.get('status') != 'SECURED':
            return
            
        # 1. Cek Aktivasi
        if not tracker_data.get('trailing_active', False):
            await self.activate_trailing_mode(symbol, current_price)
            return

        # 2. Update Trailing SL
        await self.update_trailing_sl(symbol, current_price)

    async def activate_trailing_mode(self, symbol, current_price):
        tracker_data = self.tracker.get(symbol)
        if not tracker_data: return

        entry = tracker_data['entry_price']
        side = tracker_data.get('side', 'LONG')
        
        # 1. Hitung SL Baru (Trailing)
        new_sl = 0
        
        if side == 'LONG':
            # Base Callback SL: High (Current) - Callback%
            callback_sl = current_price * (1 - config.TRAILING_CALLBACK_RATE)
            # Min Profit Lock: Entry + MinProfit%
            min_profit_sl = entry * (1 + config.TRAILING_MIN_PROFIT_LOCK)
            
            new_sl = max(callback_sl, min_profit_sl)
            
            # Init High
            tracker_data['trailing_high'] = current_price
            
        else: # SHORT
            # Base Callback SL: Low (Current) + Callback%
            callback_sl = current_price * (1 + config.TRAILING_CALLBACK_RATE)
            # Min Profit Lock: Entry - MinProfit%
            min_profit_sl = entry * (1 - config.TRAILING_MIN_PROFIT_LOCK)
            
            new_sl = min(callback_sl, min_profit_sl)
            
            tracker_data['trailing_low'] = current_price

        # 2. Update Tracker
        self.tracker.update(symbol, {
            'trailing_active': True,
            'trailing_sl': new_sl,
            'trailing_high': tracker_data.get('trailing_high'),
            'trailing_low': tracker_data.get('trailing_low')
        })
        await self.tracker.save()
        
        logger.info(f"🔄 Trailing Mode ACTIVATED for {symbol} @ {current_price} | SL: {new_sl:.4f}")
        await kirim_tele(f"🔄 <b>TRAILING ACTIVE</b>\n{symbol}\nPrice: {current_price}\nInitial SL: {new_sl:.4f} (Locked)")
        
        # 3. Apply to Exchange
        await self._amend_sl_order(symbol, new_sl, side)

    async def update_trailing_sl(self, symbol, current_price):
        tracker_data = self.tracker.get(symbol)
        if not tracker_data or not tracker_data.get('trailing_active'): return

        side = tracker_data.get('side', 'LONG')
        current_sl = tracker_data.get('trailing_sl', 0)
        
        need_update = False
        new_sl = current_sl
        
        # 1. Update Internal High/Low & Calculate Candidate SL
        if side == 'LONG':
            trailing_high = tracker_data.get('trailing_high', 0)
            
            if current_price > trailing_high:
                tracker_data['trailing_high'] = current_price
                trailing_high = current_price

            candidate_sl = trailing_high * (1 - config.TRAILING_CALLBACK_RATE)

            if candidate_sl > current_sl:
                new_sl = candidate_sl
                need_update = True
                    
        else: # SHORT
            trailing_low = tracker_data.get('trailing_low', float('inf'))
            
            if current_price < trailing_low:
                tracker_data['trailing_low'] = current_price
                trailing_low = current_price
                
            candidate_sl = trailing_low * (1 + config.TRAILING_CALLBACK_RATE)

            if candidate_sl < current_sl:
                new_sl = candidate_sl
                need_update = True

        # 2. Execute Update (Throttled)
        if need_update:
            now = time.time()
            last_update = self._trailing_last_update.get(symbol, 0)

            if now - last_update < config.TRAILING_SL_UPDATE_COOLDOWN:
                return False

            self._trailing_last_update[symbol] = now
            
            # Update RAM & Disk
            self.tracker.update(symbol, {
                'trailing_sl': new_sl,
                'trailing_high': tracker_data.get('trailing_high'),
                'trailing_low': tracker_data.get('trailing_low')
            })
            await self.tracker.save()
            
            logger.info(f"📈 Trailing SL Updated {symbol}: {current_sl:.4f} -> {new_sl:.4f}")
            await self._amend_sl_order(symbol, new_sl, side)
            return True

        return False

    async def _amend_sl_order(self, symbol, new_sl_price, side):
        try:
            tracker_data = self.tracker.get(symbol) or {}
            sl_order_id = tracker_data.get('sl_order_id')
            use_fallback = False

            if sl_order_id:
                try:
                    await self.exchange.cancel_order(sl_order_id, symbol)
                except Exception as e:
                    logger.warning(f"⚠️ Fast Cancel Failed for {sl_order_id}: {e}. Falling back.")
                    use_fallback = True
            else:
                use_fallback = True

            if use_fallback:
                orders = await self.exchange.fetch_open_orders(symbol)
                for o in orders:
                    if o['type'] in ['stop_market', 'STOP_MARKET']:
                        try:
                            await self.exchange.cancel_order(o['id'], symbol)
                        except Exception as e:
                            logger.warning(f"Failed to cancel old SL {o['id']}: {e}")
            
            p_sl = self.exchange.price_to_precision(symbol, new_sl_price)
            side_api = 'sell' if side == 'LONG' else 'buy'
             
            new_order = await self.exchange.create_order(symbol, 'STOP_MARKET', side_api, None, None, {
                'stopPrice': p_sl, 'closePosition': True, 'workingType': 'MARK_PRICE'
            })
             
            if self.tracker.exists(symbol):
                self.tracker.update(symbol, {'sl_order_id': str(new_order['id'])})
                await self.tracker.save()
             
        except Exception as e:
            logger.error(f"❌ Failed to Amend SL {symbol}: {e}")

    # --- NATIVE TRAILING ---
    async def install_native_trailing_stop(self, symbol, side, quantity, callback_rate, activation_price=None):
        try:
            rate_percent = round(callback_rate * 100, 1)
            if rate_percent < config.NATIVE_TRAILING_MIN_RATE:
                rate_percent = config.NATIVE_TRAILING_MIN_RATE
            if rate_percent > config.NATIVE_TRAILING_MAX_RATE:
                rate_percent = config.NATIVE_TRAILING_MAX_RATE

            side_api = 'sell' if side == 'LONG' else 'buy'
            
            params = {
                'symbol': symbol.replace('/', ''),
                'side': side_api.upper(),
                'type': 'TRAILING_STOP_MARKET',
                'quantity': str(quantity),
                'callbackRate': str(rate_percent),
                'workingType': 'MARK_PRICE',
                'reduceOnly': 'true'
            }

            activation_log = ""
            if activation_price is not None:
                params['activationPrice'] = self.exchange.price_to_precision(symbol, activation_price)
                activation_log = f" | Activation: {activation_price:.4f}"

            logger.info(f"📤 Sending NATIVE Trailing Stop: {symbol} | Rate: {rate_percent}%{activation_log}")
            
            # BYPASS CCXT BUG: Use raw endpoint to prevent CCXT from routing it to `algoOrder` endpoint
            # which silently ignores `activationPrice` for trailing stops.
            # UPDATE: Trailing Stop is a standard order type on Binance Futures, not an algo order.
            order = await self.exchange.fapiPrivatePostOrder(params)
            
            # Raw binance response returns 'clientAlgoId' or 'algoId' for algo orders
            # and 'orderId' for standard orders
            order_id_str = str(order.get('clientAlgoId') or order.get('algoId') or order.get('orderId'))
            
            logger.info(f"✅ NATIVE Trailing Stop Active: {symbol} (ID: {order_id_str})")
            
            if self.tracker.exists(symbol):
                update_data = {
                    "status": "SECURED_NATIVE",
                    "native_trailing_id": order_id_str,
                    "trailing_active": True
                }
                if activation_price is not None:
                    update_data["activation_price"] = activation_price
                self.tracker.update(symbol, update_data)
                await self.tracker.save()
                
            return True

        except Exception as e:
            logger.error(f"❌ Failed to install Native Trailing: {e}")
            await kirim_tele(f"⚠️ <b>NATIVE TRAILING ERROR</b>\n{symbol}: {e}")
            return False

