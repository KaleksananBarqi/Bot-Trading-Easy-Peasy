import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import time
import requests
import sys
import os
import logging
import json
import config 

# ==========================================
# KONFIGURASI & GLOBALS
# ==========================================
logging.basicConfig(filename='bot_trading.log', level=logging.INFO, format='%(asctime)s - %(message)s')

last_entry_time = {}
exchange = None
positions_cache = set()
open_orders_cache = set()

# Database JSON untuk mencatat status SL/TP (Anti-Spam)
TRACKER_FILE = "safety_tracker.json"
safety_orders_tracker = {} 

global_btc_trend = "NEUTRAL"
last_btc_check = 0

# CRITICAL FIX: Global Lock untuk mencegah concurrent execution
safety_monitor_lock = None  # Will be initialized in main()

# ==========================================
# FUNGSI HELPER (JSON & TELEGRAM)
# ==========================================
# Di bagian LOAD TRACKER (Update sedikit agar lebih robust membaca ID)
def load_tracker():
    global safety_orders_tracker
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r') as f:
                data = json.load(f)
            
            safety_orders_tracker = {}
            for symbol, item in data.items():
                safety_orders_tracker[symbol] = {
                    "status": item.get("status", "UNKNOWN"),
                    "time": item.get("time", time.time()),
                    "last_check": item.get("last_check", time.time()), # Added field
                    "entry_price": float(item.get("entry_price", 0)),
                    "quantity": float(item.get("quantity", 0)), # Pastikan load quantity
                    "sl": float(item.get("sl", 0)),
                    "tp": float(item.get("tp", 0)),
                    "side": item.get("side", "UNKNOWN"),
                    "order_ids": item.get("order_ids", []) # Ini harus list of strings/ints
                }
            print(f"📂 Tracker loaded: {len(safety_orders_tracker)} data.")
        except Exception as e:
            print(f"⚠️ Gagal load tracker: {e}, membuat baru.")
            safety_orders_tracker = {}
    else:
        safety_orders_tracker = {}

def save_tracker():
    """Menyimpan status SL/TP ke file agar tahan restart."""
    try:
        # Format output yang lebih readable (vertikal)
        formatted_data = {}
        for symbol, data in safety_orders_tracker.items():
            # Konversi timestamp ke string waktu jika ada
            time_str = data.get("time", "")
            if isinstance(time_str, (int, float)):
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_str))
            
            formatted_data[symbol] = {
                "status": data.get("status", "UNKNOWN"),
                "time": time_str,
                "entry_price": round(float(data.get("entry_price", 0)), 8),
                "sl": round(float(data.get("sl", 0)), 8),
                "tp": round(float(data.get("tp", 0)), 8),
                "side": data.get("side", "UNKNOWN"),
                "order_ids": data.get("order_ids", []),
                "order_count": len(data.get("order_ids", []))
            }
        
        with open(TRACKER_FILE, 'w') as f:
            json.dump(formatted_data, f, indent=2, sort_keys=True)
        print(f"💾 Tracker disimpan: {len(safety_orders_tracker)} posisi")
    except Exception as e:
        print(f"⚠️ Gagal save tracker: {e}")

async def fetch_open_orders_safe(symbol, retries=config.ORDER_SLTP_RETRIES, delay=config.ORDER_SLTP_RETRY_DELAY):
    """Mengambil open orders dengan mekanisme retry yang robust."""
    for i in range(retries):
        try:
            return await exchange.fetch_open_orders(symbol)
        except Exception as e:
            if i == retries - 1: # Percobaan terakhir
                print(f"⚠️ Gagal fetch orders {symbol} setelah {retries}x: {e}")
                return []
            await asyncio.sleep(delay)
    return []
async def check_close_reason(symbol, tracker_data):
    """Mengecek apakah posisi close karena SL/TP atau manual."""
    try:
        # Cek 50 order terakhir yang sudah selesai (FILLED/CANCELED)
        # Kita cari order ID yang sama dengan yang ada di tracker
        closed_orders = await exchange.fetch_closed_orders(symbol, limit=50)
        tracked_ids = tracker_data.get("order_ids", [])
        
        sl_hit = False
        tp_hit = False
        
        for order in closed_orders:
            if order['id'] in tracked_ids and order['status'] == 'closed':
                # Cek tipe order
                if 'STOP' in order['type']:
                    sl_hit = True
                elif 'TAKE_PROFIT' in order['type']:
                    tp_hit = True
        
        if sl_hit: return "SL_HIT"
        if tp_hit: return "TP_HIT"
        return "MANUAL/LIQUIDATION"
        
    except Exception as e:
        print(f"⚠️ Gagal cek close reason {symbol}: {e}")
        return "UNKNOWN"

async def kirim_tele(pesan, alert=False):
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{prefix}{pesan}", 'parse_mode': 'HTML'})
    except Exception as e: 
        print(f"Tele error: {e}")

# ==========================================
# 0. SETUP AWAL
# ==========================================
async def setup_account_settings():
    print("⚙️ Memuat Database & Mengatur Leverage...")
    
    # 1. Load Ingatan Bot
    load_tracker() 
    
    # 2. Setup Exchange
    count = 0
    await kirim_tele("⚙️ <b>Bot Restarted.</b> Mengatur ulang config...")
    
    for koin in config.DAFTAR_KOIN:
        symbol = koin['symbol']
        lev = koin.get('leverage', config.DEFAULT_LEVERAGE)
        marg_type = koin.get('margin_type', config.DEFAULT_MARGIN_TYPE)

        try:
            await exchange.set_leverage(lev, symbol)
            try:
                await exchange.set_margin_mode(marg_type, symbol)
            except Exception:
                pass 
            
            print(f"   🔹 {symbol}: Lev {lev}x | {marg_type}")
            count += 1
            if count % 5 == 0: 
                await asyncio.sleep(0.5) 
        except Exception as e:
            logging.error(f"Gagal seting {symbol}: {e}")
            print(f"❌ Gagal seting {symbol}: {e}")
    
    print("✅ Setup Selesai. Bot Siap!")
    await kirim_tele("✅ <b>Setup Selesai.</b> Bot mulai memantau market.")

async def update_btc_trend():
    global global_btc_trend, last_btc_check
    now = time.time()
    
    if now - last_btc_check < config.BTC_CHECK_INTERVAL and global_btc_trend != "NEUTRAL":
        return global_btc_trend

    try:
        bars = await exchange.fetch_ohlcv(config.BTC_SYMBOL, config.BTC_TIMEFRAME, limit=100)
        if not bars: 
            return "NEUTRAL"

        df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
        ema_btc = df.ta.ema(length=config.BTC_EMA_PERIOD)
        
        current_price = df['close'].iloc[-1]
        current_ema = ema_btc.iloc[-1]

        prev_trend = global_btc_trend
        if current_price > current_ema:
            global_btc_trend = "BULLISH"
        else:
            global_btc_trend = "BEARISH"
        
        last_btc_check = now
        if prev_trend != global_btc_trend:
            print(f"🔄 BTC TREND CHANGE: {prev_trend} -> {global_btc_trend}")
            
        return global_btc_trend
    except Exception as e:
        logging.error(f"Gagal cek BTC trend: {e}")
        return "NEUTRAL"

# ==========================================
# 1. EKSEKUSI (LIMIT & MARKET)
# ==========================================
async def _async_eksekusi_binance(symbol, side, entry_price, sl_price, tp1, coin_config, order_type='market', indicator_info=None):
    print(f"🚀 EXECUTING: {symbol} {side} | Type: {order_type} @ {entry_price}")
    try:
        my_leverage = coin_config.get('leverage', config.DEFAULT_LEVERAGE)
        my_margin_usdt = coin_config.get('amount', config.DEFAULT_AMOUNT_USDT)

        # Hitung jumlah koin
        amount_coin = (my_margin_usdt * my_leverage) / entry_price
        amount_final = exchange.amount_to_precision(symbol, amount_coin)
        price_final = exchange.price_to_precision(symbol, entry_price) 

        notional_value = float(amount_final) * entry_price
        if notional_value < config.MIN_ORDER_USDT:
            print(f"⚠️ Order {symbol} terlalu kecil (${notional_value:.2f}). Skip.")
            return False

        # --- NOTIFIKASI ENTRY ---
        icon_side = "🟢 LONG" if side == 'buy' else "🔴 SHORT"
        msg = (
            f"{icon_side} <b>{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Mode:</b> {indicator_info.get('strategy', 'Unknown')}\n"
            f"📉 <b>Vol:</b> {indicator_info.get('vol', 'N/A')}\n"
            f"📈 <b>Indikator:</b> ADX {indicator_info.get('adx',0):.1f} | RSI {indicator_info.get('rsi',0):.1f}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏁 <b>Entry:</b> {price_final}\n"
            f"🎯 <b>TP Plan:</b> {tp1:.5f}\n"
            f"🛡️ <b>SL Plan:</b> {sl_price:.5f}"
        )

        # --- A. LIMIT ORDER (Liquidity Hunt) ---
        if order_type == 'limit':
            try:
                await exchange.create_order(symbol, 'limit', side, amount_final, price_final)
                print(f"⏳ {symbol} Limit Order placed at {price_final}. Menunggu fill...")
                await kirim_tele(msg + "\n⚠️ <i>Pending Limit Order</i>")
                return True
            except Exception as e:
                print(f"❌ Limit order gagal: {e}")
                # Fallback ke market order jika limit gagal
                print("🔄 Fallback ke market order...")
                order_type = 'market'

        # --- B. MARKET ORDER (Normal) ---
        if order_type == 'market':
            await exchange.create_order(symbol, 'market', side, amount_final)
            await kirim_tele(msg + "\n🚀 <i>Market Executed</i>")
            return True

    except Exception as e:
        logging.error(f"Error Eksekusi {symbol}: {e}")
        return False

# ==========================================
# 2. MONITOR & SAFETY (AUTO SL/TP - TRACKER PRIORITY)
# ==========================================
async def check_stop_orders(symbol):
    """Cek apakah stop orders sudah terpasang untuk simbol tertentu."""
    try:
        open_orders = await exchange.fetch_open_orders(symbol)
        stop_orders = []
        for order in open_orders:
            order_type = order['type'].lower()
            if 'stop' in order_type or 'take_profit' in order_type:
                stop_orders.append({
                    'id': order['id'],
                    'type': order['type'],
                    'side': order['side'],
                    'price': order.get('price'),
                    'stopPrice': order.get('stopPrice')
                })
        return stop_orders
    except Exception as e:
        print(f"⚠️ Error checking stop orders for {symbol}: {e}")
        return []

def print_tracker_status():
    """Mencetak status tracker ke terminal."""
    print("\n" + "="*60)
    print("📊 SAFETY TRACKER STATUS")
    print("="*60)
    
    if not safety_orders_tracker:
        print("📭 Tracker kosong")
        return
    
    for symbol, data in safety_orders_tracker.items():
        status = data.get("status", "UNKNOWN")
        side = data.get("side", "UNKNOWN")
        entry = data.get("entry_price", 0)
        sl = data.get("sl", 0)
        tp = data.get("tp", 0)
        order_count = len(data.get("order_ids", []))
        
        if side == "LONG":
            profit_pct = ((tp - entry) / entry * 100) if entry > 0 else 0
            loss_pct = ((entry - sl) / entry * 100) if entry > 0 else 0
        else:
            profit_pct = ((entry - tp) / entry * 100) if entry > 0 else 0
            loss_pct = ((sl - entry) / entry * 100) if entry > 0 else 0
        
        print(f"\n📈 {symbol}")
        print(f"   Status: {status} | Side: {side}")
        print(f"   Entry: {entry:.6f}")
        print(f"   SL: {sl:.6f} ({loss_pct:.2f}%)")
        print(f"   TP: {tp:.6f} ({profit_pct:.2f}%)")
        print(f"   Orders: {order_count} aktif")
    
    print("\n" + "="*60)
    
async def monitor_positions_safety():
    global safety_orders_tracker, safety_monitor_lock
    
    # CRITICAL: Acquire lock untuk mencegah concurrent execution
    async with safety_monitor_lock:
        try:
            # 1. AMBIL DATA REAL-TIME
            pos_raw = await exchange.fetch_positions()
            # Filter hanya posisi aktif (>0)
            active_positions = [p for p in pos_raw if float(p.get('contracts', 0)) > 0]
            
            active_symbols_now = []
            now = time.time()

            for pos in active_positions:
                symbol = pos['symbol']
                market_symbol = symbol.split(':')[0] if ':' in symbol else symbol
                active_symbols_now.append(market_symbol)

                current_contracts = float(pos['contracts'])
                entry_price = float(pos['entryPrice'])
                current_side = "LONG" if float(pos['info'].get('positionAmt', 0)) > 0 else "SHORT"
                
                # Toleransi Perubahan Size (misal kena DCA sedikit atau fee)
                size_tolerance = current_contracts * 0.05 

                # ==============================================================
                # LOGIKA ANTI-SPAM (STRICT MODE)
                # ==============================================================
                
                if market_symbol in safety_orders_tracker:
                    tracker = safety_orders_tracker[market_symbol]
                    tracked_qty = tracker.get("quantity", 0)
                    status = tracker.get("status", "UNKNOWN")
                    
                    # 1. CEK STATUS PENDING (Sedang OTW pasang)
                    if status == "PENDING":
                        # Jika masih pending kurang dari 1 menit, JANGAN GANGGU
                        if (now - tracker.get("time", 0)) < 60:
                            print(f"⏳ {market_symbol}: Sedang proses pasang TP/SL (PENDING)... Skip.")
                            continue
                        else:
                            print(f"⚠️ {market_symbol}: Pending macet > 60s. Reset status.")
                            # Jangan continue, biarkan lanjut ke bawah untuk dipasang ulang

                    # 2. CEK STATUS SECURED (Sudah terpasang)
                    if status == "SECURED":
                        # Cek apakah Size berubah drastis (Posisi ditambah/dikurang manual)
                        if abs(current_contracts - tracked_qty) < size_tolerance:
                            # JIKA SIZE SAMA & STATUS SECURED -> TIDAK USAH CEK BINANCE SAMA SEKALI
                            # Ini kunci agar tidak spam. Percaya tracker 100%.
                            tracker["last_check"] = now
                            continue 
                        else:
                            print(f"⚠️ {market_symbol}: Size berubah ({tracked_qty} -> {current_contracts}). Reset Tracker.")
                            # Hapus tracker lama agar di-setup ulang sesuai size baru
                            del safety_orders_tracker[market_symbol]
                
                # ==============================================================
                # JIKA LOLOS DARI ATAS, BERARTI BELUM AMAN. LANJUT PASANG.
                # ==============================================================

                print(f"🛡️ {market_symbol}: Mendeteksi posisi baru/berubah. Memeriksa safety...")

                # 1. Double Check ke API (Apakah order sudah ada di exchange tapi belum di tracker?)
                #    Hanya dilakukan jika di tracker kosong/reset.
                open_orders = await fetch_open_orders_safe(market_symbol, retries=3)
                
                existing_sl = []
                existing_tp = []
                
                for o in open_orders:
                    o_type = str(o['type']).upper()
                    o_reduce = o.get('reduceOnly', False)
                    o_side = str(o['side']).lower()
                    
                    is_pure_sl = (o_type in ['STOP_MARKET', 'STOP']) and o_reduce
                    is_pure_tp = (o_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT']) and o_reduce
                    
                    # Cek arah (Long punya Sell order, Short punya Buy order)
                    correct_side = (current_side == "LONG" and o_side == "sell") or \
                                   (current_side == "SHORT" and o_side == "buy")
                    
                    if correct_side:
                        if is_pure_sl: existing_sl.append(str(o['id']))
                        elif is_pure_tp: existing_tp.append(str(o['id']))

                has_sl = len(existing_sl) > 0
                has_tp = len(existing_tp) > 0

                # KASUS A: Order ternyata sudah ada di Binance (Sinkronisasi)
                if has_sl and has_tp:
                    print(f"✅ {market_symbol}: Order ditemukan di Exchange. Sync ke Tracker.")
                    safety_orders_tracker[market_symbol] = {
                        "status": "SECURED",
                        "time": now,
                        "last_check": now,
                        "entry_price": entry_price,
                        "quantity": current_contracts,
                        "side": current_side,
                        "order_ids": existing_sl + existing_tp
                    }
                    save_tracker()
                    continue

                # KASUS B: Belum ada order. PASANG BARU.
                
                # --- BERSIHKAN ORDER SAMPAH DULU ---
                # Misal cuma ada SL tanpa TP, atau TP tanpa SL, cancel semua biar rapi
                if len(open_orders) > 0:
                    print(f"🧹 {market_symbol}: Membersihkan order tidak lengkap sebelum setup...")
                    try:
                        await exchange.cancel_all_orders(market_symbol)
                        await asyncio.sleep(1) # Jeda agar exchange proses cancel
                    except Exception as e:
                        print(f"   Gagal cancel: {e}")

                # --- HITUNG HARGA ---
                try:
                    bars = await exchange.fetch_ohlcv(market_symbol, config.TIMEFRAME_EXEC, limit=50)
                    df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
                    atr = df.ta.atr(length=config.ATR_PERIOD).iloc[-1]
                except: 
                    atr = entry_price * 0.01

                # Logic Multiplier
                multiplier_sl = getattr(config, 'TRAP_SAFETY_SL', config.ATR_MULTIPLIER_SL) if getattr(config, 'USE_LIQUIDITY_HUNT', False) else config.ATR_MULTIPLIER_SL
                
                sl_dist = atr * multiplier_sl
                tp_dist = atr * config.ATR_MULTIPLIER_TP1
                
                if current_side == "LONG":
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + tp_dist
                    sl_side_api = 'sell'
                else:
                    sl_price = entry_price + sl_dist
                    tp_price = entry_price - tp_dist
                    sl_side_api = 'buy'

                qty_final = exchange.amount_to_precision(market_symbol, current_contracts)
                p_sl = exchange.price_to_precision(market_symbol, sl_price)
                p_tp = exchange.price_to_precision(market_symbol, tp_price)

                # --- KUNCI TRACKER SEKARANG (STATE: PENDING) ---
                # Ini yang mencegah concurrent process lain masuk saat kita lagi request ke API
                safety_orders_tracker[market_symbol] = {
                    "status": "PENDING",
                    "time": now,
                    "last_check": now,
                    "quantity": current_contracts,
                    "side": current_side,
                    "order_ids": []
                }
                save_tracker() # Simpan ke file biar kalau crash statusnya PENDING

                new_ids = []
                try:
                    print(f"🚀 {market_symbol}: Memasang TP/SL Baru...")
                    
                    # 1. Pasang SL
                    o_sl = await exchange.create_order(
                        market_symbol, 'STOP_MARKET', sl_side_api, qty_final, None, 
                        {'stopPrice': p_sl, 'workingType': 'MARK_PRICE', 'reduceOnly': True}
                    )
                    new_ids.append(str(o_sl['id']))
                    
                    # 2. Pasang TP
                    o_tp = await exchange.create_order(
                        market_symbol, 'TAKE_PROFIT_MARKET', sl_side_api, qty_final, None, 
                        {'stopPrice': p_tp, 'workingType': 'CONTRACT_PRICE', 'reduceOnly': True}
                    )
                    new_ids.append(str(o_tp['id']))

                    # SUKSES -> UPDATE JADI SECURED
                    safety_orders_tracker[market_symbol].update({
                        "status": "SECURED",
                        "sl": float(p_sl),
                        "tp": float(p_tp),
                        "entry_price": entry_price,
                        "order_ids": new_ids
                    })
                    save_tracker()
                    
                    print(f"✅ {market_symbol}: Safety orders TERPASANG.")
                    
                    # Hitung RR untuk laporan
                    risk = abs(entry_price - float(p_sl))
                    reward = abs(entry_price - float(p_tp))
                    rr_ratio = reward / risk if risk > 0 else 0
                    
                    await kirim_tele(
                        f"🛡️ <b>SAFETY SECURED</b>\n"
                        f"{market_symbol} ({current_side})\n"
                        f"📍 Entry: {entry_price}\n"
                        f"🛑 SL: {p_sl}\n"
                        f"🎯 TP: {p_tp}\n"
                        f"⚖️ R:R 1:{rr_ratio:.2f}"
                    )

                except Exception as e:
                    print(f"❌ Gagal pasang safety {market_symbol}: {e}")
                    # Jika gagal, HAPUS tracker agar dicoba lagi di loop berikutnya
                    if market_symbol in safety_orders_tracker:
                        del safety_orders_tracker[market_symbol]
                        save_tracker()
                    
                    # Cancel order setengah jalan (misal SL masuk, TP gagal)
                    for oid in new_ids:
                        try: await exchange.cancel_order(oid, market_symbol)
                        except: pass

            # ==============================================================
            # CLEANUP: Hapus Tracker jika posisi sudah ditutup di Binance
            # ==============================================================
            tracked_symbols = list(safety_orders_tracker.keys())
            for tracked in tracked_symbols:
                if tracked not in active_symbols_now:
                    # Ambil data sebelum dihapus untuk laporan
                    tracker_data = safety_orders_tracker[tracked]
                    reason = await check_close_reason(tracked, tracker_data)
                    
                    if reason == "SL_HIT":
                        msg = "🔴 <b>STOP LOSS HIT</b>"
                    elif reason == "TP_HIT":
                        msg = "🟢 <b>TAKE PROFIT HIT</b>"
                    else:
                        msg = "👋 <b>Position Closed / Manual</b>"
                    
                    await kirim_tele(f"{msg}\n🔐 {tracked}")
                    
                    print(f"🗑️ {tracked}: Posisi close. Menghapus tracker.")
                    del safety_orders_tracker[tracked]
                    save_tracker()

        except Exception as e:
            print(f"❌ Error Safety Monitor: {e}")
            import traceback
            traceback.print_exc()

# ==========================================
# 3. ANALISA MARKET (STRATEGI)
# ==========================================
def calculate_trade_parameters(signal, df):
    current = df.iloc[-1]
    atr = df.iloc[-2]['ATR']
    current_price = current['close']
    
    # Hitung Jarak Dasar
    retail_sl_dist = atr * config.ATR_MULTIPLIER_SL
    retail_tp_dist = atr * config.ATR_MULTIPLIER_TP1
    
    # Hitung Level Retail (Standard)
    if signal == "LONG":
        retail_sl = current_price - retail_sl_dist
        retail_tp = current_price + retail_tp_dist
        side_api = 'buy'
    else:
        # SHORT: SL diatas, TP dibawah
        retail_sl = current_price + retail_sl_dist
        retail_tp = current_price - retail_tp_dist
        side_api = 'sell'

    # Mode Liquidity Hunt (Anti-Retail)
    if getattr(config, 'USE_LIQUIDITY_HUNT', False):
        # Entry digeser ke posisi SL Retail (Trap)
        new_entry = retail_sl 
        
        # SL untuk safety trap (Jarak dari entry baru)
        safety_sl_dist = atr * getattr(config, 'TRAP_SAFETY_SL', 1.0)

        # [FIX] TP DIHITUNG ULANG DARI ENTRY BARU
        # Agar RR tetap konsisten sesuai config (misal 2.0 ATR)
        trap_tp_dist = atr * config.ATR_MULTIPLIER_TP1 
        
        if signal == "LONG":
            final_sl = new_entry - safety_sl_dist
            final_tp = new_entry + trap_tp_dist # TP Relatif terhadap Entry Bawah
        else:
            final_sl = new_entry + safety_sl_dist
            final_tp = new_entry - trap_tp_dist # TP Relatif terhadap Entry Atas
            
        return {"entry_price": new_entry, "sl": final_sl, "tp1": final_tp, "side_api": side_api, "type": "limit"}

    else:
        # Mode Normal (Market Order)
        return {"entry_price": current_price, "sl": retail_sl, "tp1": retail_tp, "side_api": side_api, "type": "market"}

async def analisa_market(coin_config, btc_trend_status):
    symbol = coin_config['symbol']
    now = time.time()
    
    # --- CEK COOLDOWN & OPEN ORDERS ---
    if symbol in last_entry_time and (now - last_entry_time[symbol] < config.COOLDOWN_PER_SYMBOL_SECONDS): 
        return

    try:
        base_symbol = symbol.split('/')[0]
        for pos_sym in positions_cache:
            if pos_sym == symbol or pos_sym.startswith(base_symbol): 
                return
        
        open_orders = await exchange.fetch_open_orders(symbol)
        limit_orders = [o for o in open_orders if o['type'] == 'limit' and o['status'] == 'open']
        if len(limit_orders) > 0:
            if len(limit_orders) > 1: 
                await exchange.cancel_all_orders(symbol)
            return 
            
    except Exception as e: 
        return 

    # --- FILTER TREND BTC ---
    allowed_signal = "BOTH"
    if symbol != config.BTC_SYMBOL:
        if btc_trend_status == "BULLISH": 
            allowed_signal = "LONG_ONLY"
        elif btc_trend_status == "BEARISH": 
            allowed_signal = "SHORT_ONLY"

    try:
        # 1. FETCH DATA (TIMEFRAME TREND & EKSEKUSI)
        bars = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
        bars_h1 = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND) 
        
        if not bars or not bars_h1: 
            return

        # 2. PROSES DATA MAJOR TREND FILTER
        df_h1 = pd.DataFrame(bars_h1, columns=['time','open','high','low','close','volume'])
        df_h1['EMA_MAJOR'] = df_h1.ta.ema(length=config.EMA_TREND_MAJOR)
        
        # Tentukan Bias Koin di Major Trend (Up/Down)
        trend_major_val = df_h1['EMA_MAJOR'].iloc[-1]
        price_h1_now = df_h1['close'].iloc[-1]
        is_coin_uptrend_h1 = price_h1_now > trend_major_val

        # 3. PROSES DATA TIMEFRAME EKSEKUSI
        df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
        
        # Hitung Indikator TIMEFRAME EKSEKUSI DULU SEBELUM LOGIKA
        df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
        df['EMA_SLOW'] = df.ta.ema(length=config.EMA_SLOW)
        df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)
        df['ADX'] = df.ta.adx(length=config.ADX_PERIOD)[f"ADX_{config.ADX_PERIOD}"]
        df['RSI'] = df.ta.rsi(length=14)
        
        df['VOL_MA'] = df['volume'].rolling(window=config.VOL_MA_PERIOD).mean() 
        
        bb = df.ta.bbands(length=config.BB_LENGTH, std=config.BB_STD)
        df['BBL'] = bb[f'BBL_{config.BB_LENGTH}_{config.BB_STD}']
        df['BBU'] = bb[f'BBU_{config.BB_LENGTH}_{config.BB_STD}']
        stoch = df.ta.stochrsi(length=config.STOCHRSI_LEN, rsi_length=config.STOCHRSI_LEN, k=config.STOCHRSI_K, d=config.STOCHRSI_D)
        df['STOCH_K'] = stoch.iloc[:, 0]
        df['STOCH_D'] = stoch.iloc[:, 1]
        
        # Ambil variable indikator
        confirm = df.iloc[-2]
        adx_val = confirm['ADX']
        current_price = confirm['close']
        current_rsi = confirm['RSI']
        is_volume_valid = confirm['volume'] > confirm['VOL_MA']
        
        price_now = confirm['close']
        ema_fast_m5 = confirm['EMA_FAST']

        signal = None
        strategy_type = "NONE"
        
        # Cek apakah fitur Trend Trap aktif di Config
        if getattr(config, 'USE_TREND_TRAP_STRATEGY', False):
            
            # --- A. STRATEGI TREND TRAP (Pullback di Tren Kuat) ---
            # Syarat: ADX > Limit Config (Default 25)
            if adx_val > config.TREND_TRAP_ADX_MIN:
                
                # 1. CEK LONG (Trend H1 Naik + M5 Koreksi)
                if (allowed_signal in ["LONG_ONLY", "BOTH"]) and is_coin_uptrend_h1:
                    # Zona Diskon: Harga di bawah EMA Fast (sedang merah) tapi di atas BB Bawah
                    is_pullback_zone = (price_now < ema_fast_m5) and (price_now > confirm['BBL'])
                    
                    # Cek Filter RSI dari Config
                    rsi_pass = (current_rsi >= config.TREND_TRAP_RSI_LONG_MIN) and \
                               (current_rsi <= config.TREND_TRAP_RSI_LONG_MAX)
                    
                    if is_pullback_zone and rsi_pass:
                        signal = "LONG"
                        strategy_type = f"TREND_PULLBACK (RSI {current_rsi:.1f})"

                # 2. CEK SHORT (Trend H1 Turun + M5 Koreksi Naik)
                if (allowed_signal in ["SHORT_ONLY", "BOTH"]) and (not is_coin_uptrend_h1) and (signal is None):
                    # Zona Diskon Sell: Harga di atas EMA Fast (sedang hijau) tapi di bawah BB Atas
                    is_pullback_zone_sell = (price_now > ema_fast_m5) and (price_now < confirm['BBU'])
                    
                    # Cek Filter RSI dari Config
                    rsi_pass = (current_rsi >= config.TREND_TRAP_RSI_SHORT_MIN) and \
                               (current_rsi <= config.TREND_TRAP_RSI_SHORT_MAX)
                    
                    if is_pullback_zone_sell and rsi_pass:
                        signal = "SHORT"
                        strategy_type = f"TREND_PULLBACK (RSI {current_rsi:.1f})"

        # --- B. STRATEGI SIDEWAYS (BB BOUNCE) ---
        # Hanya jalan jika diaktifkan di config DAN ADX rendah
        if getattr(config, 'USE_SIDEWAYS_SCALP', False) and (signal is None):
            if adx_val < config.SIDEWAYS_ADX_MAX:
                # Buy di BB Bawah
                if (price_now <= confirm['BBL']) and (confirm['STOCH_K'] < 20):
                     if (allowed_signal in ["LONG_ONLY", "BOTH"]):
                        signal = "LONG"
                        strategy_type = "BB_BOUNCE_BOTTOM"
                
                # Sell di BB Atas
                elif (price_now >= confirm['BBU']) and (confirm['STOCH_K'] > 80):
                     if (allowed_signal in ["SHORT_ONLY", "BOTH"]):
                        signal = "SHORT"
                        strategy_type = "BB_BOUNCE_TOP"

        # 5. EKSEKUSI
        if signal:
            params = calculate_trade_parameters(signal, df)
            
            info = {
                'strategy': strategy_type,
                'vol': 'High' if is_volume_valid else 'Low',
                'adx': adx_val,
                'rsi': current_rsi
            }

            berhasil = await _async_eksekusi_binance(
                symbol, params['side_api'], params['entry_price'], 
                params['sl'], params['tp1'], coin_config, 
                order_type=params.get('type', 'market'),
                indicator_info=info
            )
            
            if berhasil:
                last_entry_time[symbol] = now
                
    except Exception as e:
        logging.error(f"Analisa error {symbol}: {e}")

# ==========================================
# 4. LOOP UTAMA
# ==========================================
async def main():
    global exchange, positions_cache, global_btc_trend, safety_orders_tracker, safety_monitor_lock
    
    # CRITICAL: Initialize async lock
    safety_monitor_lock = asyncio.Lock()
    
    params = {'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
              'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
              'enableRateLimit': True, 'options': {'defaultType': 'future'}}
    exchange = ccxt.binance(params)
    if config.PAKAI_DEMO: 
        exchange.enable_demo_trading(True)

    await kirim_tele("🚀 <b>BOT STARTED (Pullback Sniper + LOCK FIX)</b>")
    await setup_account_settings()

    # Semaphore untuk limit konkurensi analisa
    sem = asyncio.Semaphore(config.CONCURRENCY_LIMIT)

    async def safe_analisa(k, trend):
        async with sem:
            await analisa_market(k, trend)

    while True:
        try:
            pos = await exchange.fetch_positions()
            positions_cache = {p['symbol'].split(':')[0] for p in pos if float(p.get('contracts', 0)) > 0}
            
            # CRITICAL: Monitor dijalankan SEKALI per loop (tidak concurrent!)
            await monitor_positions_safety()
            
            # Tampilkan status
            print_tracker_status()

            btc_trend = await update_btc_trend()
            
            # Analisa market bisa concurrent (sudah di-protect semaphore)
            tasks = [safe_analisa(k, btc_trend) for k in config.DAFTAR_KOIN]
            await asyncio.gather(*tasks)
            
            print(f"⏳ Loop selesai. Active Pos: {len(positions_cache)}")
            await asyncio.sleep(10)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 1. Handle Stop Manual (Ctrl+C)
        print("\n🛑 Bot dihentikan oleh User...")
        asyncio.run(kirim_tele("🛑 <b>BOT STOPPED</b>\nBot dimatikan secara manual oleh User", alert=True))
    except Exception as e:
        # 2. Handle Crash / Error Sistem Tak Terduga
        print(f"\n❌ Bot Crash: {e}")
        asyncio.run(kirim_tele(f"❌ <b>BOT CRASHED</b>\nSistem berhenti mendadak karena error:\n<code>{str(e)}</code>", alert=True))