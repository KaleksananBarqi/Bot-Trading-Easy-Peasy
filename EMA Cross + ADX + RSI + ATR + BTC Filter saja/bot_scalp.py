import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import time
import requests
import sys
import os
import logging
import config 

# --- LOGGING & GLOBALS ---
last_entry_time = {}
exchange = None
positions_cache = set()
global_btc_trend = "NEUTRAL"
last_btc_check = 0

logging.basicConfig(filename='bot_trading.log', level=logging.INFO, format='%(asctime)s - %(message)s')

async def kirim_tele(pesan, alert=False):
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{prefix}{pesan}", 'parse_mode': 'HTML'})
    except Exception as e: print(f"Tele error: {e}")

# ==========================================
# 0. SETUP AWAL (CUSTOM PER KOIN)
# ==========================================
async def setup_account_settings():
    """Mengatur Leverage dan Margin Mode spesifik untuk SETIAP koin."""
    print("⚙️ Menerapkan Custom Leverage & Margin Mode...")
    await kirim_tele("⚙️ <b>Setup Awal:</b> Mengatur Custom Config per Koin...")
    
    count = 0
    for koin in config.DAFTAR_KOIN:
        symbol = koin['symbol']
        # Ambil settingan dari config, atau pakai default jika lupa ditulis
        lev = koin.get('leverage', config.DEFAULT_LEVERAGE)
        marg_type = koin.get('margin_type', config.DEFAULT_MARGIN_TYPE)

        try:
            # Set Leverage
            await exchange.set_leverage(lev, symbol)
            # Set Margin Mode (Isolated/Cross)
            try:
                await exchange.set_margin_mode(marg_type, symbol)
            except Exception:
                pass # Abaikan jika sudah terset atau ada posisi
            
            print(f"   🔹 {symbol}: Lev {lev}x | {marg_type}")
            count += 1
            if count % 5 == 0: await asyncio.sleep(0.5) 
        except Exception as e:
            logging.error(f"Gagal seting {symbol}: {e}")
            print(f"❌ Gagal seting {symbol}: {e}")
    
    print("✅ Setup Selesai.")
    await kirim_tele("✅ <b>Setup Selesai.</b> Bot siap berjalan.")

async def update_btc_trend():
    """Mengecek Trend BTC Global"""
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
# 1. EKSEKUSI (CUSTOM AMOUNT)
# ==========================================
async def _async_eksekusi_binance(symbol, side, entry_price, sl_price, tp1, coin_config):
    print(f"🚀 MARKET ENTRY: {symbol} {side}...")
    try:
        # 1. Ambil settingan khusus koin ini
        my_leverage = coin_config.get('leverage', config.DEFAULT_LEVERAGE)
        my_margin_usdt = coin_config.get('amount', config.DEFAULT_AMOUNT_USDT)

        # 2. Hitung Quantity
        # Rumus: (Margin * Leverage) / Harga
        amount_coin = (my_margin_usdt * my_leverage) / entry_price
        amount_final = exchange.amount_to_precision(symbol, amount_coin)

        # Cek Minimum Order Binance (biasanya min $5 notional)
        notional_value = float(amount_final) * entry_price
        if notional_value < config.MIN_ORDER_USDT:
            print(f"⚠️ Order {symbol} terlalu kecil (${notional_value:.2f}). Skip.")
            return False

        # 3. Eksekusi Entry
        await exchange.create_order(symbol, 'market', side, amount_final)

        # 4. Polling Posisi
        pos_found = False
        for _ in range(config.POSITION_POLL_RETRIES):
            positions = await exchange.fetch_positions([symbol])
            if any(float(p.get('contracts', 0)) > 0 for p in positions):
                pos_found = True; break
            await asyncio.sleep(config.POSITION_POLL_DELAY)

        if not pos_found: return False

        # 5. Pasang SL & TP
        sl_side = 'sell' if side == 'buy' else 'buy'
        for attempt in range(1, config.ORDER_SLTP_RETRIES + 1):
            try:
                params_sl = {'stopPrice': exchange.price_to_precision(symbol, sl_price), 'reduceOnly': True}
                await exchange.create_order(symbol, 'STOP_MARKET', sl_side, amount_final, params=params_sl)
                
                params_tp = {'stopPrice': exchange.price_to_precision(symbol, tp1), 'reduceOnly': True}
                await exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', sl_side, amount_final, params=params_tp)
                
                print(f"✅ {symbol} SL/TP Installed (Margin: ${my_margin_usdt}, Lev: {my_leverage}x)")
                return True
            except Exception as e:
                logging.warning(f"Retry {attempt} SL/TP {symbol}: {e}")
                await asyncio.sleep(config.ORDER_SLTP_RETRY_DELAY)

        return False
    except Exception as e:
        logging.error(f"Error Eksekusi {symbol}: {e}")
        return False

# ==========================================
# 2. ANALISA
# ==========================================
def calculate_trade_parameters(signal, df):
    current = df.iloc[-1]
    atr = df.iloc[-2]['ATR']
    entry_price = current['close']
    
    if signal == "LONG":
        sl = entry_price - (atr * config.ATR_MULTIPLIER_SL)
        tp1 = entry_price + (atr * config.ATR_MULTIPLIER_TP1)
        side_api = 'buy'
    else:
        sl = entry_price + (atr * config.ATR_MULTIPLIER_SL)
        tp1 = entry_price - (atr * config.ATR_MULTIPLIER_TP1)
        side_api = 'sell'

    return {"entry_price": entry_price, "sl": sl, "tp1": tp1, "side_api": side_api}

async def analisa_market(coin_config, btc_trend_status):
    # Kita butuh 'coin_config' dict secara utuh
    symbol = coin_config['symbol']
    
    now = time.time()
    if symbol in last_entry_time and (now - last_entry_time[symbol] < config.COOLDOWN_PER_SYMBOL_SECONDS): return

    # --- FILTER BTC LOGIC ---
    allowed_signal = "BOTH"
    if symbol != config.BTC_SYMBOL:
        if btc_trend_status == "BULLISH": allowed_signal = "LONG_ONLY"
        elif btc_trend_status == "BEARISH": allowed_signal = "SHORT_ONLY"

    try:
        bars = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
        bars_h1 = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND)
        if not bars or not bars_h1: return

        df = pd.DataFrame(bars, columns=['time','open','high','low','close','volume'])
        df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
        df['EMA_SLOW'] = df.ta.ema(length=config.EMA_SLOW)
        df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)
        df['RSI'] = df.ta.rsi(length=config.RSI_PERIOD)
        df['ADX'] = df.ta.adx(length=config.ADX_PERIOD)[f"ADX_{config.ADX_PERIOD}"]
        
        df_h1 = pd.DataFrame(bars_h1, columns=['time','open','high','low','close','volume'])
        ema_trend = df_h1.ta.ema(length=config.EMA_TREND_MAJOR).iloc[-2]

        confirm = df.iloc[-2]
        is_uptrend = confirm['close'] > ema_trend
        
        signal = None
        
        if (allowed_signal in ["LONG_ONLY", "BOTH"]) and is_uptrend and (confirm['EMA_FAST'] > confirm['EMA_SLOW']) and (confirm['ADX'] > config.ADX_LIMIT):
            if config.RSI_MIN_LONG < confirm['RSI'] < config.RSI_MAX_LONG: 
                signal = "LONG"
        elif (allowed_signal in ["SHORT_ONLY", "BOTH"]) and not is_uptrend and (confirm['EMA_FAST'] < confirm['EMA_SLOW']) and (confirm['ADX'] > config.ADX_LIMIT):
            if config.RSI_MIN_SHORT < confirm['RSI'] < config.RSI_MAX_SHORT: 
                signal = "SHORT"

        if signal:
            if symbol in positions_cache: return
            
            print(f"🎯 Sinyal {symbol} {signal} (BTC: {btc_trend_status})")

            params = calculate_trade_parameters(signal, df)
            # PASSING 'coin_config' ke fungsi eksekusi agar tahu marginnya berapa
            berhasil = await _async_eksekusi_binance(symbol, params['side_api'], params['entry_price'], params['sl'], params['tp1'], coin_config)
            
            if berhasil:
                lev = coin_config.get('leverage', config.DEFAULT_LEVERAGE)
                amt = coin_config.get('amount', config.DEFAULT_AMOUNT_USDT)
                msg = f"{'🟢' if signal=='LONG' else '🔴'} <b>{symbol} {signal}</b>\nLev: {lev}x | Margin: ${amt}\nEntry: {params['entry_price']}\nSL: {params['sl']:.4f}\nTP: {params['tp1']:.4f}"
                await kirim_tele(msg)
                last_entry_time[symbol] = now
    except Exception as e: logging.error(f"Analisa error {symbol}: {e}")

# ==========================================
# 3. LOOP UTAMA
# ==========================================
async def main():
    global exchange, positions_cache, global_btc_trend
    
    # Init Exchange
    params = {'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
              'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
              'enableRateLimit': True, 'options': {'defaultType': 'future'}}
    exchange = ccxt.binance(params)
    if config.PAKAI_DEMO: exchange.enable_demo_trading(True)

    await kirim_tele("🚀 <b>BOT STARTED</b>\nFitur: Multi-Config per Coin & BTC Filter")
    
    # SETUP AWAL
    await setup_account_settings()

    while True:
        try:
            pos = await exchange.fetch_positions()
            positions_cache = {p['symbol'].split(':')[0] for p in pos if float(p.get('contracts', 0)) > 0}
            
            btc_trend = await update_btc_trend()
            
            # Perhatikan: Kita kirim seluruh object dict 'k' ke analisa
            tasks = [analisa_market(k, btc_trend) for k in config.DAFTAR_KOIN]
            await asyncio.gather(*tasks)
            
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())