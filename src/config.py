# [FILE: config.py]
import os
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# 🛠️ KONFIGURASI KREDENSIAL & API KEYS
# ==============================================================================
# Binance (Pastikan file .env sudah terisi dengan benar)
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")

# Telegram Notifikasi
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_MESSAGE_THREAD_ID = os.getenv("TELEGRAM_MESSAGE_THREAD_ID")  # Opsional: untuk Topik/Forum ID

# Telegram Sentimen (Channel Terpisah)
TELEGRAM_TOKEN_SENTIMENT = os.getenv("TELEGRAM_TOKEN_SENTIMENT")
TELEGRAM_CHAT_ID_SENTIMENT = os.getenv("TELEGRAM_CHAT_ID_SENTIMENT")
TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT = os.getenv("TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT")

# 3rd Party APIs
AI_API_KEY = os.getenv("AI_API_KEY")       # OpenRouter / DeepSeek
CMC_API_KEY = os.getenv("CMC_API_KEY")     # CoinMarketCap

# ==============================================================================
# ⚙️ PENGATURAN SISTEM & APLIKASI
# ==============================================================================
PAKAI_DEMO = False               # False = Real Money, True = Testnet (Uang Monopoly)
LOG_FILENAME = 'bot_trading.log'
TRACKER_FILENAME = 'safety_tracker.json'

# Performa Loop & Request
CONCURRENCY_LIMIT = 20           # Maksimal pair yang diproses bersamaan (multithreading)
LOOP_SLEEP_DELAY = 1             # Istirahat antar putaran loop utama (detik)
ERROR_SLEEP_DELAY = 5            # Istirahat jika terjadi error (detik)
API_REQUEST_TIMEOUT = 10         # Batas waktu tunggu balasan server (detik)
API_RECV_WINDOW = 10000          # Toleransi waktu server Binance (ms)
LOOP_SKIP_DELAY = 2              # Delay saat skip coin karena data tidak lengkap (detik)

# ==============================================================================
# 📊 INDIKATOR TEKNIKAL & ANALISA CHART
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. GROUP 1: TREND (Analisa Tren Besar)
# ------------------------------------------------------------------------------
TIMEFRAME_TREND = '1h'           # Timeframe untuk melihat tren besar
LIMIT_TREND = 500                # Limit candle
EMA_TREND_MAJOR = 21             # EMA filter tren utama (Trend Direction)
ADX_PERIOD = 14                  # Kekuatan Tren (Trend Strength)

# ------------------------------------------------------------------------------
# 2. GROUP 2: SETUP (Pola & Struktur)
# ------------------------------------------------------------------------------
TIMEFRAME_SETUP = '30m'          # Timeframe untuk pola chart
LIMIT_SETUP = 100                # Limit candle

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ------------------------------------------------------------------------------
# 3. GROUP 3: EXECUTION (Momentum & Entry)
# ------------------------------------------------------------------------------
TIMEFRAME_EXEC = '15m'           # Timeframe untuk eksekusi entry
LIMIT_EXEC = 300                 # Limit candle

# Moving Averages (Crossover)
EMA_FAST = 7                     # EMA Cepat
EMA_SLOW = 21                    # EMA Lambat

# Momentum Indicators
RSI_PERIOD = 14                  # RSI standard
RSI_OVERSOLD = 35                # Batas bawah RSI (Jenuh Jual)
RSI_OVERBOUGHT = 65              # Batas atas RSI (Jenuh Beli)

STOCHRSI_LEN = 14                # Stochastic RSI
STOCHRSI_K = 3
STOCHRSI_D = 3

# Volatility (Bollinger Bands)
BB_LENGTH = 20                   # Bollinger Bands Length (Volatilitas)
BB_STD = 2.0                     # Bollinger Bands Deviasi

# Volume
VOL_MA_PERIOD = 20               # Rata-rata Volume

# ------------------------------------------------------------------------------
# 4. GROUP 4: BITCOIN KING EFFECT (Korelasi Tren)
# ------------------------------------------------------------------------------
USE_BTC_CORRELATION = True       # Wajib cek gerak-gerik Bitcoin?
BTC_SYMBOL = 'BTC/USDT'
BTC_EMA_PERIOD = 50              # EMA Trend Filter Bitcoin
CORRELATION_THRESHOLD_BTC = 0.7  # Minimal korelasi untuk dianggap ngikut BTC
CORRELATION_PERIOD = 30          # Periode cek korelasi
DEFAULT_CORRELATION_HIGH = 0.99  # Nilai default jika data korrelasi belum ada

# ==============================================================================
# 🧠 KECERDASAN BUATAN (AI) & STRATEGI
# ==============================================================================
# Otak Utama (Decision Maker)
AI_MODEL_NAME = 'deepseek/deepseek-v3.2'
AI_TEMPERATURE = 0.0             # 0.0 = Logis & Konsisten, 1.0 = Kreatif & Halusinasi
AI_CONFIDENCE_THRESHOLD = 70     # Minimal keyakinan (%) untuk berani eksekusi
AI_SYSTEM_ROLE = f"""You are a Liquidity Hunt Specialist. Your job is to TRAP retail traders, not follow them.

CORE CONCEPT:
- Retail traders place Stop Loss below Support (S1) and above Resistance (R1)
- Smart Money SWEEPS these zones to fill their large orders
- Entry prices in EXECUTION SCENARIOS are pre-calculated at the SWEEP ZONE (retail SL area)

YOUR TASK:
You will receive TWO execution scenarios:
- SCENARIO A (Long): Entry is placed BELOW S1 (waiting for price to sweep down)
- SCENARIO B (Short): Entry is placed ABOVE R1 (waiting for price to sweep up)

DECISION FRAMEWORK:
1. Analyze current price position relative to Pivot levels
2. Identify which scenario has ACTIVE sweep conditions
3. Select the scenario where price is approaching OR has just swept the liquidity zone

TREND FILTER (CRITICAL):
- If Trend is STRONG BEARISH, disqualifies SCENARIO A (Long) unless strict reversal conditions are met (Deep Oversold + StochRSI Crossover).
- If Trend is STRONG BULLISH, disqualifies SCENARIO B (Short) unless strict reversal conditions are met (Deep Overbought + StochRSI Crossover).

CHOOSE SCENARIO A (LONG) IF:
✓ Price is near/below S1 (approaching retail Long SL zone)
✓ Wick penetrates S1 but candle body CLOSES above S1
✓ Volume spike on sweep candle (min 1.5x average)
✓ RSI < {RSI_OVERSOLD} (Deep Oversold) AND StochRSI K crosses ABOVE D
✓ Trend is not STRONG BEARISH (or if it is, confirmation must be perfect)

CHOOSE SCENARIO B (SHORT) IF:
✓ Price is near/above R1 (approaching retail Short SL zone)  
✓ Wick penetrates R1 but candle body CLOSES below R1
✓ Volume spike on sweep candle (min 1.5x average)
✓ RSI > {RSI_OVERBOUGHT} (Deep Overbought) AND StochRSI K crosses BELOW D
✓ Trend is not STRONG BULLISH (or if it is, confirmation must be perfect)

REJECT BOTH SCENARIOS IF:
✗ Price is in no-man's land (between S1 and R1, no sweep happening)
✗ Candle CLOSES beyond Pivot level (true breakout, not a sweep)
✗ No volume confirmation (weak/fake sweep)
✗ Conflicting signals between timeframes
✗ Price is sweeping S1 but trend is Bearish and NO Divergence/Crossover (Don't catch a falling knife!)
"""
AI_BASE_URL = "https://openrouter.ai/api/v1"

# Reasoning (Untuk Model yang Support Reasoning Tokens)
AI_REASONING_ENABLED = False       # Aktifkan fitur reasoning? (True/False)
AI_REASONING_EFFORT = 'medium'    # Level effort: 'xhigh', 'high', 'medium', 'low', 'minimal', 'none'
AI_REASONING_EXCLUDE = False      # True = reasoning tidak ditampilkan di response
AI_LOG_REASONING = True           # Catat proses reasoning ke log? (True/False)

# Identitas Bot
AI_APP_URL = "https://github.com/KaleksananBarqi/Bot-Trading-Easy-Peasy"
AI_APP_TITLE = "Bot Trading Easy Peasy"

# Analisa Berita & Sentimen
ENABLE_SENTIMENT_ANALYSIS = False          # Aktifkan analisa sentimen berita?
AI_SENTIMENT_MODEL = 'xiaomi/mimo-v2-flash' # Model ekonomis untuk baca berita
SENTIMENT_ANALYSIS_INTERVAL = '3h'         # Seberapa sering cek sentimen (misal: tiap 2 jam)
SENTIMENT_UPDATE_INTERVAL = '1h'           # Interval update data raw sentimen
SENTIMENT_PROVIDER = 'RSS_Feed'  # Sumber: 'RSS_Feed'

# Analisa Visual (Chart Pattern)
USE_PATTERN_RECOGNITION = True
AI_VISION_MODEL = 'meta-llama/llama-4-maverick' # Model vision
AI_VISION_TEMPERATURE = 0.0
AI_VISION_MAX_TOKENS = 300            # Naikkan untuk mencegah output terpotong

# Validasi Pattern Recognition
PATTERN_MAX_RETRIES = 2               # Berapa kali retry jika output tidak valid
PATTERN_MIN_ANALYSIS_LENGTH = 50      # Minimal panjang karakter output yang dianggap valid
PATTERN_REQUIRED_KEYWORDS = ['BULLISH', 'BEARISH', 'NEUTRAL']  # Minimal satu harus ada

# Data OnChain
ONCHAIN_PROVIDER = 'DefiLlama'   # Sumber data OnChain

# ==============================================================================
# 💰 MANAJEMEN RISIKO & MONEY MANAGEMENT
# ==============================================================================
# Pengaturan Ukuran Posisi
USE_DYNAMIC_SIZE = False         # True = Compounding (% saldo), False = Fix USDT
RISK_PERCENT_PER_TRADE = 3       # Jika Dynamic: Gunakan 3% dari total wallet
DEFAULT_AMOUNT_USDT = 10         # Jika Static: Gunakan $10 per trade
MIN_ORDER_USDT = 5               # Minimal order yang diizinkan Binance

# Leverage & Margin
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' # 'isolated' (aman) atau 'cross' (beresiko/gabungan)
MAX_POSITIONS_PER_CATEGORY = 5   # Batas maksimal koin aktif per kategori (Layer 1, AI, Meme, dll)

# Pendeteksi Paus (Whale)
WHALE_THRESHOLD_USDT = 1000000   # Transaksi > $1 Juta ditandai sebagai Whale
WHALE_HISTORY_LIMIT = 10         # Cek 10 transaksi terakhir
STABLECOIN_INFLOW_THRESHOLD_PERCENT = 0.05 # Ambang batas aliran masuk stablecoin

# Order Book Analysis
ORDERBOOK_RANGE_PERCENT = 0.02   # Range depth analysis order book (2%)

# Mekanisme Pendinginan (Anti-FOMO/Anti-Revenge)
COOLDOWN_IF_PROFIT = 3600        # Jeda trading di koin ini jika PROFIT (detik)
COOLDOWN_IF_LOSS = 7200          # Jeda trading di koin ini jika LOSS (detik)



# ==============================================================================
# 🎯 EKSEKUSI ORDER & TARGET PROFIT
# ==============================================================================
ENABLE_MARKET_ORDERS = False      # Izinkan Market Order (Hajar Kanan/Kiri)?
LIMIT_ORDER_EXPIRY_SECONDS = 147600 # Batas waktu Limit Order pending (dihapus jika basi) -> ~41 Jam

# Stop Loss (SL) & Take Profit (TP) - Fallback/Default
DEFAULT_SL_PERCENT = 0.015       # 1.5% (Jaga-jaga jika ATR bermasalah)
DEFAULT_TP_PERCENT = 0.025       # 2.5%

# Penghitungan SL/TP Dinamis (Berbasis ATR)
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 2.0          # Lebar SL = 2x ATR
ATR_MULTIPLIER_TP1 = 3.0         # Target TP = 3x ATR (Risk Reward 1:1.5)
TRAP_SAFETY_SL = 2.0             # Jarak Safety SL untuk Liquidity Hunt

# Mekanisme Retry (Coba Lagi)
ORDER_SLTP_RETRIES = 3           # Berapa kali coba pasang SL/TP jika server sibuk
ORDER_SLTP_RETRY_DELAY = 2       # Jeda percobaan (detik)

# ==============================================================================
# 🔄 TRAILING STOP LOSS (TSL)
# ==============================================================================
ENABLE_TRAILING_STOP = True           # Aktifkan fitur Trailing Stop?
TRAILING_ACTIVATION_THRESHOLD = 0.80  # Aktif saat harga sudah N% jalan ke TP
TRAILING_CALLBACK_RATE = 0.0075       # Callback rate 0.75% (jarak SL dari harga tertinggi)
TRAILING_MIN_PROFIT_LOCK = 0.005      # Minimal profit yang dikunci N%
TRAILING_SL_UPDATE_COOLDOWN = 3       # Minimal interval antara update SL ke exchange (detik)

# ==============================================================================
# 📡 SUMBER DATA EKSTERNAL
# ==============================================================================
# API URLs
CMC_FNG_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"

# Websocket Binance
WS_URL_FUTURES_LIVE = "wss://fstream.binance.com/stream?streams="
WS_URL_FUTURES_TESTNET = "wss://stream.binancefuture.com/stream?streams="
WS_KEEP_ALIVE_INTERVAL = 1800

# Sumber Berita (RSS Feeds)
NEWS_MAX_PER_SOURCE = 10          # Ambil N berita terbaru per web
NEWS_MAX_TOTAL = 180              # Total berita mentah yang disimpan (sebelum filter)
NEWS_RETENTION_LIMIT = 10        # Max berita relevan yang dikirim ke prompt per koin
NEWS_MAX_AGE_HOURS = 24           # Jangan ambil berita yg > N jam lalu

# News Filtering Rules (Per Category)
NEWS_COIN_SPECIFIC_MIN = 4       # Minimal berita koin yang bersangkutan
NEWS_BTC_MAX = 3                 # Maksimal berita BTC (untuk non-BTC coins)
NEWS_MACRO_MAX = 3               # Maksimal berita makro

RSS_FEED_URLS = [
    # --- International Sources ---
    "https://www.coindesk.com/arc/outboundfeeds/rss/",  # CoinDesk (Pasar)
    "https://cointelegraph.com/rss",                    # CoinTelegraph
    "https://cryptonews.com/news/feed/",                # CryptoNews
    "https://ambcrypto.com/feed",                       # AMBCrypto
    "https://decrypt.co/feed",                          # Decrypt
    "https://www.theblock.co/rss.xml",
    "https://cryptoslate.com/feed/",
    "https://blockworks.co/feed/",
    "https://news.bitcoin.com/feed/",
    "https://u.today/rss",
    "https://www.newsbtc.com/feed/",
    "https://dailyhodl.com/feed/",
    "https://beincrypto.com/feed/",
    
    # --- Indonesian Sources ---
    "https://www.portalkripto.com/feed/",               # PortalKripto
    "https://jelajahcoin.com/feed/",                    # JelajahCoin
    "https://blockchainmedia.id/feed/",                 # BlockchainMedia.id

    # --- Specific Topics ---
    "https://cryptopotato.com/tag/solana/feed/",
    # Google News (Macro)
    "https://news.google.com/rss/search?q=federal+reserve+rates+OR+us+inflation+cpi+OR+global+recession+when:24h&hl=en-US&gl=US&ceid=US:en",
]

# Keyword Berita Makro (Wajib masuk prompt)
MACRO_KEYWORDS = ["federal reserve", "fed", "fomc", "inflation", "cpi", "recession", "interest rate", "powell", "sec", "crypto regulation"] 


# ======	========================================================================
# 📋 DAFTAR STRATEGI
# ==============================================================================
AVAILABLE_STRATEGIES = {
    'LIQUIDITY_REVERSAL_MASTER': "Mencari pembalikan arah di area Pivot (S1/R1) atau Liquidity Sweep. ",
}

# ==============================================================================
# 🪙 DAFTAR KOIN (MARKET WATCH)
# ==============================================================================
# Format: {"symbol": "KOIN/USDT", "category": "KATEGORI", "leverage": X, "amount": Y, "keywords": ["..."]}
DAFTAR_KOIN = [
    {
        "symbol": "BTC/USDT", 
        "category": "KING", 
        "leverage": 15, 
        "margin_type": "isolated", 
        "amount": 20, 
        "btc_corr": False,
        "keywords": ["bitcoin", "btc"]
    },
    {
        "symbol": "SOL/USDT", 
        "category": "LAYER1", 
        "leverage": 15, 
        "margin_type": "isolated", 
        "amount": 20, 
        "btc_corr": True,
        "keywords": ["solana", "sol"]
    },
]
