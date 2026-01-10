
import asyncio
import json
import time
import pandas as pd
import pandas_ta as ta
import ccxt.async_support as ccxt
import websockets
import config
from src.utils.helper import logger, kirim_tele, wib_time

class MarketDataManager:
    def __init__(self, exchange):
        self.exchange = exchange
        self.market_store = {} # OHLCV Data
        self.ticker_data = {}  # Live Price / Ticker
        self.funding_rates = {} 
        self.open_interest = {}
        
        self.btc_trend = "NEUTRAL"
        self.data_lock = asyncio.Lock()
        
        self.ws_url = config.WS_URL_FUTURES_TESTNET if config.PAKAI_DEMO else config.WS_URL_FUTURES_LIVE
        self.listen_key = None
        self.last_heartbeat = time.time()
        
        # Initialize Store Structure
        for coin in config.DAFTAR_KOIN:
            self.market_store[coin['symbol']] = {
                config.TIMEFRAME_EXEC: [],
                config.BTC_TIMEFRAME: []
            }
        # BTC (Wajib ada helper store)
        if config.BTC_SYMBOL not in self.market_store:
            self.market_store[config.BTC_SYMBOL] = {
                config.TIMEFRAME_EXEC: [],
                config.BTC_TIMEFRAME: []
            }

    async def initialize_data(self):
        """Fetch Initial Historical Data (REST API)"""
        logger.info("📥 Initializing Market Data...")
        tasks = []
        
        async def fetch_pair(symbol):
            try:
                # 1. Fetch OHLCV
                bars_exec = await self.exchange.fetch_ohlcv(symbol, config.TIMEFRAME_EXEC, limit=config.LIMIT_EXEC)
                bars_trend = await self.exchange.fetch_ohlcv(symbol, config.BTC_TIMEFRAME, limit=config.LIMIT_TREND)
                
                # 2. Fetch Funding Rate & Open Interest (Public Endpoint)
                # Note: CCXT fetch_funding_rate usually works
                fund_rate = await self.exchange.fetch_funding_rate(symbol)
                # Open Interest might need specific call or ticker
                # We will update these via Rest mostly or WS if available
                
                async with self.data_lock:
                    self.market_store[symbol][config.TIMEFRAME_EXEC] = bars_exec
                    self.market_store[symbol][config.BTC_TIMEFRAME] = bars_trend
                    self.funding_rates[symbol] = fund_rate.get('fundingRate', 0)
                
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
            bars = self.market_store[config.BTC_SYMBOL][config.BTC_TIMEFRAME]
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

    async def start_stream(self, callback_account_update=None, callback_order_update=None, callback_whale=None):
        """Main WebSocket Loop"""
        while True:
            await self.get_listen_key()
            if not self.listen_key:
                await asyncio.sleep(5)
                continue
                
            streams = [self.listen_key]
            # Add Kline Streams
            for coin in config.DAFTAR_KOIN:
                s_clean = coin['symbol'].replace('/', '').lower()
                streams.append(f"{s_clean}@kline_{config.TIMEFRAME_EXEC}")
                streams.append(f"{s_clean}@kline_{config.BTC_TIMEFRAME}")
                streams.append(f"{s_clean}@aggTrade") # Whale Detector Stream
            
            # Add BTC Stream manual if not exists
            btc_clean = config.BTC_SYMBOL.replace('/', '').lower()
            btc_s = f"{btc_clean}@kline_{config.BTC_TIMEFRAME}"
            if btc_s not in streams: streams.append(btc_s)

            url = self.ws_url + "/".join(streams)
            logger.info(f"📡 Connecting WS... ({len(streams)} streams)")
            
            # Keep Alive Task from Config
            asyncio.create_task(self._keep_alive_listen_key())

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
                                side = "SELL" if payload['m'] else "BUY" # m=True means Maker (Sell side initiatior usually? No, m=True means maker... wait. AggTrade: m=True means the buyer was the maker. So it was a SELL.)
                                if amount_usdt >= config.WHALE_THRESHOLD_USDT:
                                    callback_whale(symbol, amount_usdt, side)
                                
            except Exception as e:
                logger.warning(f"⚠️ WS Disconnected: {e}. Reconnecting...")
                await asyncio.sleep(5)

    async def _keep_alive_listen_key(self):
        while True:
            await asyncio.sleep(config.WS_KEEP_ALIVE_INTERVAL)
            try:
                await self.exchange.fapiPrivatePutListenKey({'listenKey': self.listen_key})
            except: pass

    async def _handle_kline(self, data):
        sym = data['s'].replace('USDT', '/USDT')
        k = data['k']
        interval = k['i']
        new_candle = [int(k['t']), float(k['o']), float(k['h']), float(k['l']), float(k['c']), float(k['v'])]
        
        async with self.data_lock:
            if sym in self.market_store:
                target = self.market_store[sym].get(interval, [])
                if target and target[-1][0] == new_candle[0]:
                    target[-1] = new_candle
                else:
                    target.append(new_candle)
                    if len(target) > config.LIMIT_TREND: target.pop(0)
                self.market_store[sym][interval] = target
        
        # Update BTC Trend Realtime
        if sym == config.BTC_SYMBOL and interval == config.BTC_TIMEFRAME:
            self._update_btc_trend()

    async def get_btc_correlation(self, symbol, period=config.CORRELATION_PERIOD):
        """Hitung korelasi Close price simbol vs BTC (Timeframe 1H)"""
        try:
            if symbol == config.BTC_SYMBOL: return 1.0
            
            bars_sym = self.market_store.get(symbol, {}).get(config.BTC_TIMEFRAME, [])
            bars_btc = self.market_store.get(config.BTC_SYMBOL, {}).get(config.BTC_TIMEFRAME, [])
            
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

    def get_technical_data(self, symbol):
        """Retrieve aggregated technical data for AI Prompt"""
        try:
            bars = self.market_store.get(symbol, {}).get(config.TIMEFRAME_EXEC, [])
            if len(bars) < config.EMA_SLOW + 5: return None
            
            df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
            # 1. EMAs
            df['EMA_FAST'] = df.ta.ema(length=config.EMA_FAST)
            df['EMA_SLOW'] = df.ta.ema(length=config.EMA_SLOW) # EMA Trend Major
            
            # 2. RSI & ADX
            df['RSI'] = df.ta.rsi(length=config.RSI_PERIOD)
            df['ADX'] = df.ta.adx(length=config.ADX_PERIOD)[f"ADX_{config.ADX_PERIOD}"]
            
            # 3. Volume MA
            df['VOL_MA'] = df.ta.sma(close='volume', length=config.VOL_MA_PERIOD)
            
            # 4. Bollinger Bands
            bb = df.ta.bbands(length=config.BB_LENGTH, std=config.BB_STD)
            if bb is not None:
                df['BB_LOWER'] = bb.iloc[:, 0]
                df['BB_UPPER'] = bb.iloc[:, 2]
            
            # 5. Stochastic RSI
            stoch_rsi = df.ta.stochrsi(length=config.STOCHRSI_LEN, rsi_length=config.RSI_PERIOD, k=config.STOCHRSI_K, d=config.STOCHRSI_D)
            # keys example: STOCHRSIk_14_14_3_3, STOCHRSId_14_14_3_3
            k_key = f"STOCHRSIk_{config.STOCHRSI_LEN}_{config.RSI_PERIOD}_{config.STOCHRSI_K}_{config.STOCHRSI_D}"
            d_key = f"STOCHRSId_{config.STOCHRSI_LEN}_{config.RSI_PERIOD}_{config.STOCHRSI_K}_{config.STOCHRSI_D}"
            df['STOCH_K'] = stoch_rsi[k_key]
            df['STOCH_D'] = stoch_rsi[d_key]

            # 6. ATR (Untuk Liquidity Hunt)
            df['ATR'] = df.ta.atr(length=config.ATR_PERIOD)

            cur = df.iloc[-2] # Confirmed Candle (Close)
            
            # Simple Trend Check
            ema_pos = "Above" if cur['close'] > cur['EMA_FAST'] else "Below"
            trend_major = "Bullish" if cur['close'] > cur['EMA_SLOW'] else "Bearish"
            
            return {
                "price": cur['close'],
                "rsi": cur['RSI'],
                "adx": cur['ADX'],
                "ema_fast": cur['EMA_FAST'],
                "ema_slow": cur['EMA_SLOW'], # EMA Trend Major
                "vol_ma": cur['VOL_MA'],
                "volume": cur['volume'],
                "bb_upper": cur['BB_UPPER'],
                "bb_lower": cur['BB_LOWER'],
                "stoch_k": cur['STOCH_K'],
                "stoch_d": cur['STOCH_D'],
                "atr": cur['ATR'],
                "price_vs_ema": ema_pos,
                "trend_major": trend_major,
                "btc_trend": self.btc_trend,
                "funding_rate": self.funding_rates.get(symbol, 0),
                "open_interest": "N/A"
            }
        except Exception as e:
            logger.error(f"Get Tech Data Error {symbol}: {e}")
            return None
