
import asyncio
import json
import time
import numpy as np
import pandas as pd
import pandas_ta as ta
import ccxt.async_support as ccxt
import websockets
import config
from collections import deque
from typing import NamedTuple
from scipy.signal import argrelextrema
from src.utils.helper import logger, kirim_tele, wib_time, parse_timeframe_to_seconds

# --- NAMED TUPLES FOR TYPE SAFETY ---

class Candle(NamedTuple):
    """Represents a single OHLCV candle with named fields for clarity."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

# --- STATIC CALCULATION FUNCTIONS (Thread-Safe) ---

def _calculate_pivot_points_static(bars):
    """Calculate Classic Pivot Points based on provided bars list"""
    try:
        if len(bars) < 2: return None

        # Gunakan candle terakhir yang COMPLETE (Completed Period)
        # [-1] adalah candle berjalan (unconfirmed), [-2] adalah candle terakhir yang close
        # Unpack into NamedTuple for clarity and type safety
        prev = Candle(*bars[-2])
        high = prev.high
        low = prev.low
        close = prev.close

        # Classic Pivot Formula
        pivot = (high + low + close) / 3
        r1 = (2 * pivot) - low
        s1 = (2 * pivot) - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)

        return {
            "P": pivot,
            "R1": r1,
            "S1": s1,
            "R2": r2,
            "S2": s2
        }
    except Exception as e:
        logger.error(f"Pivot calc error: {e}")
        return None

def _calculate_market_structure_static(bars, lookback=5):
    """
    Mendeteksi Market Structure (Higher High/Lower Low).
    Menggunakan scipy.signal.argrelextrema.
    """
    try:
        if len(bars) < config.MIN_BARS_MARKET_STRUCTURE: return "INSUFFICIENT_DATA"

        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])

        # Vektorisasi menggunakan scipy.signal.argrelextrema
        high_vals = df['high'].values
        low_vals = df['low'].values

        # Cari indeks swing high/low (order=lookback -> cek N candle kiri & kanan)
        swing_high_idx = argrelextrema(high_vals, np.greater_equal, order=lookback)[0]
        swing_low_idx = argrelextrema(low_vals, np.less_equal, order=lookback)[0]

        # Exclude candle terakhir (current open) dari hasil
        # Dengan menfilter indeks yang >= len(df) - lookback - 1
        max_valid_idx = len(df) - lookback - 1
        swing_high_idx = swing_high_idx[swing_high_idx < max_valid_idx]
        swing_low_idx = swing_low_idx[swing_low_idx < max_valid_idx]

        # Ambil nilai dari indeks yang valid
        swing_highs = high_vals[swing_high_idx].tolist() if len(swing_high_idx) > 0 else []
        swing_lows = low_vals[swing_low_idx].tolist() if len(swing_low_idx) > 0 else []

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "UNCLEAR"

        # Analisa 2 Swing Terakhir
        last_h = swing_highs[-1]
        prev_h = swing_highs[-2]
        last_l = swing_lows[-1]
        prev_l = swing_lows[-2]

        structure = "SIDEWAYS"

        if last_h > prev_h and last_l > prev_l:
            structure = "BULLISH (HH + HL)"
        elif last_h < prev_h and last_l < prev_l:
            structure = "BEARISH (LH + LL)"
        elif last_h > prev_h and last_l < prev_l:
            structure = "EXPANDING (Megaphone)"
        elif last_h < prev_h and last_l > prev_l:
            structure = "CONSOLIDATION (Triangle)"

        return structure

    except Exception as e:
        logger.error(f"Market Structure Error: {e}")
        return "ERROR"

def _calculate_wick_rejection_static(bars, lookback=5, df=None):
    """
    Mendeteksi candle dengan wick besar sebagai tanda rejection.
    
    Args:
        bars: List of OHLCV bars
        lookback: Number of candles to analyze
        df: Optional pre-existing DataFrame (to avoid redundant creation)
    """
    try:
        if not bars or len(bars) < lookback:
            return {"recent_rejection": "NONE", "rejection_strength": 0.0}

        # Analyze last N candles
        start_idx = -1 - lookback
        end_idx = -1

        # Check length again to be safe
        if len(bars) < lookback + 2:
            candidates = bars[:-1] # take all available closed
        else:
            candidates = bars[start_idx:end_idx]

        # Use provided DataFrame or create new one
        # candidates format: [timestamp, open, high, low, close, volume]
        if df is not None and len(df) >= len(candidates):
            local_df = df.iloc[start_idx:end_idx].copy()
        else:
            local_df = pd.DataFrame(candidates, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calculate wicks and body
        local_df['body'] = (local_df['close'] - local_df['open']).abs()
        local_df['upper_wick'] = local_df['high'] - local_df[['open', 'close']].max(axis=1)
        local_df['lower_wick'] = local_df[['open', 'close']].min(axis=1) - local_df['low']
        
        # Handle division by zero
        local_df['body_ref'] = local_df['body'].where(local_df['body'] > 0, (local_df['high'] - local_df['low']) * config.WICK_REJECTION_MIN_BODY_RATIO)
        local_df['body_ref'] = local_df['body_ref'].where(local_df['body_ref'] > 0, config.WICK_REJECTION_MIN_BODY_REF)
        
        # Logic: Wick must be > 2x Body
        local_df['is_bullish'] = local_df['lower_wick'] > (local_df['body'] * config.WICK_REJECTION_MULTIPLIER)
        local_df['is_bearish'] = local_df['upper_wick'] > (local_df['body'] * config.WICK_REJECTION_MULTIPLIER)
        
        # Calculate strength
        local_df['strength_bull'] = local_df['lower_wick'] / local_df['body_ref']
        local_df['strength_bear'] = local_df['upper_wick'] / local_df['body_ref']
        
        # Count rejections
        rejection_count = local_df['is_bullish'].sum() + local_df['is_bearish'].sum()
        
        # Find max strength for each type
        max_bull = local_df.loc[local_df['is_bullish'], 'strength_bull'].max() if local_df['is_bullish'].any() else 0.0
        max_bear = local_df.loc[local_df['is_bearish'], 'strength_bear'].max() if local_df['is_bearish'].any() else 0.0
        
        # Determine final rejection type (strongest wins)
        if max_bull > max_bear and max_bull > 0:
            rejection_type = "BULLISH_REJECTION"
            max_strength = max_bull
        elif max_bear > 0:
            rejection_type = "BEARISH_REJECTION"
            max_strength = max_bear
        else:
            rejection_type = "NONE"
            max_strength = 0.0

        return {
            "recent_rejection": rejection_type,
            "rejection_strength": round(max_strength, 2),
            "rejection_candles": int(rejection_count)
        }

    except Exception as e:
        logger.error(f"Wick Rejection Calc Error: {e}")
        return {"recent_rejection": "ERROR", "rejection_strength": 0.0}


def _prepare_dataframe(bars):
    """
    Prepare DataFrame from OHLCV bars.
    
    Args:
        bars: List of [timestamp, open, high, low, close, volume]
    
    Returns:
        pd.DataFrame with columns: timestamp, open, high, low, close, volume
    """
    return pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])


def _calculate_ema_indicators(df):
    """
    Calculate EMA Fast and Slow indicators.
    Adds EMA_FAST and EMA_SLOW columns to DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
    """
    df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
    df['EMA_SLOW'] = df.ta.ema(length=config.EMA_SLOW)


def _calculate_momentum_indicators(df):
    """
    Calculate momentum indicators: RSI, ADX, and Stochastic RSI.
    Adds RSI, ADX, STOCH_K, and STOCH_D columns to DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
    """
    # RSI & ADX
    df['RSI'] = df.ta.rsi(length=config.RSI_PERIOD)
    adx_result = df.ta.adx(length=config.ADX_PERIOD)
    df['ADX'] = adx_result[f"ADX_{config.ADX_PERIOD}"]
    
    # Stochastic RSI
    stoch_rsi = df.ta.stochrsi(
        length=config.STOCHRSI_LEN,
        rsi_length=config.RSI_PERIOD,
        k=config.STOCHRSI_K,
        d=config.STOCHRSI_D
    )
    k_key = f"STOCHRSIk_{config.STOCHRSI_LEN}_{config.RSI_PERIOD}_{config.STOCHRSI_K}_{config.STOCHRSI_D}"
    d_key = f"STOCHRSId_{config.STOCHRSI_LEN}_{config.RSI_PERIOD}_{config.STOCHRSI_K}_{config.STOCHRSI_D}"
    df['STOCH_K'] = stoch_rsi[k_key]
    df['STOCH_D'] = stoch_rsi[d_key]


def _calculate_volatility_indicators(df):
    """
    Calculate volatility indicators: Bollinger Bands and ATR.
    Adds BB_UPPER, BB_LOWER, and ATR columns to DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
    """
    # Bollinger Bands
    bb = df.ta.bbands(length=config.BB_LENGTH, std=config.BB_STD)
    if bb is not None:
        df['BB_LOWER'] = bb.iloc[:, 0]
        df['BB_UPPER'] = bb.iloc[:, 2]
    
    # ATR (For Liquidity Hunt)
    df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)


def _calculate_volume_indicators(df):
    """
    Calculate volume indicator: Volume MA.
    Adds VOL_MA column to DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
    """
    df['VOL_MA'] = df.ta.sma(close='volume', length=config.VOL_MA_PERIOD)


def _calculate_trend_state(cur_row):
    """
    Calculate trend state based on current row values.
    
    Args:
        cur_row: Series representing current candle data
    
    Returns:
        dict with 'price_vs_ema' and 'trend_major' keys
    """
    return {
        'price_vs_ema': "Above" if cur_row['close'] > cur_row['EMA_FAST'] else "Below",
        'trend_major': "Bullish" if cur_row['close'] > cur_row['EMA_SLOW'] else "Bearish"
    }


def _calculate_global_trend(bars_trend, symbol):
    """
    Calculate global trend (1D timeframe) for AI filter.
    
    Args:
        bars_trend: List of OHLCV bars from trend timeframe
        symbol: Trading symbol for error logging
    
    Returns:
        str: "BULLISH", "BEARISH", or "NEUTRAL"
    """
    if len(bars_trend) <= config.EMA_TREND_MAJOR:
        return "NEUTRAL"
    
    try:
        df_trend = _prepare_dataframe(bars_trend)
        ema_major_series = df_trend.ta.ema(length=config.EMA_TREND_MAJOR)
        
        # Get last closed candle (index -2, -1 is current forming)
        if len(df_trend) >= 2:
            idx = -2
            price_1d = df_trend['close'].iloc[idx]
            ema_1d = ema_major_series.iloc[idx]
            
            if pd.notna(ema_1d):
                return "BULLISH" if price_1d > ema_1d else "BEARISH"
    except Exception as e:
        logger.error(f"Global Trend Calc Warning {symbol}: {e}")
    
    return "NEUTRAL"


def _assemble_tech_data(cur_row, trend_state, pivots, structure, wick_rejection, global_trend):
    """
    Assemble all technical data into result dictionary.
    
    Args:
        cur_row: Series with current candle indicator values
        trend_state: dict with price_vs_ema and trend_major
        pivots: Pivot points data
        structure: Market structure data
        wick_rejection: Wick rejection analysis data
        global_trend: Global trend direction string
    
    Returns:
        dict: Complete technical data dictionary
    """
    return {
        "price": cur_row['close'],
        "rsi": cur_row['RSI'],
        "adx": cur_row['ADX'],
        "ema_fast": cur_row['EMA_FAST'],
        "ema_slow": cur_row['EMA_SLOW'],
        "vol_ma": cur_row['VOL_MA'],
        "volume": cur_row['volume'],
        "bb_upper": cur_row['BB_UPPER'],
        "bb_lower": cur_row['BB_LOWER'],
        "stoch_k": cur_row['STOCH_K'],
        "stoch_d": cur_row['STOCH_D'],
        "atr": cur_row['ATR'],
        "price_vs_ema": trend_state['price_vs_ema'],
        "trend_major": trend_state['trend_major'],
        "pivots": pivots,
        "market_structure": structure,
        "wick_rejection": wick_rejection,
        "global_trend_1d": global_trend,
        "candle_timestamp": int(cur_row['timestamp']),
        "last_candle": {
            "open": cur_row['open'],
            "high": cur_row['high'],
            "low": cur_row['low'],
            "close": cur_row['close'],
            "timestamp": int(cur_row['timestamp'])
        }
    }


def _calculate_tech_data_threaded(bars_exec, bars_trend, symbol):
    """
    Heavy Calculation Logic (Pandas/TA) to be run in a separate thread.
    Takes Lists of bars (snapshots), not Deques.
    
    Refactored to use helper functions for better maintainability and testability.
    """
    try:
        # 1. Validate input data
        if len(bars_exec) < config.EMA_SLOW + 5:
            return None

        # 2. Prepare DataFrame
        df = _prepare_dataframe(bars_exec)

        # 3. Calculate all technical indicators
        _calculate_ema_indicators(df)
        _calculate_momentum_indicators(df)
        _calculate_volatility_indicators(df)
        _calculate_volume_indicators(df)

        # 4. Get current (confirmed) candle
        cur = df.iloc[-2]

        # 5. Calculate trend state
        trend_state = _calculate_trend_state(cur)

        # 6. Calculate external analyses
        pivots = _calculate_pivot_points_static(bars_trend)
        structure = _calculate_market_structure_static(bars_trend)
        wick_rejection = _calculate_wick_rejection_static(bars_exec, df=df)
        global_trend = _calculate_global_trend(bars_trend, symbol)

        # 7. Assemble final result
        return _assemble_tech_data(cur, trend_state, pivots, structure, wick_rejection, global_trend)

    except Exception as e:
        logger.error(f"Threaded Calc Error {symbol}: {e}")
        return None


class MarketDataManager:
    def __init__(self, exchange):
        self.exchange = exchange
        self.exchange_public = None # [NEW] Untuk fetch data public di mode testnet
        
        self.market_store = {} # OHLCV Data
        self.ticker_data = {}  # Live Price / Ticker
        self.funding_rates = {} 
        self.open_interest = {}
        self.lsr_data = {} # Top Trader Long/Short Ratio
        
        self.btc_trend = "NEUTRAL"
        self.data_lock = asyncio.Lock()
        self.sem_slow_data = asyncio.Semaphore(config.CONCURRENCY_LIMIT)
        
        self.ws_url = config.WS_URL_FUTURES_TESTNET if config.PAKAI_DEMO else config.WS_URL_FUTURES_LIVE
        self.listen_key = None
        self.last_heartbeat = time.time()
        
        # [NEW] Initialize Public Exchange if Demo Mode
        if config.PAKAI_DEMO:
            # Kita butuh akses ke Data LIVE untuk L/S Ratio karena tidak ada di Testnet
            self.exchange_public = ccxt.binance({
                'options': {'defaultType': 'future'}
            })
        
        # Initialize Store Structure with Deque
        for coin in config.DAFTAR_KOIN:
            self.market_store[coin['symbol']] = {
                config.TIMEFRAME_EXEC: deque(maxlen=config.LIMIT_EXEC),
                config.TIMEFRAME_TREND: deque(maxlen=config.LIMIT_TREND),
                config.TIMEFRAME_SETUP: deque(maxlen=config.LIMIT_SETUP)
            }
        # BTC (Wajib ada helper store)
        if config.BTC_SYMBOL not in self.market_store:
            self.market_store[config.BTC_SYMBOL] = {
                config.TIMEFRAME_EXEC: deque(maxlen=config.LIMIT_EXEC),
                config.TIMEFRAME_TREND: deque(maxlen=config.LIMIT_TREND),
                config.TIMEFRAME_SETUP: deque(maxlen=config.LIMIT_SETUP)
            }
        
        # Cache for Technical Data to avoid redundant recalculation
        self.tech_cache = {} # {symbol: {ts, data}}

        # Cache for Order Book Analysis to avoid spamming API if managed differently
        self.ob_cache = {} # {symbol: {ts, data}}

    async def _fetch_lsr(self, symbol):
        """Helper Fetch LSR dengan Fallback ke Public Exchange jika Demo"""
        try:
            target_exchange = self.exchange
            # Jika di mode demo, gunakan exchange public (karena lsr gak ada di testnet)
            if config.PAKAI_DEMO and self.exchange_public:
                target_exchange = self.exchange_public
                
            clean_sym = symbol.replace('/', '')
            lsr = await target_exchange.fapiDataGetTopLongShortAccountRatio({
                'symbol': clean_sym,
                'period': config.TIMEFRAME_EXEC,
                'limit': 1
            })
            if lsr and len(lsr) > 0:
                return lsr[0]
            return None
        except Exception as e:

            # Fallback silently or log if critical
            return None

    async def initialize_data(self):
        """Fetch Initial Historical Data (REST API)"""
        logger.info("📥 Initializing Market Data...")
        tasks = []
        
        async def fetch_pair(symbol):
            try:
                # 1. Fetch OHLCV
                bars_exec_raw = await self.exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
                bars_trend_raw = await self.exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND)
                bars_setup_raw = await self.exchange.fetch_ohlcv(symbol, config.TIMEFRAME_SETUP, limit=config.LIMIT_SETUP)

                # Convert to Deque
                bars_exec = deque(bars_exec_raw, maxlen=config.LIMIT_EXEC)
                bars_trend = deque(bars_trend_raw, maxlen=config.LIMIT_TREND)
                bars_setup = deque(bars_setup_raw, maxlen=config.LIMIT_SETUP)
                
                # 2. Fetch Funding Rate & Open Interest (Public Endpoint)
                # Note: CCXT fetch_funding_rate usually works
                fund_rate = await self.exchange.fetch_funding_rate(symbol)
                # Open Interest (CCXT)
                try:
                    oi_data = await self.exchange.fetch_open_interest(symbol)
                    oi_val = float(oi_data.get('openInterestAmount', 0))
                except ccxt.BaseError:
                    oi_val = 0.0

                # We will update these via Rest mostly or WS if available
                
                # 3. Initial LSR (Refactored to Helper)
                lsr_val = await self._fetch_lsr(symbol)

                async with self.data_lock:
                    self.market_store[symbol][config.TIMEFRAME_EXEC] = bars_exec
                    self.market_store[symbol][config.TIMEFRAME_TREND] = bars_trend
                    self.market_store[symbol][config.TIMEFRAME_SETUP] = bars_setup
                    self.funding_rates[symbol] = fund_rate.get('fundingRate', 0)
                    self.open_interest[symbol] = oi_val
                    self.lsr_data[symbol] = lsr_val
                
                logger.info(f"   ✅ Data Loaded: {symbol}")
            except Exception as e:
                logger.error(f"   ❌ Failed Load {symbol}: {e}")

        # Batch fetch
        for coin in config.DAFTAR_KOIN:
            tasks.append(fetch_pair(coin['symbol']))
            
        if not any(k['symbol'] == config.BTC_SYMBOL for k in config.DAFTAR_KOIN):
             tasks.append(fetch_pair(config.BTC_SYMBOL))
             
        await asyncio.gather(*tasks)
        self._update_btc_trend()

    def _update_btc_trend(self):
        """Update Global BTC Trend Direction"""
        try:
            bars = self.market_store[config.BTC_SYMBOL][config.TIMEFRAME_TREND]
            if bars:
                df_btc = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                ema_btc = df_btc.ta.ema(length=config.BTC_EMA_PERIOD).iloc[-1]
                price_now = df_btc['close'].iloc[-1]
                
                new_trend = "BULLISH" if price_now > ema_btc else "BEARISH"
                if new_trend != self.btc_trend:
                    logger.info(f"👑 BTC TREND CHANGE: {self.btc_trend} -> {new_trend}")
                    self.btc_trend = new_trend
        except Exception as e:
            logger.error(f"Error BTC Trend Calc: {e}")

    # --- WEBSOCKET LOGIC ---
    async def get_listen_key(self):
        try:
            response = await self.exchange.fapiPrivatePostListenKey()
            self.listen_key = response['listenKey']
            return self.listen_key
        except Exception as e:
            logger.error(f"❌ Gagal ListenKey: {e}")
            return None

    async def start_stream(self, callback_account_update=None, callback_order_update=None, callback_whale=None, callback_trailing=None):
        """Main WebSocket Loop"""
        while True:
            await self.get_listen_key()
            if not self.listen_key:
                await asyncio.sleep(5)
                continue
                
            streams = [self.listen_key]
            # Add Kline Streams & MiniTicker
            for coin in config.DAFTAR_KOIN:
                s_clean = coin['symbol'].replace('/', '').lower()
                streams.append(f"{s_clean}@kline_{config.TIMEFRAME_EXEC}")
                streams.append(f"{s_clean}@kline_{config.TIMEFRAME_TREND}")
                streams.append(f"{s_clean}@kline_{config.TIMEFRAME_SETUP}")
                streams.append(f"{s_clean}@aggTrade") # Whale Detector Stream
                streams.append(f"{s_clean}@miniTicker") # [NEW] Realtime Price for Trailing
                streams.append(f"{s_clean}@depth20@500ms") # [NEW] Order Book Cache Stream

            # Add BTC Stream manual if not exists
            btc_clean = config.BTC_SYMBOL.replace('/', '').lower()
            btc_s = f"{btc_clean}@kline_{config.TIMEFRAME_TREND}"
            if btc_s not in streams: streams.append(btc_s)

            # [NEW] Force BTC Whale Stream for Context (Global Whale Data)
            btc_whale_stream = f"{btc_clean}@aggTrade"
            if btc_whale_stream not in streams:
                streams.append(btc_whale_stream)
                # logger.info("🐋 BTC Whale Stream Subscribed (Context Only)")

            url = self.ws_url + "/".join(streams)
            logger.info(f"📡 Connecting WS... ({len(streams)} streams)")
            
            # Keep Alive Task from Config
            asyncio.create_task(self._keep_alive_listen_key())
            
            # [NEW] Background Task untuk Data Lambat (Funding Rate & OI)
            asyncio.create_task(self._maintain_slow_data())

            try:
                async with websockets.connect(url) as ws:
                    logger.info("✅ WebSocket Connected!")
                    await kirim_tele("✅ <b>WebSocket System Online</b>")
                    self.last_heartbeat = time.time()
                    
                    while True:
                        msg = await ws.recv()
                        self.last_heartbeat = time.time()
                        data = json.loads(msg)
                        
                        if 'data' in data:
                            payload = data['data']
                            evt = payload.get('e', '')
                            
                            if evt == 'kline':
                                await self._handle_kline(payload)
                            elif evt == 'ACCOUNT_UPDATE' and callback_account_update:
                                await callback_account_update(payload)
                            elif evt == 'ORDER_TRADE_UPDATE' and callback_order_update:
                                await callback_order_update(payload)
                            elif evt == 'aggTrade' and callback_whale:
                                # "s": "BTCUSDT", "p": "0.001", "q": "100", "m": true
                                symbol = payload['s'].replace('USDT', '/USDT')
                                price = float(payload['p'])
                                qty = float(payload['q'])
                                amount_usdt = price * qty
                                side = "SELL" if payload['m'] else "BUY" # m=True means the maker was a buyer, so the aggressor was a seller (SELL trade).
                                if amount_usdt >= config.WHALE_THRESHOLD_USDT:
                                    callback_whale(symbol, amount_usdt, side)
                            
                            elif evt == '24hrMiniTicker':
                                # [NEW] Realtime Price Handler for Trailing Stop
                                # Payload: {"e":"24hrMiniTicker","E":167233,"s":"BTCUSDT","c":"1234.56",...}
                                symbol = payload['s'].replace('USDT', '/USDT')
                                price = float(payload['c']) # Current Close Price
                                
                                if callback_trailing:
                                    # Use fire-and-forget task
                                    asyncio.create_task(self._safe_callback_execution(callback_trailing, symbol, price))

                            elif evt == 'depthUpdate':
                                await self._handle_depth_update(payload)
                                
            except Exception as e:
                logger.warning(f"⚠️ WS Disconnected: {e}. Reconnecting...")
                await asyncio.sleep(5)

    async def _maintain_slow_data(self):
        """
        Background task untuk update data yang tidak perlu real-time (Funding Rate & Open Interest).
        Interval: Mengikuti config.TIMEFRAME_EXEC.
        """
        interval = parse_timeframe_to_seconds(config.TIMEFRAME_EXEC)
        logger.info(f"🐢 Slow Data Maintenance Started (Interval: {interval}s)")
        
        while True:
            await asyncio.sleep(interval)
            try:
                # 1. Bulk Update Funding Rates
                await self._update_funding_rates_bulk()

                # 2. Parallel Update for Open Interest & LSR (No Bulk API available)
                tasks = [self._update_single_coin_slow_data(coin) for coin in config.DAFTAR_KOIN]
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.error(f"Slow Data Loop Error: {e}")

    async def _update_funding_rates_bulk(self):
        """Fetch all funding rates in a single request (Optimization)"""
        try:
            # fetch_funding_rates returns a dict {symbol: {info...}, ...}
            all_rates = await self.exchange.fetch_funding_rates()

            # Filter only monitored coins
            monitored_symbols = {c['symbol'] for c in config.DAFTAR_KOIN}

            async with self.data_lock:
                for symbol, data in all_rates.items():
                    if symbol in monitored_symbols:
                        self.funding_rates[symbol] = data.get('fundingRate', 0)

        except Exception as e:
            logger.error(f"Failed Bulk Funding Rate Update: {e}")

    async def _update_single_coin_slow_data(self, coin):
        """Helper to update slow data for a single coin concurrently (OI & LSR)"""
        symbol = coin['symbol']
        async with self.sem_slow_data:
            try:
                # Parallel fetch: Open Interest, LSR (Funding Rate moved to bulk)
                results = await asyncio.gather(
                    self.exchange.fetch_open_interest(symbol),
                    self._fetch_lsr(symbol),
                    return_exceptions=True
                )

                oi_res, lsr_res = results

                # Process results safely
                oi_val = 0.0
                if not isinstance(oi_res, Exception):
                    try:
                        oi_val = float(oi_res.get('openInterestAmount', 0))
                    except (ValueError, TypeError):
                        oi_val = 0.0

                lsr_val = None
                if not isinstance(lsr_res, Exception):
                    lsr_val = lsr_res

                # Single lock acquisition for updates
                async with self.data_lock:
                    if not isinstance(oi_res, Exception):
                        self.open_interest[symbol] = oi_val
                    if lsr_val:
                        self.lsr_data[symbol] = lsr_val

            except Exception as e:
                # Log debug only to avoid spam
                # logger.debug(f"Failed updating slow data for {symbol}: {e}")
                pass

    async def _keep_alive_listen_key(self):
        while True:
            await asyncio.sleep(config.WS_KEEP_ALIVE_INTERVAL)
            try:
                await self.exchange.fapiPrivatePutListenKey({'listenKey': self.listen_key})
            except ccxt.NetworkError as e:
                logger.debug(f"Keep alive listen key failed: {e}")

    async def _safe_callback_execution(self, callback, *args):
        """Helper to safely run callbacks without crashing the loop"""
        try:
            await callback(*args)
        except Exception as e:
            logger.error(f"Error in trailing callback: {e}")

    async def _handle_kline(self, data):
        sym = data['s'].replace('USDT', '/USDT')
        k = data['k']
        interval = k['i']
        new_candle = [int(k['t']), float(k['o']), float(k['h']), float(k['l']), float(k['c']), float(k['v'])]
        
        async with self.data_lock:
            if sym in self.market_store:
                target = self.market_store[sym].get(interval)
                if target is not None:
                    if target and target[-1][0] == new_candle[0]:
                        target[-1] = new_candle
                    else:
                        target.append(new_candle)
                        # Deque handles popping automatically
                else:
                    # Fallback for unexpected interval
                    self.market_store[sym][interval] = deque([new_candle], maxlen=config.LIMIT_TREND)
        
        # Update BTC Trend Realtime
        if sym == config.BTC_SYMBOL and interval == config.TIMEFRAME_TREND:
            self._update_btc_trend()

    async def _handle_depth_update(self, payload):
        """
        Handle WebSocket Partial Depth Update (depth20)
        Payload: {e: depthUpdate, s: BTCUSDT, b: [[p, q], ...], a: [[p, q], ...]}
        """
        try:
            symbol = payload['s'].replace('USDT', '/USDT')

            # Convert strings to floats
            # WS sends ["price", "qty"] as strings
            bids = [[float(p), float(q)] for p, q in payload['b']]
            asks = [[float(p), float(q)] for p, q in payload['a']]

            # Update Cache (Overwrite is fine for partial depth stream)
            # No lock needed for simple dict replacement, but good practice if structure is complex.
            # Here we just replace the reference.
            self.ob_cache[symbol] = {
                'bids': bids,
                'asks': asks,
                'ts': time.time()
            }
        except Exception as e:
            logger.debug(f"Depth Update Error: {e}")

    async def get_btc_correlation(self, symbol, period=config.CORRELATION_PERIOD):
        """Hitung korelasi Close price simbol vs BTC (Timeframe 1H)"""
        try:
            if symbol == config.BTC_SYMBOL: return 1.0
            
            bars_sym = self.market_store.get(symbol, {}).get(config.TIMEFRAME_TREND, [])
            bars_btc = self.market_store.get(config.BTC_SYMBOL, {}).get(config.TIMEFRAME_TREND, [])
            
            if len(bars_sym) < period or len(bars_btc) < period:
                return config.DEFAULT_CORRELATION_HIGH # Default high correlation to be safe (Follow BTC)
            
            # Create DF
            df_sym = pd.DataFrame(bars_sym, columns=['timestamp','o','h','l','c','v'])
            df_btc = pd.DataFrame(bars_btc, columns=['timestamp','o','h','l','c','v'])
            
            # Merge on timestamp to align candles
            merged = pd.merge(df_sym[['timestamp','c']], df_btc[['timestamp','c']], on='timestamp', suffixes=('_sym', '_btc'))
            
            if len(merged) < period:
                return config.DEFAULT_CORRELATION_HIGH
                
            # Calc Correlation
            corr = merged['c_sym'].rolling(period).corr(merged['c_btc']).iloc[-1]
            
            if pd.isna(corr): return 0.0
            return corr
            
        except Exception as e:
            logger.error(f"Corr Error {symbol}: {e}")
            return config.DEFAULT_CORRELATION_HIGH # Fallback

    async def get_technical_data(self, symbol):
        """Retrieve aggregated technical data for AI Prompt"""
        try:
            # 1. Snapshot Data (Thread-Safe Preparation)
            # Avoid accessing self.market_store inside the thread.
            # Convert deque to list to ensure we have a static copy.
            bars_exec = list(self.market_store.get(symbol, {}).get(config.TIMEFRAME_EXEC, []))
            bars_trend = list(self.market_store.get(symbol, {}).get(config.TIMEFRAME_TREND, []))

            if len(bars_exec) < config.EMA_SLOW + 5: return None
            
            # Determine last closed candle timestamp (bars[-2])
            last_closed_ts = bars_exec[-2][0]
            
            # Check Cache
            cached = self.tech_cache.get(symbol)
            if cached and cached.get('timestamp') == last_closed_ts:
                # Cache Hit - Use static data
                tech_data = cached['data']
            else:
                # Cache Miss - Offload to Thread
                # Run the heavy calculation in a separate thread to avoid blocking the event loop
                tech_data = await asyncio.to_thread(
                    _calculate_tech_data_threaded,
                    bars_exec,
                    bars_trend,
                    symbol
                )

                if tech_data:
                    # Update Cache
                    self.tech_cache[symbol] = {
                        'timestamp': last_closed_ts,
                        'data': tech_data
                    }
                else:
                    return None

            # 9. Return Combined Data (Static + Dynamic)
            # Dynamic fields: btc_trend, funding_rate, open_interest, lsr
            result = tech_data.copy()
            result.update({
                "btc_trend": self.btc_trend,
                "funding_rate": self.funding_rates.get(symbol, 0),
                "open_interest": self.open_interest.get(symbol, 0.0),
                "lsr": self.lsr_data.get(symbol)
            })

            return result
        except Exception as e:
            logger.error(f"Get Tech Data Error {symbol}: {e}")
            return None

    async def get_order_book_depth(self, symbol, limit=20):
        """
        Fetch Order Book and calculate imbalance within 2% range.
        Return: {bids_vol_usdt, asks_vol_usdt, imbalance_pct}
        """
        try:
            bids = []
            asks = []

            # 1. Try Cache First (Zero Latency)
            cached = self.ob_cache.get(symbol)
            if cached:
                bids = cached['bids']
                asks = cached['asks']
            else:
                # 2. Fallback to API (Network Latency)
                # This happens only at startup before first WS message arrives
                ob = await self.exchange.fetch_order_book(symbol, limit)
                bids = ob['bids']
                asks = ob['asks']
            
            if not bids or not asks: return None
            
            mid_price = (bids[0][0] + asks[0][0]) / 2
            
            # Filter Range from Config
            range_limit = config.ORDERBOOK_RANGE_PERCENT
            
            bids_vol = 0
            for price, qty in bids:
                if price < mid_price * (1 - range_limit): break
                bids_vol += price * qty
                
            asks_vol = 0
            for price, qty in asks:
                if price > mid_price * (1 + range_limit): break
                asks_vol += price * qty
                
            total_vol = bids_vol + asks_vol
            if total_vol == 0: return None
            
            imbalance = ((bids_vol - asks_vol) / total_vol) * 100 # Positive = Bullish (More Bids)
            
            return {
                "bids_vol_usdt": bids_vol,
                "asks_vol_usdt": asks_vol,
                "imbalance_pct": imbalance
            }
            
        except Exception as e:
            logger.error(f"❌ Order Book Error {symbol}: {e}")
            return None
