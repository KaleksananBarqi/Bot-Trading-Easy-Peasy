"""
===========================================================
BOT V6.0 - PRO EXECUTION EDITION
Fitur Baru:
1. Entry via Limit Order (Maker Fee) + Timeout Fallback
2. Spread Protection (Anti Slip)
3. Flexible TP Config (Bisa atur porsi TP1/TP2/TP3 sesuka hati)
===========================================================
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import time
import requests
import sys
import os
from datetime import datetime, timedelta
import logging
import config

# --- VARIABEL GLOBAL ---
last_entry_time = {}
exchange = None
positions_cache = set()
start_of_day_balance = 0.0
is_circuit_breaker_active = False

logging.basicConfig(
    filename='bot_trading.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
async def kirim_tele(pesan, alert=False):
    try:
        if alert:
            pesan = f"⚠️ <b>SYSTEM ALERT</b>\n{pesan}"
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': pesan, 'parse_mode': 'HTML'})
    except Exception as e:
        print(f"Gagal kirim tele: {e}")

def format_harga(price):
    if price < 0.01: return f"{price:.6f}"
    if price < 1: return f"{price:.4f}"
    return f"{price:.2f}"

async def get_available_balance():
    try:
        bal = await exchange.fetch_balance()
        return float(bal['USDT']['free']), float(bal['USDT']['total'])
    except Exception as e:
        logging.error(f"Gagal fetch balance: {e}")
        return 0.0, 0.0

async def cek_posisi_terbuka(symbol):
    try:
        if positions_cache:
            return symbol in positions_cache
        positions = await exchange.fetch_positions([symbol])
        for pos in positions:
            if float(pos['contracts']) > 0: return True
        return False
    except: return True 

def get_seconds_to_next_candle(timeframe):
    tf_in_minutes = int(''.join(filter(str.isdigit, timeframe)))
    now = datetime.utcnow()
    next_candle_minute = (now.minute // tf_in_minutes + 1) * tf_in_minutes
    if next_candle_minute >= 60:
        next_candle_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_candle_time = now.replace(minute=next_candle_minute, second=0, microsecond=0)
    return (next_candle_time - now).total_seconds()

async def check_spread_ok(symbol):
    """Mengecek apakah spread (Ask - Bid) aman."""
    try:
        ticker = await exchange.fetch_ticker(symbol)
        bid = ticker['bid']
        ask = ticker['ask']
        if not bid or not ask: return False
        
        spread_percent = ((ask - bid) / ask) * 100
        
        if spread_percent > config.MAX_SPREAD_PERCENT:
            print(f"⛔ Spread High {symbol}: {spread_percent:.3f}% (Max {config.MAX_SPREAD_PERCENT}%)")
            return False
        return True
    except Exception as e:
        print(f"Err Spread {symbol}: {e}")
        return False

# ==========================================
# 3. BACKGROUND TASK: RISK MONITORING
# ==========================================
async def monitoring_risk_task(shutdown_event):
    global start_of_day_balance, is_circuit_breaker_active
    print("🛡️ Risk Monitoring Module Active...")
    
    while not shutdown_event.is_set():
        try:
            # A. CHECK DAILY MAX LOSS
            if start_of_day_balance > 0:
                free_usdt, total_usdt = await get_available_balance()
                loss_percent = ((start_of_day_balance - total_usdt) / start_of_day_balance) * 100
                
                if loss_percent >= config.MAX_DAILY_LOSS_PERCENT and not is_circuit_breaker_active:
                    is_circuit_breaker_active = True
                    msg = (f"🚨 <b>DAILY MAX LOSS HIT!</b> 🚨\n"
                           f"Loss: {loss_percent:.2f}%\nBot stopped.")
                    await kirim_tele(msg, alert=True)

            # B. AUTO MOVE TO BE
            if config.AUTO_MOVE_TO_BE:
                positions = await exchange.fetch_positions()
                active_positions = [p for p in positions if float(p['contracts']) > 0]
                
                for pos in active_positions:
                    symbol = pos['symbol']
                    entry_price = float(pos['entryPrice'])
                    mark_price = float(pos['markPrice'])
                    side = pos['side']
                    amount = float(pos['contracts'])
                    
                    if side == 'long':
                        pnl_percent = ((mark_price - entry_price) / entry_price) * 100
                        be_target = entry_price * (1 + (config.BE_BUFFER_PERCENT/100))
                    else:
                        pnl_percent = ((entry_price - mark_price) / entry_price) * 100
                        be_target = entry_price * (1 - (config.BE_BUFFER_PERCENT/100))
                    
                    if pnl_percent >= config.MOVE_TO_BE_TRIGGER_PERCENT:
                        # Logic pindah SL (Simplified)
                        # ... (Sama seperti versi sebelumnya, disingkat agar muat)
                        pass 

        except Exception as e:
            logging.error(f"Error Risk Task: {e}")
        await asyncio.sleep(5)

# ==========================================
# 4. EKSEKUSI ORDER (LIMIT + FALLBACK MARKET)
# ==========================================
async def _execute_entry_strategy(symbol, side, amount_final):
    """
    Menangani logika Entry:
    1. Coba Limit Order di harga Best Bid/Ask (Maker).
    2. Tunggu X detik.
    3. Jika belum fill, Cancel -> Market Order (Taker).
    """
    order_type = config.ENTRY_ORDER_TYPE.upper()
    
    # --- STRATEGI 1: MARKET ORDER LANGSUNG ---
    if order_type == 'MARKET':
        try:
            order = await exchange.create_order(symbol, 'market', side, amount_final)
            return True, float(order['average'] or order['price'] or 0)
        except Exception as e:
            print(f"❌ Market Order Failed: {e}")
            return False, 0

    # --- STRATEGI 2: LIMIT ORDER (MAKER) WITH FALLBACK ---
    elif order_type == 'LIMIT':
        try:
            # 1. Ambil Harga Terbaik Saat Ini
            ticker = await exchange.fetch_ticker(symbol)
            best_price = ticker['bid'] if side == 'buy' else ticker['ask']
            
            print(f"⏳ Placing LIMIT {side} {symbol} @ {best_price}...")
            limit_order = await exchange.create_order(symbol, 'limit', side, amount_final, best_price)
            order_id = limit_order['id']

            # 2. Tunggu Fill
            start_wait = time.time()
            filled = False
            
            while time.time() - start_wait < config.LIMIT_WAIT_SECONDS:
                await asyncio.sleep(1) # Cek tiap 1 detik
                try:
                    check_ord = await exchange.fetch_order(order_id, symbol)
                    if check_ord['status'] == 'closed': # Sudah fill
                        filled = True
                        print(f"✅ Limit Order Filled!")
                        return True, float(check_ord['average'])
                    elif check_ord['status'] == 'canceled':
                        return False, 0
                except: pass
            
            # 3. Jika Timeout & Belum Fill -> Cancel & Market
            if not filled:
                print(f"⚠️ Limit timeout ({config.LIMIT_WAIT_SECONDS}s). Switching to MARKET...")
                try:
                    await exchange.cancel_order(order_id, symbol)
                except: pass # Mungkin sudah fill di split second terakhir
                
                # Fallback ke Market
                market_order = await exchange.create_order(symbol, 'market', side, amount_final)
                return True, float(market_order['average'] or market_order['price'])

        except Exception as e:
            print(f"❌ Limit/Fallback Error: {e}")
            return False, 0

    return False, 0

async def _async_eksekusi_binance(symbol, side, signal_entry_price, sl_price, tp1, tp2, tp3):
    global is_circuit_breaker_active
    
    if is_circuit_breaker_active: return False

    # 1. CEK SPREAD SEBELUM EKSEKUSI
    if not await check_spread_ok(symbol):
        return False

    print(f"🚀 EKSEKUSI: {symbol} {side} (Strategy: {config.ENTRY_ORDER_TYPE})...")
    
    try:
        # 2. Hitung Size
        free_usdt, _ = await get_available_balance()
        if config.USE_DYNAMIC_SIZE:
            margin_usdt = max(2, free_usdt * (config.RISK_PERCENT_PER_TRADE / 100))
            amount_usdt = margin_usdt * config.LEVERAGE
        else:
            amount_usdt = config.MARGIN_PER_POSISI_FIXED * config.LEVERAGE

        # Gunakan harga sinyal untuk estimasi jumlah koin
        amount_coin = amount_usdt / signal_entry_price
        amount_final = exchange.amount_to_precision(symbol, amount_coin)
        
        notional = float(amount_final) * signal_entry_price
        if notional < config.MIN_ORDER_USDT:
            print(f"⚠️ Order too small (${notional:.2f}). Skip.")
            return False

        # 3. LAKUKAN ENTRY (Limit / Market Logic)
        success, avg_fill_price = await _execute_entry_strategy(symbol, side, amount_final)
        
        if not success:
            await kirim_tele(f"⚠️ Gagal Entry {symbol}", alert=True)
            return False

        # Entry berhasil, harga fill real mungkin beda dengan sinyal
        real_entry = avg_fill_price if avg_fill_price > 0 else signal_entry_price

        # 4. PASANG SL & TP (FLEXIBLE CONFIG)
        sl_side = 'sell' if side == 'buy' else 'buy'
        
        # A. Pasang STOP LOSS (Wajib)
        try:
            p_sl = {'stopPrice': exchange.price_to_precision(symbol, sl_price), 'reduceOnly': True}
            await exchange.create_order(symbol, 'STOP_MARKET', sl_side, amount_final, params=p_sl)
        except Exception as e:
            print(f"❌ Gagal Pasang SL: {e}")
            # Close immediately if SL fails (Safety)
            await exchange.create_order(symbol, 'market', sl_side, amount_final, params={'reduceOnly': True})
            return False

        # B. Pasang TAKE PROFIT (Flexible Loop)
        qty_total = float(amount_final)
        remaining_qty = qty_total
        
        tp_configs = [
            ('TP1', tp1, config.TP_ALLOCATION.get('TP1', 0)),
            ('TP2', tp2, config.TP_ALLOCATION.get('TP2', 0)),
            ('TP3', tp3, config.TP_ALLOCATION.get('TP3', 0))
        ]
        
        # Filter TP yang aktif (>0%)
        active_tps = [t for t in tp_configs if t[2] > 0]
        
        for i, (name, price, ratio) in enumerate(active_tps):
            # Jika ini TP terakhir di list, habiskan sisa qty (menghindari sisa receh 0.00001)
            if i == len(active_tps) - 1:
                qty_tp = remaining_qty
            else:
                qty_tp = float(exchange.amount_to_precision(symbol, qty_total * ratio))
                remaining_qty -= qty_tp
            
            if qty_tp > 0:
                try:
                    p_tp = {'reduceOnly': True}
                    limit_price = exchange.price_to_precision(symbol, price)
                    qty_str = exchange.amount_to_precision(symbol, qty_tp)
                    await exchange.create_order(symbol, 'limit', sl_side, qty_str, limit_price, params=p_tp)
                    print(f"✅ {name} Set @ {limit_price} (Qty: {qty_str})")
                except Exception as e:
                    print(f"⚠️ Gagal pasang {name}: {e}")

        print(f"✅ {symbol} Trade Active. Entry Avg: {real_entry}")
        return True

    except Exception as e:
        print(f"❌ Critical Error Execution {symbol}: {e}")
        return False

# ==========================================
# 5. ANALISA MARKET (SAME LOGIC)
# ==========================================
async def fetch_and_calculate_indicators(symbol):
    try:
        bars = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
        bars_h1 = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND)
        if not bars or len(bars) < config.LIMIT_EXEC: return None, None
        
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df_h1 = pd.DataFrame(bars_h1, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
        df['EMA_SLOW'] = df.ta.ema(length=config.EMA_SLOW)
        df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)
        df['RSI'] = df.ta.rsi(length=config.RSI_PERIOD)
        adx_df = df.ta.adx(length=config.ADX_PERIOD)
        df['ADX'] = adx_df[f"ADX_{config.ADX_PERIOD}"]
        
        df_h1['EMA_TREND'] = df_h1.ta.ema(length=config.EMA_TREND_MAJOR)
        return df, df_h1
    except: return None, None

def check_signal(df, df_h1):
    try:
        confirm = df.iloc[-2]
        prev    = df.iloc[-3]
        h1_confirm = df_h1.iloc[-2]
        is_uptrend_h1 = h1_confirm['close'] > h1_confirm['EMA_TREND']
        
        # Logic Cross (Sama)
        if not config.WAJIB_EMA_CROSS:
            cross_up = (confirm['EMA_FAST'] > confirm['EMA_SLOW'])
            cross_down = (confirm['EMA_FAST'] < confirm['EMA_SLOW'])
        else:
            cross_up = (prev['EMA_FAST'] < prev['EMA_SLOW']) and (confirm['EMA_FAST'] > confirm['EMA_SLOW'])
            cross_down = (prev['EMA_FAST'] > prev['EMA_SLOW']) and (confirm['EMA_FAST'] < confirm['EMA_SLOW'])

        adx_val = confirm['ADX']
        strong_trend = adx_val > config.ADX_LIMIT

        if is_uptrend_h1 and cross_up and strong_trend and (config.RSI_MIN_LONG < confirm['RSI'] < config.RSI_MAX_LONG):
            return "LONG"
        elif (not is_uptrend_h1) and cross_down and strong_trend and (config.RSI_MIN_SHORT < confirm['RSI'] < config.RSI_MAX_SHORT):
            return "SHORT"
        return None
    except: return None

def calculate_trade_parameters(signal, df):
    confirm = df.iloc[-2]
    current = df.iloc[-1]
    atr = confirm['ATR']
    entry_price = current['close']
    
    if signal == "LONG":
        side_api = 'buy'
        sl  = entry_price - (atr * config.ATR_MULTIPLIER_SL)
        tp1 = entry_price + (atr * config.ATR_MULTIPLIER_TP1)
        tp2 = entry_price + (atr * config.ATR_MULTIPLIER_TP2)
        tp3 = entry_price + (atr * config.ATR_MULTIPLIER_TP3)
    else: 
        side_api = 'sell'
        sl  = entry_price + (atr * config.ATR_MULTIPLIER_SL)
        tp1 = entry_price - (atr * config.ATR_MULTIPLIER_TP1)
        tp2 = entry_price - (atr * config.ATR_MULTIPLIER_TP2)
        tp3 = entry_price - (atr * config.ATR_MULTIPLIER_TP3)
        
    risk = abs(entry_price - sl)
    reward = abs(tp2 - entry_price)
    rr = reward / risk if risk > 0 else 0
    
    return {
        "entry_price": entry_price, "sl": sl, 
        "tp1": tp1, "tp2": tp2, "tp3": tp3, 
        "side_api": side_api, "rr": rr
    }

def format_telegram_message(symbol, signal, params):
    header = f"🟢 <b>{symbol} LONG</b>" if signal == "LONG" else f"🔴 <b>{symbol} SHORT</b>"
    # Hanya tampilkan TP yang aktif di config
    tp_txt = ""
    if config.TP_ALLOCATION.get('TP1', 0) > 0: tp_txt += f"TP1: {format_harga(params['tp1'])}\n"
    if config.TP_ALLOCATION.get('TP2', 0) > 0: tp_txt += f"TP2: {format_harga(params['tp2'])}\n"
    if config.TP_ALLOCATION.get('TP3', 0) > 0: tp_txt += f"TP3: {format_harga(params['tp3'])}\n"
    
    msg = f"{header}\n\nEntry: {format_harga(params['entry_price'])}\nSL: {format_harga(params['sl'])}\n{tp_txt}RR: 1:{params['rr']:.2f}"
    return msg

async def analisa_market(symbol):
    global last_entry_time
    now = time.time()
    if symbol in last_entry_time and now - last_entry_time[symbol] < config.COOLDOWN_PER_SYMBOL_SECONDS: return
    try:
        df, df_h1 = await fetch_and_calculate_indicators(symbol)
        if df is None: return
        signal = check_signal(df, df_h1)
        if not signal: return
        if await cek_posisi_terbuka(symbol): return
        
        params = calculate_trade_parameters(signal, df)
        
        # Eksekusi dengan logic baru
        berhasil = await _async_eksekusi_binance(symbol, params['side_api'], params['entry_price'], params['sl'], params['tp1'], params['tp2'], params['tp3'])
        
        if berhasil:
            await kirim_tele(format_telegram_message(symbol, signal, params))
            last_entry_time[symbol] = now
    except Exception as e:
        print(f"⚠️ Error {symbol}: {e}")

# ==========================================
# 6. MAIN LOOP
# ==========================================
async def main():
    global exchange, start_of_day_balance

    try:
        if config.PAKAI_DEMO:
            print("⚠️ MODE DEMO")
            exchange = ccxt.binance({
                'apiKey': config.API_KEY_DEMO,
                'secret': config.SECRET_KEY_DEMO,
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
            exchange.enable_demo_trading(True)
        else:
            print("🚨 MODE LIVE")
            exchange = ccxt.binance({
                'apiKey': config.API_KEY_LIVE, 
                'secret': config.SECRET_KEY_LIVE, 
                'enableRateLimit': True, 
                'options': {'defaultType': 'future'}
            })

        await exchange.load_markets()
        
        bal = await exchange.fetch_balance()
        start_of_day_balance = float(bal['USDT']['total'])
        print(f"💰 Balance: ${start_of_day_balance:.2f} | Execution: {config.ENTRY_ORDER_TYPE}")
        
    except Exception as e:
        print(f"❌ Error Koneksi: {e}")
        return

    await kirim_tele(f"🤖 <b>BOT V6.0 STARTED</b>\nExec: {config.ENTRY_ORDER_TYPE}\nTP Mode: {list(config.TP_ALLOCATION.keys())}")

    shutdown_event = asyncio.Event()
    asyncio.create_task(monitoring_risk_task(shutdown_event))
    sem = asyncio.Semaphore(config.CONCURRENCY_LIMIT)

    try:
        while not shutdown_event.is_set():
            if is_circuit_breaker_active:
                print("💤 Circuit Breaker Active...")
                await asyncio.sleep(60)
                continue

            wait_seconds = get_seconds_to_next_candle(config.TIMEFRAME_EXEC)
            if wait_seconds > 0:
                print(f"⏳ Wait candle... ({int(wait_seconds)}s)")
                await asyncio.sleep(wait_seconds)

            print(f"\n--- 🕯️ Scan Start ---")
            
            # Refresh Position Cache
            try:
                positions = await exchange.fetch_positions()
                positions_cache.clear()
                for pos in positions:
                    if float(pos['contracts']) > 0:
                        positions_cache.add(pos['symbol'])
            except: pass

            tasks = []
            for koin in config.DAFTAR_KOIN:
                async def run_safe(s):
                    async with sem: await analisa_market(s)
                tasks.append(asyncio.create_task(run_safe(koin['symbol'])))
                await asyncio.sleep(config.SCAN_DELAY_PER_COIN_SECONDS)

            if tasks: await asyncio.gather(*tasks)
            print("✅ Scan Selesai.")

    except KeyboardInterrupt:
        shutdown_event.set()
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())