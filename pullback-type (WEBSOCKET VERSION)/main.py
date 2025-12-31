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
import websockets
import config 

# ==========================================
# KONFIGURASI LOGGER (FILE + CONSOLE)
# ==========================================
from datetime import datetime, timedelta, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def wib_time(*args):
    utc_dt = datetime.now(timezone.utc)
    wib_dt = utc_dt + timedelta(hours=7)
    return wib_dt.timetuple()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')
formatter.converter = wib_time 

file_handler = logging.FileHandler(config.LOG_FILENAME)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==========================================
# KONFIGURASI & GLOBALS
# ==========================================
market_data_store = {} 
position_cache_ws = {} 
ticker_cache = {}

exchange = None
safety_orders_tracker = {} 
SYMBOL_COOLDOWN = {} 

# GLOBAL TREND FILTER
btc_trend_direction = "NEUTRAL" 
data_lock = asyncio.Lock()

# ==========================================
# FUNGSI HELPER
# ==========================================
def load_tracker():
    global safety_orders_tracker
    if os.path.exists(config.TRACKER_FILENAME):
        try:
            with open(config.TRACKER_FILENAME, 'r') as f:
                safety_orders_tracker = json.load(f)
            print(f"📂 Tracker loaded: {len(safety_orders_tracker)} data.")
        except: safety_orders_tracker = {}
    else: safety_orders_tracker = {}

def save_tracker():
    try:
        with open(config.TRACKER_FILENAME, 'w') as f:
            json.dump(safety_orders_tracker, f, indent=2, sort_keys=True)
    except Exception as e: print(f"⚠️ Gagal save tracker: {e}")

async def kirim_tele(pesan, alert=False):
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{prefix}{pesan}", 'parse_mode': 'HTML'})
    except: pass

# ==========================================
# WEBSOCKET MANAGER
# ==========================================
class BinanceWSManager:
    def __init__(self, exchange_ref):
        self.exchange = exchange_ref
        self.listen_key = None
        self.base_url = config.WS_URL_FUTURES_TESTNET if config.PAKAI_DEMO else config.WS_URL_FUTURES_LIVE
        self.last_heartbeat = time.time()
        
    async def get_listen_key(self):
        try:
            response = await self.exchange.fapiPrivatePostListenKey()
            self.listen_key = response['listenKey']
            return self.listen_key
        except Exception as e:
            print(f"❌ Gagal ambil ListenKey: {e}")
            return None

    async def keep_alive_listen_key(self):
        while True:
            await asyncio.sleep(config.WS_KEEP_ALIVE_INTERVAL)
            try:
                await self.exchange.fapiPrivatePutListenKey({'listenKey': self.listen_key})
                if time.time() - self.last_heartbeat > 60:
                    print("⚠️ WS Heartbeat Timeout! Reconnecting...")
                    raise Exception("WS Heartbeat Timeout")
            except Exception as e: 
                print(f"⚠️ Keep Alive / Health Check Error: {e}")

    async def start_stream(self):
        while True: 
            await self.get_listen_key()
            if not self.listen_key: 
                await asyncio.sleep(5)
                continue

            streams = []
            for coin in config.DAFTAR_KOIN:
                sym_clean = coin['symbol'].replace('/', '').lower()
                streams.append(f"{sym_clean}@kline_{config.TIMEFRAME_EXEC}")
                streams.append(f"{sym_clean}@kline_{config.BTC_TIMEFRAME}")
            
            streams.append(self.listen_key) 
            url = self.base_url + "/".join(streams)
            print(f"📡 Connecting to WebSocket... ({len(streams)} streams)")

            asyncio.create_task(self.keep_alive_listen_key())

            try:
                async with websockets.connect(url) as ws:
                    print("✅ WebSocket Connected!")
                    await kirim_tele("✅ <b>WebSocket Connected</b>. System Online.")
                    self.last_heartbeat = time.time()
                    
                    while True:
                        msg = await ws.recv()
                        self.last_heartbeat = time.time()
                        data = json.loads(msg)
                        
                        if 'data' in data:
                            payload = data['data']
                            evt = payload.get('e', '')
                            
                            if evt == 'kline': await self.handle_kline(payload)
                            elif evt == 'ACCOUNT_UPDATE': await self.handle_account_update(payload)
                            elif evt == 'ORDER_TRADE_UPDATE': await self.handle_order_update(payload)
            except Exception as e:
                print(f"⚠️ WS Connection Lost: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def handle_kline(self, data):
        global market_data_store, btc_trend_direction
        
        sym = data['s'] 
        symbol = sym.replace('USDT', '/USDT') 
        k = data['k']
        interval = k['i']
        
        # Format: [timestamp, open, high, low, close, volume]
        new_candle = [
            int(k['t']), float(k['o']), float(k['h']), 
            float(k['l']), float(k['c']), float(k['v'])
        ]
        
        async with data_lock:
            if symbol not in market_data_store: return
            target_list = market_data_store[symbol].get(interval, [])
            
            # Logic update candle: Jika timestamp sama, replace. Jika beda, append.
            if len(target_list) > 0 and new_candle[0] == target_list[-1][0]:
                target_list[-1] = new_candle
            else:
                target_list.append(new_candle)
                if len(target_list) > config.LIMIT_TREND + 5: target_list.pop(0)
            
            market_data_store[symbol][interval] = target_list

            # --- UPDATE TREND BTC (KING FILTER) ---
            if symbol == config.BTC_SYMBOL and interval == config.BTC_TIMEFRAME:
                # Perlu minimal 50 candle untuk EMA 50
                closes = [c[4] for c in target_list]
                if len(closes) >= config.BTC_EMA_PERIOD:
                    # Hitung EMA Manual sederhana untuk BTC Filter
                    ema_val = pd.Series(closes).ewm(span=config.BTC_EMA_PERIOD, adjust=False).mean().iloc[-1]
                    price_now = closes[-1]
                    prev_trend = btc_trend_direction
                    
                    # Logic: Close > EMA = Bullish
                    btc_trend_direction = "BULLISH" if price_now > ema_val else "BEARISH"
                    
                    if prev_trend != btc_trend_direction:
                        print(f"👑 BTC TREND CHANGE: {prev_trend} -> {btc_trend_direction}")

    async def handle_account_update(self, data):
        global position_cache_ws, safety_orders_tracker
        try:
            positions = data['a']['P']
            async with data_lock:
                for p in positions:
                    sym = p['s'].replace('USDT', '/USDT')
                    amt = float(p['pa'])
                    entry = float(p['ep'])
                    base_sym = sym.split('/')[0]
                    
                    if amt != 0:
                        position_cache_ws[base_sym] = {
                            'symbol': sym, 'contracts': abs(amt),
                            'side': 'LONG' if amt > 0 else 'SHORT',
                            'entryPrice': entry, 'update_time': time.time()
                        }
                    else:
                        if base_sym in position_cache_ws:
                            print(f"📉 Position Closed (WS): {sym}")
                            del position_cache_ws[base_sym]
                            if sym in safety_orders_tracker:
                                del safety_orders_tracker[sym]
                                save_tracker()
                                try: await exchange.cancel_all_orders(sym)
                                except: pass
        except: pass

    async def handle_order_update(self, data):
        try:
            order_info = data['o']
            symbol = order_info['s'].replace('USDT', '/USDT')
            status = order_info['X'] 
            order_type = order_info['ot'] 
            side = order_info['S']
            price = float(order_info['ap']) 
            pnl = float(order_info.get('rp', 0)) 

            if status == 'FILLED':
                if order_type == 'LIMIT':
                    # Entry Sniper Filled
                    logger.info(f"⚡ LIMIT FILLED: {symbol} | Side: {side} | Price: {price}")
                    async with data_lock:
                        safety_orders_tracker[symbol] = {'status': 'PENDING', 'last_check': time.time()}
                        save_tracker()
                    msg = (f"⚡ <b>ENTRY FILLED</b>\n🚀 <b>{symbol}</b> Entered @ {price}\n<i>Memasang safety orders...</i>")
                    await kirim_tele(msg)

                elif order_type in ['TAKE_PROFIT_MARKET', 'STOP_MARKET']:
                    logger.info(f"🏁 POSITION CLOSED: {symbol} | Type: {order_type} | PnL: ${pnl:.2f}")
                    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
                    msg = (f"{'💰 TAKE PROFIT' if pnl > 0 else '🛑 STOP LOSS'} HIT\n✨ <b>{symbol}</b>\n💸 PnL: <b>{pnl_str}</b>")
                    await kirim_tele(msg)
                    await fetch_existing_positions()

            elif status == 'CANCELED':
                logger.warning(f"🚫 ORDER CANCELED: {symbol} | ID: {order_info.get('i')}")

        except Exception as e:
            logger.error(f"⚠️ Order Update Error: {e}", exc_info=True)

# ==========================================
# INITIALIZER & RECOVERY
# ==========================================
async def fetch_existing_positions():
    print("🔍 Checking Existing Positions...")
    try:
        balance = await exchange.fetch_positions() 
        count = 0
        async with data_lock:
            for pos in balance:
                amt = float(pos['contracts'])
                if amt > 0:
                    sym = pos['symbol'] 
                    base_sym = sym.split('/')[0]
                    side = 'LONG' if pos['side'] == 'long' else 'SHORT' 
                    if pos.get('info', {}).get('positionAmt'):
                        raw_amt = float(pos['info']['positionAmt'])
                        side = 'LONG' if raw_amt > 0 else 'SHORT'

                    position_cache_ws[base_sym] = {
                        'symbol': sym, 'contracts': amt,
                        'side': side,
                        'entryPrice': float(pos['entryPrice']),
                        'update_time': time.time()
                    }
                    count += 1
        print(f"✅ Positions Synced: {count} active.")
    except Exception as e:
        print(f"❌ Failed to fetch positions: {e}")

async def install_safety_for_existing_positions():
    # Helper untuk recovery restart
    current_positions = dict(position_cache_ws)
    for base_sym, pos_data in current_positions.items():
        symbol = pos_data['symbol']
        tracker = safety_orders_tracker.get(symbol, {})
        status = tracker.get("status", "UNKNOWN")
        if status != "SECURED":
            safety_orders_tracker[symbol] = {"status": "PENDING", "last_check": time.time()}
            save_tracker()

async def initialize_market_data():
    print("📥 Initializing Market Data (REST)...")
    tasks = []
    
    async def fetch_pair(coin):
        symbol = coin['symbol']
        market_data_store[symbol] = {}
        try:
            # Ambil data sedikit lebih banyak untuk aman
            bars_5m = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
            bars_btc = await exchange.fetch_ohlcv(symbol, config.BTC_TIMEFRAME, limit=config.LIMIT_TREND)
            async with data_lock:
                market_data_store[symbol][config.TIMEFRAME_EXEC] = bars_5m
                market_data_store[symbol][config.BTC_TIMEFRAME] = bars_btc
            print(f"   ✅ Loaded: {symbol}")
        except Exception as e:
            print(f"   ❌ Failed Load {symbol}: {e}")

    for koin in config.DAFTAR_KOIN: tasks.append(fetch_pair(koin))
    await asyncio.gather(*tasks)
    
    # Initialize BTC Trend
    if config.BTC_SYMBOL in market_data_store:
        bars = market_data_store[config.BTC_SYMBOL][config.BTC_TIMEFRAME]
        df_btc = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        ema_btc = df_btc.ta.ema(length=config.BTC_EMA_PERIOD).iloc[-1]
        global btc_trend_direction
        btc_trend_direction = "BULLISH" if df_btc['close'].iloc[-1] > ema_btc else "BEARISH"
        print(f"👑 INITIAL BTC TREND: {btc_trend_direction}")

# ==========================================
# CORE LOGIC: ANALISA MARKET (FIXED 1:1 BACKTEST)
# ==========================================

def calculate_trade_parameters(signal, df, symbol=None, strategy_type="TREND_TRAP", tech_info=None):
    # [FIX POINT 4]: WAJIB pakai iloc[-2] (Candle yg sudah Close)
    current = df.iloc[-2] 
    atr = current['ATR']
    current_price = current['close']
    
    # Hitung Jarak Dasar (Standard Retail)
    retail_sl_dist = atr * config.ATR_MULTIPLIER_SL
    retail_tp_dist = atr * config.ATR_MULTIPLIER_TP1
    
    if signal == "LONG":
        retail_sl = current_price - retail_sl_dist
        retail_tp = current_price + retail_tp_dist
        side_api = 'buy'
    else: # SHORT
        retail_sl = current_price + retail_sl_dist
        retail_tp = current_price - retail_tp_dist
        side_api = 'sell'
        
    entry_price = current_price
    sl_price = retail_sl
    tp_price = retail_tp
    order_type = config.ORDER_TYPE

    # --- [FIX POINT 1]: LOGIKA SNIPER / LIQUIDITY HUNT (Anti-Retail) ---
    # Syarat: Hanya aktif jika config TRUE dan strategy bukan murni momentum (optional)
    if config.USE_LIQUIDITY_HUNT:
        
        # [FIX]: Gunakan jarak safety trap (Trap Safety SL)
        safety_sl_dist = atr * getattr(config, 'TRAP_SAFETY_SL', 1.0)
        
        if signal == "LONG":
            # [FIX]: Entry persis di Retail SL (Tanpa buffer variabel, hardcoded logic backtest)
            sniper_entry = retail_sl 
            
            # Cek logika dasar: Entry limit harus dibawah harga sekarang
            if sniper_entry < current_price:
                entry_price = sniper_entry
                sl_price = entry_price - safety_sl_dist
                # [FIX POINT 2]: TP dihitung dari ENTRY BARU + (ATR * Multiplier)
                # Bukan berdasarkan Risk Ratio, tapi Fixed Distance sesuai Config Backtest
                tp_price = entry_price + (atr * config.ATR_MULTIPLIER_TP1)
                order_type = 'limit'
                print(f"🔫 SNIPER LONG: Entry moved to Retail SL @ {entry_price}")

        elif signal == "SHORT":
            # [FIX]: Entry persis di Retail SL
            sniper_entry = retail_sl
            
            if sniper_entry > current_price:
                entry_price = sniper_entry
                sl_price = entry_price + safety_sl_dist
                # [FIX POINT 2]: TP dihitung dari ENTRY BARU - (ATR * Multiplier)
                tp_price = entry_price - (atr * config.ATR_MULTIPLIER_TP1)
                order_type = 'limit'
                print(f"🔫 SNIPER SHORT: Entry moved to Retail SL @ {entry_price}")

    return { 
        "entry_price": entry_price, 
        "sl": sl_price, 
        "tp1": tp_price, 
        "side_api": side_api, 
        "type": order_type,
        "tech_info": tech_info 
    }

async def analisa_market_hybrid(coin_config):
    symbol = coin_config['symbol']
    now = time.time()
    
    if symbol in SYMBOL_COOLDOWN and now < SYMBOL_COOLDOWN[symbol]: return
    base_sym = symbol.split('/')[0]
    
    # Cek cache posisi (jangan entry kalau sudah punya posisi)
    is_in_position = False
    async with data_lock:
        if base_sym in position_cache_ws: is_in_position = True
    if is_in_position: return 

    # --- 1. SIAPKAN DATA ---
    try:
        async with data_lock:
            if symbol not in market_data_store: return
            bars_5m = market_data_store[symbol].get(config.TIMEFRAME_EXEC, [])
            bars_h1 = market_data_store[symbol].get(config.BTC_TIMEFRAME, []) 
        
        if len(bars_5m) < config.EMA_SLOW + 2 or len(bars_h1) < config.EMA_TREND_MAJOR + 2: return

        # --- [FIX POINT 3]: FILTER TREND MAJOR (H1 COIN) ---
        # Backtest menggunakan EMA 50 di Timeframe 1H untuk filter bias koin
        df_h1 = pd.DataFrame(bars_h1, columns=['timestamp','open','high','low','close','volume'])
        df_h1['EMA_MAJOR'] = df_h1.ta.ema(length=config.EMA_TREND_MAJOR)
        
        # Trend H1 Coin (Confirmed Candle / iloc[-1] aman utk H1 karena update lama)
        trend_major_val = df_h1['EMA_MAJOR'].iloc[-1] 
        price_h1_now = df_h1['close'].iloc[-1]
        is_coin_uptrend_h1 = price_h1_now > trend_major_val
        
        # --- 2. ANALISA TIMEFRAME EKSEKUSI (5m) ---
        df = pd.DataFrame(bars_5m, columns=['timestamp','open','high','low','close','volume'])
        
        df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
        df['ADX'] = df.ta.adx(length=config.ADX_PERIOD)[f"ADX_{config.ADX_PERIOD}"]
        df['RSI'] = df.ta.rsi(length=14)
        df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)
        df['VOL_MA'] = df['volume'].rolling(window=config.VOL_MA_PERIOD).mean()
        
        bb = df.ta.bbands(length=config.BB_LENGTH, std=config.BB_STD)
        df['BBL'] = bb[f'BBL_{config.BB_LENGTH}_{config.BB_STD}']
        df['BBU'] = bb[f'BBU_{config.BB_LENGTH}_{config.BB_STD}']
        
        stoch = df.ta.stochrsi(length=config.STOCHRSI_LEN, rsi_length=config.STOCHRSI_LEN, k=config.STOCHRSI_K, d=config.STOCHRSI_D)
        df['STOCH_K'] = stoch.iloc[:, 0] 

        # --- [FIX POINT 4]: GUNAKAN ILOC[-2] (CANDLE CLOSE) ---
        # Backtest logic selalu melihat candle yg baru saja close
        confirm = df.iloc[-2] 
        
        price_now = confirm['close']
        ema_fast_m5 = confirm['EMA_FAST'] # EMA Fast pada candle close
        
        signal = None
        strategy_type = "NONE"

        # FILTER ARAH BERDASARKAN BTC TREND (GLOBAL)
        allowed_signal = "BOTH"
        if symbol != config.BTC_SYMBOL:
            if btc_trend_direction == "BULLISH": allowed_signal = "LONG_ONLY"
            elif btc_trend_direction == "BEARISH": allowed_signal = "SHORT_ONLY"

        # --- STRATEGI A: TREND TRAP (PULLBACK) ---
        if config.USE_TREND_TRAP_STRATEGY and confirm['ADX'] > config.TREND_TRAP_ADX_MIN:
            
            # CEK LONG (Trend H1 Naik + M5 Koreksi)
            if (allowed_signal in ["LONG_ONLY", "BOTH"]) and is_coin_uptrend_h1:
                
                # [FIX POINT 5]: LOGIKA PULLBACK ZONE
                # 1. Harga Close < EMA Fast (Menunjukkan koreksi/pullback)
                # 2. Harga Close > BB Lower (Belum jebol BB bawah, masih wajar)
                is_pullback_valid = (price_now < ema_fast_m5) and (price_now > confirm['BBL'])
                
                if is_pullback_valid:
                    if config.TREND_TRAP_RSI_LONG_MIN <= confirm['RSI'] <= config.TREND_TRAP_RSI_LONG_MAX:
                        signal = "LONG"
                        strategy_type = "TREND_PULLBACK"

            # CEK SHORT (Trend H1 Turun + M5 Koreksi Naik)
            elif (allowed_signal in ["SHORT_ONLY", "BOTH"]) and (not is_coin_uptrend_h1):
                
                # [FIX POINT 5]: LOGIKA PULLBACK ZONE SELL
                # 1. Harga Close > EMA Fast (Menunjukkan koreksi naik sementara)
                # 2. Harga Close < BB Upper (Belum jebol BB atas)
                is_pullback_valid_sell = (price_now > ema_fast_m5) and (price_now < confirm['BBU'])
                
                if is_pullback_valid_sell:
                    if config.TREND_TRAP_RSI_SHORT_MIN <= confirm['RSI'] <= config.TREND_TRAP_RSI_SHORT_MAX:
                        signal = "SHORT"
                        strategy_type = "TREND_PULLBACK"

        # --- STRATEGI B: SIDEWAYS SCALP (BB BOUNCE) ---
        elif config.USE_SIDEWAYS_SCALP and confirm['ADX'] < config.SIDEWAYS_ADX_MAX and signal is None:
            
            # BB Bounce Bottom (Long)
            if price_now <= confirm['BBL'] and confirm['STOCH_K'] < config.STOCH_OVERSOLD:
                if (allowed_signal in ["LONG_ONLY", "BOTH"]): 
                    signal = "LONG"
                    strategy_type = "BB_BOUNCE_BOTTOM"
            
            # BB Bounce Top (Short)
            elif price_now >= confirm['BBU'] and confirm['STOCH_K'] > config.STOCH_OVERBOUGHT:
                if (allowed_signal in ["SHORT_ONLY", "BOTH"]): 
                    signal = "SHORT"
                    strategy_type = "BB_BOUNCE_TOP"

        if signal:
            print(f"💎 SIGNAL (MATCHED): {symbol} {signal} | Str: {strategy_type}")
            
            tech_info = {
                "adx": confirm['ADX'],
                "rsi": confirm['RSI'],
                "stoch_k": confirm['STOCH_K'],
                "vol_valid": confirm['volume'] > confirm['VOL_MA'],
                "btc_trend": btc_trend_direction,
                "strategy": strategy_type,
                "price_vs_ema": "Above" if price_now > confirm['EMA_FAST'] else "Below"
            }
            
            params = calculate_trade_parameters(signal, df, symbol, strategy_type, tech_info) 
            await execute_order(symbol, params['side_api'], params, strategy_type, coin_config)

    except Exception as e:
        logger.error(f"Error Analisa Hybrid {symbol}: {e}") 

# GANTI FUNGSI execute_order DENGAN INI AGAR NOTIF LENGKAP:
async def execute_order(symbol, side, params, strategy, coin_cfg):
    try:
        # 1. Bersihkan order lama
        try:
            await exchange.cancel_all_orders(symbol)
        except: pass

        # 2. Setup Leverage & Margin
        leverage = coin_cfg.get('leverage', config.DEFAULT_LEVERAGE)
        amount = coin_cfg.get('amount', config.DEFAULT_AMOUNT_USDT)
        margin_type = coin_cfg.get('margin_type', config.DEFAULT_MARGIN_TYPE)
        if margin_type not in ['isolated', 'cross']: margin_type = config.DEFAULT_MARGIN_TYPE
        
        try:
            await exchange.set_leverage(leverage, symbol)
            await exchange.set_margin_mode(margin_type, symbol)
        except: pass

        logger.info(f"🚀 PREPARING ORDER: {symbol} | Side: {side} | Strat: {strategy} | Price: {params['entry_price']}")

        # 3. Hitung Quantity
        qty = (amount * leverage) / params['entry_price']
        qty = exchange.amount_to_precision(symbol, qty)
        
        # 4. Eksekusi Order (Limit/Market)
        order = None
        if params['type'] == 'limit':
            order = await exchange.create_order(symbol, 'limit', side, qty, params['entry_price'])
            logger.info(f"✅ LIMIT PLACED: {symbol} | ID: {order['id']}")
            
            # Update Tracker ke WAITING_ENTRY
            safety_orders_tracker[symbol] = {
                "status": "WAITING_ENTRY",
                "entry_id": str(order['id']),
                "created_at": time.time(),
                "strategy": strategy
            }
            save_tracker()
        else:
            order = await exchange.create_order(symbol, 'market', side, qty)
            logger.info(f"✅ MARKET FILLED: {symbol} | Qty: {qty}")
        
        # 5. Set Cooldown
        SYMBOL_COOLDOWN[symbol] = time.time() + config.COOLDOWN_PER_SYMBOL_SECONDS
        
        # --- 6. FORMAT NOTIFIKASI TELEGRAM (YANG DIPERBAIKI) ---
        try:
            rr_ratio = round(abs(params['tp1'] - params['entry_price']) / abs(params['entry_price'] - params['sl']), 2)
        except: rr_ratio = 0
        
        icon_side = "🟢 LONG" if side == 'buy' else "🔴 SHORT"
        
        # Ambil data tech_info yang dikirim dari analisa
        ti = params.get('tech_info', {})
        
        # Format Data Indikator (Restored)
        vol_status = "✅ High" if ti.get('vol_valid') else "⚠️ Low"
        btc_t = ti.get('btc_trend', 'NEUTRAL')
        btc_icon = "🟢" if btc_t == "BULLISH" else ("🔴" if btc_t == "BEARISH" else "⚪")
        ema_pos = ti.get('price_vs_ema', '-')
        ema_icon = "📈" if ema_pos == "Above" else "📉"

        tech_detail = (
            f"• <b>BTC Trend:</b> {btc_icon} {btc_t}\n"
            f"• <b>Price vs EMA:</b> {ema_icon} {ema_pos}\n"
            f"• <b>ADX:</b> {ti.get('adx', 0):.1f} | <b>RSI:</b> {ti.get('rsi', 0):.1f}\n"
            f"• <b>Stoch K:</b> {ti.get('stoch_k', 0):.1f}\n"
            f"• <b>Volume:</b> {vol_status}"
        )

        msg = (
            f"🎯 <b>NEW SETUP ({strategy})</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>{symbol}</b> | {icon_side}\n"
            f"📊 Type: {params['type'].upper()} ({margin_type} x{leverage})\n"
            f"💵 Entry: {params['entry_price']}\n"
            f"🛡️ SL: {params['sl']} | 💰 TP: {params['tp1']}\n"
            f"⚖️ R:R: 1:{rr_ratio}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🧠 <b>TECHNICAL INSIGHT:</b>\n{tech_detail}"
        )
        await kirim_tele(msg)
        
    except Exception as e:
        logger.error(f"❌ Order Failed {symbol}: {e}", exc_info=True)
        await kirim_tele(f"⚠️ <b>ORDER ERROR</b>\n{symbol}: {e}", alert=True)

# ==========================================
# SAFETY MONITOR (ANTI-GHOST & RECOVERY)
# ==========================================
async def install_safety_orders(symbol, pos_data):
    entry_price = float(pos_data['entryPrice'])
    quantity = float(pos_data['contracts'])
    side = pos_data['side']
    
    try:
        async with data_lock:
            bars = market_data_store.get(symbol, {}).get(config.TIMEFRAME_EXEC, [])
        if not bars: 
            atr = entry_price * 0.01 
        else:
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            atr = df.ta.atr(length=config.ATR_PERIOD).iloc[-1]
    except: atr = entry_price * 0.01
    
    sl_dist = atr * config.ATR_MULTIPLIER_SL
    tp_dist = atr * config.ATR_MULTIPLIER_TP1
    
    # Override logic jika menggunakan mode Sniper/Trap (ATR Trap Safety mungkin beda)
    # Namun untuk Safety Monitor (posisi sudah jalan), kita pakai ATR Multiplier Standard untuk SL
    # Atau sesuaikan dengan logic config.TRAP_SAFETY_SL jika ingin konsisten dengan Sniper
    if config.USE_LIQUIDITY_HUNT:
        sl_dist = atr * getattr(config, 'TRAP_SAFETY_SL', 1.0)

    if side == "LONG":
        sl_price, tp_price = entry_price - sl_dist, entry_price + tp_dist
        side_api = 'sell'
    else:
        sl_price, tp_price = entry_price + sl_dist, entry_price - tp_dist
        side_api = 'buy'
        
    p_sl = exchange.price_to_precision(symbol, sl_price)
    p_tp = exchange.price_to_precision(symbol, tp_price)
    qty_final = exchange.amount_to_precision(symbol, quantity)

    for attempt in range(config.ORDER_SLTP_RETRIES):
        try:
            o_sl = await exchange.create_order(symbol, 'STOP_MARKET', side_api, qty_final, None, {'stopPrice': p_sl, 'workingType': 'MARK_PRICE', 'reduceOnly': True})
            o_tp = await exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side_api, qty_final, None, {'stopPrice': p_tp, 'workingType': 'CONTRACT_PRICE', 'reduceOnly': True})
            
            logger.info(f"✅ SAFETY ORDERS PLACED: {symbol}")
            msg = (f"🛡️ <b>SAFETY SECURED</b>\nCoin: <b>{symbol}</b>\n✅ SL Set: {p_sl}\n✅ TP Set: {p_tp}")
            await kirim_tele(msg)
            return [str(o_sl['id']), str(o_tp['id'])]
        except Exception as e:
            logger.warning(f"⚠️ Safety Retry {attempt+1} Failed {symbol}: {e}")
            await asyncio.sleep(config.ORDER_SLTP_RETRY_DELAY)
    
    logger.error(f"❌ SAFETY FAILED {symbol} after retries!", exc_info=True)
    return []

async def safety_monitor_hybrid():
    global safety_orders_tracker
    while True:
        try:
            now = time.time()
            async with data_lock:
                current_positions = dict(position_cache_ws)
            
            for base_sym, pos_data in current_positions.items():
                symbol = pos_data['symbol']
                current_status = safety_orders_tracker.get(symbol, {}).get("status", "NONE")
                
                if current_status == "NONE" or current_status == "PENDING":
                    print(f"🛡️ Installing Safety for: {symbol}")
                    safety_orders_tracker[symbol] = {"status": "PROCESSING", "last_check": now}
                    order_ids = await install_safety_orders(symbol, pos_data)
                    if order_ids:
                        safety_orders_tracker[symbol] = {"status": "SECURED", "order_ids": order_ids, "last_check": now}
                        save_tracker()
                    else:
                        safety_orders_tracker[symbol] = {"status": "PENDING", "last_check": now}
            
            # CHECK GHOST ORDERS
            active_trackers = list(safety_orders_tracker.items())
            for sym, tracker in active_trackers:
                if tracker.get("status") == "SECURED":
                    last_check = tracker.get("last_check", 0)
                    if (now - last_check) > 300: # 5 Menit Verification
                        try:
                            open_orders = await exchange.fetch_open_orders(sym)
                            real_ids = [str(o['id']) for o in open_orders]
                            tracked_ids = tracker.get("order_ids", [])
                            still_active = any(tid in real_ids for tid in tracked_ids)
                            if not still_active:
                                print(f"⚠️ GHOST ORDER DETECTED: {sym}. Resetting tracker.")
                                del safety_orders_tracker[sym] 
                            else:
                                safety_orders_tracker[sym]['last_check'] = now
                        except Exception as e: pass
            
            save_tracker()
            await asyncio.sleep(5) 
        except Exception as e:
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)

# ==========================================
# MAIN LOOP
# ==========================================
async def main():
    global exchange
    
    exchange = ccxt.binance({
        'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
        'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
        'options': {'defaultType': 'future'}
    })
    if config.PAKAI_DEMO: exchange.enable_demo_trading(True)

    await kirim_tele("🤖 <b>BOT STARTED (FINAL FIXED VERSION)</b>\nLogic aligned 1:1 with Backtest", alert=True)

    try:
        load_tracker()
        await initialize_market_data()
        await fetch_existing_positions() 
        await install_safety_for_existing_positions()
        
        ws_manager = BinanceWSManager(exchange)
        asyncio.create_task(ws_manager.start_stream())
        asyncio.create_task(safety_monitor_hybrid())
        
        print("🚀 BOT RUNNING (FULL STRATEGY + RECOVERY + VERIFICATION)...")
        
        while True:
            try:
                tasks = [analisa_market_hybrid(koin) for koin in config.DAFTAR_KOIN]
                await asyncio.gather(*tasks)
                await asyncio.sleep(1) 
            except asyncio.CancelledError: raise 
            except Exception: await asyncio.sleep(config.ERROR_SLEEP_DELAY)

    except KeyboardInterrupt:
        print("\n👋 Bot dimatikan manual.")
    except Exception as e:
        logger.error(f"Bot Crash: {e}", exc_info=True)
    finally:
        print("🔌 Closing connection...")
        try: await exchange.close()
        except: pass
        print("✅ Shutdown Complete.")

if __name__ == "__main__":
    asyncio.run(main())