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

# ==========================================
# FUNGSI HELPER (JSON & TELEGRAM)
# ==========================================
def load_tracker():
    """Membaca status SL/TP dari file saat bot dinyalakan."""
    global safety_orders_tracker
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r') as f:
                safety_orders_tracker = json.load(f)
            print(f"📂 Tracker loaded: {len(safety_orders_tracker)} data.")
        except Exception as e:
            print(f"⚠️ Gagal load tracker: {e}, membuat baru.")
            safety_orders_tracker = {}
    else:
        safety_orders_tracker = {}

def save_tracker():
    """Menyimpan status SL/TP ke file agar tahan restart."""
    try:
        with open(TRACKER_FILE, 'w') as f:
            json.dump(safety_orders_tracker, f)
    except Exception as e:
        print(f"⚠️ Gagal save tracker: {e}")

async def kirim_tele(pesan, alert=False):
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{prefix}{pesan}", 'parse_mode': 'HTML'})
    except Exception as e: print(f"Tele error: {e}")

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
            if count % 5 == 0: await asyncio.sleep(0.5) 
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
        if not bars: return "NEUTRAL"

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
            await exchange.create_order(symbol, 'limit', side, amount_final, price_final)
            print(f"⏳ {symbol} Limit Order placed at {price_final}. Menunggu fill...")
            await kirim_tele(msg + "\n⚠️ <i>Pending Limit Order</i>")
            return True

        # --- B. MARKET ORDER (Normal) ---
        else:
            await exchange.create_order(symbol, 'market', side, amount_final)
            await kirim_tele(msg + "\n🚀 <i>Market Executed</i>")
            
            # Pasang SL/TP Langsung (Opsional, karena Safety Monitor juga akan handle)
            # Kita biarkan Safety Monitor yang handle agar logika terpusat satu pintu
            return True

    except Exception as e:
        logging.error(f"Error Eksekusi {symbol}: {e}")
        return False

# ==========================================
# 2. MONITOR & SAFETY (AUTO SL/TP - TRACKER PRIORITY)
# ==========================================
async def monitor_positions_safety():
    """
    Fungsi Satpam V10 (Tracker Priority):
    - Mengutamakan catatan lokal (JSON) daripada API untuk mencegah spam.
    - Jika di JSON tercatat 'aman', bot TIDAK AKAN mengecek order ke Binance.
    - Hanya menghapus catatan jika posisi benar-benar tertutup.
    """
    global safety_orders_tracker 

    try:
        # 1. Ambil Posisi Aktif dari Binance
        pos_raw = await exchange.fetch_positions()
        # Filter hanya posisi yang size-nya > 0
        active_positions = [p for p in pos_raw if float(p.get('contracts', 0)) > 0]
        
        # List simbol yang sedang aktif sekarang (untuk keperluan cleanup nanti)
        active_symbols_now = [] 

        for pos in active_positions:
            symbol = pos['symbol']
            # Normalisasi simbol (misal METIS/USDT:USDT -> METIS/USDT)
            market_symbol = symbol.split(':')[0] if ':' in symbol else symbol
            active_symbols_now.append(market_symbol)

            # --- [LOGIKA BARU] CEK TRACKER DULU (USULAN ANDA) ---
            # Jika simbol ini sudah tercatat di tracker, ANGGAP AMAN. 
            # Jangan buang waktu fetch_open_orders (ini biang kerok spam).
            if market_symbol in safety_orders_tracker:
                # Optional: Print heartbeat sesekali kalau mau, tapi di-skip biar log bersih
                continue 

            # ==========================================================
            # JIKA SAMPAI SINI, BERARTI POSISI BARU ATAU BELUM DIAMANKAN
            # ==========================================================
            
            # --- DETEKSI ARAH POSISI ---
            raw_amt = float(pos['info'].get('positionAmt', 0))
            if raw_amt > 0: is_long_pos = True
            elif raw_amt < 0: is_long_pos = False
            else: continue 

            print(f"🔍 Mendeteksi posisi baru/unsecured: {market_symbol}...")

            # --- KALKULASI SL/TP ---
            amount = float(pos['contracts'])
            entry_price = float(pos['entryPrice'])
            
            # Fetch ATR untuk jarak dinamis
            try:
                bars = await exchange.fetch_ohlcv(market_symbol, config.TIMEFRAME_EXEC, limit=20)
                df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
                atr = df.ta.atr(length=config.ATR_PERIOD).iloc[-1]
            except:
                print(f"⚠️ Gagal fetch ATR {market_symbol}, pakai default 1% price.")
                atr = entry_price * 0.01

            sl_dist = atr * config.ATR_MULTIPLIER_SL
            tp_dist = atr * config.ATR_MULTIPLIER_TP1
            
            if is_long_pos:
                sl_price = entry_price - sl_dist; tp_price = entry_price + tp_dist; sl_side = 'sell'
            else:
                sl_price = entry_price + sl_dist; tp_price = entry_price - tp_dist; sl_side = 'buy'
            
            amount_final = exchange.amount_to_precision(market_symbol, amount)

            # --- EKSEKUSI PEMASANGAN SL/TP ---
            try:
                # 1. Pastikan tidak ada order nyangkut dulu (Cancel All spesifik simbol ini)
                #    Kita lakukan ini SEKALI saja di awal pendeteksian.
                try:
                    await exchange.cancel_all_orders(market_symbol)
                    await asyncio.sleep(1) # Jeda agar binance proses cancel
                except: pass

                # 2. Pasang Order Baru
                tasks = []
                # SL MARKET
                params_sl = {'stopPrice': exchange.price_to_precision(market_symbol, sl_price), 'workingType': 'MARK_PRICE', 'reduceOnly': True}
                tasks.append(exchange.create_order(market_symbol, 'STOP_MARKET', sl_side, amount_final, params=params_sl))
                
                # TP MARKET
                params_tp = {'stopPrice': exchange.price_to_precision(market_symbol, tp_price), 'workingType': 'CONTRACT_PRICE', 'reduceOnly': True}
                tasks.append(exchange.create_order(market_symbol, 'TAKE_PROFIT_MARKET', sl_side, amount_final, params=params_tp))
                
                # Jalankan order
                await asyncio.gather(*tasks)

                # --- [PENTING] CATAT KE TRACKER AGAR TIDAK DIULANG ---
                safety_orders_tracker[market_symbol] = {
                    "status": "SECURED",
                    "time": time.time(),
                    "sl": sl_price,
                    "tp": tp_price
                }
                save_tracker() # Simpan ke JSON fisik
                
                print(f"✅ {market_symbol} Safety Replaced & Locked in Tracker.")
                await kirim_tele(f"🛡️ <b>SAFETY SECURED</b>\n{market_symbol}\nSL: {sl_price:.4f} | TP: {tp_price:.4f}\n<i>Status: Locked (Anti-Spam)</i>")

            except Exception as e:
                print(f"❌ Gagal pasang safety {market_symbol}: {e}")
                # Jangan catat ke tracker kalau gagal, biar dicoba lagi next loop

        # 3. CLEANUP (HAPUS CATATAN KALO POSISI DAH CLOSE)
        # Logic: Jika ada di tracker TAPI tidak ada di active_symbols_now -> Hapus
        keys_to_delete = []
        for recorded_symbol in list(safety_orders_tracker.keys()):
            if recorded_symbol not in active_symbols_now:
                keys_to_delete.append(recorded_symbol)
        
        if keys_to_delete:
            for k in keys_to_delete:
                del safety_orders_tracker[k]
                print(f"🗑️ Posisi {k} closed. Tracker dibersihkan.")
            save_tracker()

    except Exception as e:
        print(f"Error Safety Monitor: {e}")

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
    if symbol in last_entry_time and (now - last_entry_time[symbol] < config.COOLDOWN_PER_SYMBOL_SECONDS): return

    try:
        base_symbol = symbol.split('/')[0]
        for pos_sym in positions_cache:
            if pos_sym == symbol or pos_sym.startswith(base_symbol): return
        
        open_orders = await exchange.fetch_open_orders(symbol)
        limit_orders = [o for o in open_orders if o['type'] == 'limit' and o['status'] == 'open']
        if len(limit_orders) > 0:
            if len(limit_orders) > 1: await exchange.cancel_all_orders(symbol)
            return 
            
    except Exception as e: return 

    # --- FILTER TREND BTC ---
    allowed_signal = "BOTH"
    if symbol != config.BTC_SYMBOL:
        if btc_trend_status == "BULLISH": allowed_signal = "LONG_ONLY"
        elif btc_trend_status == "BEARISH": allowed_signal = "SHORT_ONLY"

    try:
        # 1. FETCH DATA (TIMEFRAME TREND & EKSEKUSI)
        bars = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
        bars_h1 = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND) 
        
        if not bars or not bars_h1: return

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
                        signal = "LONG"; strategy_type = "BB_BOUNCE_BOTTOM"
                
                # Sell di BB Atas
                elif (price_now >= confirm['BBU']) and (confirm['STOCH_K'] > 80):
                     if (allowed_signal in ["SHORT_ONLY", "BOTH"]):
                        signal = "SHORT"; strategy_type = "BB_BOUNCE_TOP"

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
    global exchange, positions_cache, global_btc_trend
    
    params = {'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
              'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
              'enableRateLimit': True, 'options': {'defaultType': 'future'}}
    exchange = ccxt.binance(params)
    if config.PAKAI_DEMO: exchange.enable_demo_trading(True)

    await kirim_tele("🚀 <b>BOT STARTED (Pullback Type))</b>")
    await setup_account_settings()

    # --- PERUBAHAN DIMULAI DI SINI ---
    # 1. Buat "Satpam Pintu" (Semaphore) sesuai limit di config
    sem = asyncio.Semaphore(config.CONCURRENCY_LIMIT)

    # 2. Fungsi Wrapper untuk membatasi antrian masuk
    async def safe_analisa(k, trend):
        async with sem: # Hanya izinkan masuk jika "pintu" belum penuh
            await analisa_market(k, trend)
    # --- PERUBAHAN SELESAI ---

    while True:
        try:
            pos = await exchange.fetch_positions()
            positions_cache = {p['symbol'].split(':')[0] for p in pos if float(p.get('contracts', 0)) > 0}
            
            await monitor_positions_safety()

            btc_trend = await update_btc_trend()
            
            # Gunakan wrapper 'safe_analisa' di dalam list comprehension
            tasks = [safe_analisa(k, btc_trend) for k in config.DAFTAR_KOIN]
            
            # Eksekusi (sekarang sudah dibatasi rate limit-nya oleh Semaphore)
            await asyncio.gather(*tasks)
            
            print(f"⏳ Loop selesai. Active Pos: {len(positions_cache)}")
            await asyncio.sleep(10)

        except asyncio.CancelledError:
            # Tangkap jika task di-cancel secara internal
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