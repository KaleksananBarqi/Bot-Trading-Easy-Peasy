# [FILE: config.py]
import os
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# --- SECTION 1: CREDENTIALS & API KEYS ---
# ==============================================================================
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_MESSAGE_THREAD_ID = os.getenv("TELEGRAM_MESSAGE_THREAD_ID")  # Opsional untuk topik/forum
TELEGRAM_TOKEN_SENTIMENT = os.getenv("TELEGRAM_TOKEN_SENTIMENT")
TELEGRAM_CHAT_ID_SENTIMENT = os.getenv("TELEGRAM_CHAT_ID_SENTIMENT")
TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT = os.getenv("TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT")
AI_API_KEY = os.getenv("AI_API_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")

# ==============================================================================
# --- SECTION 2: SYSTEM & APPLICATION CONFIG ---
# ==============================================================================
PAKAI_DEMO = True               # Set True untuk menggunakan Binance Testnet
LOG_FILENAME = 'bot_trading.log'
TRACKER_FILENAME = 'safety_tracker.json'

CONCURRENCY_LIMIT = 20          # Maksimal pair yang diproses bersamaan
LOOP_SLEEP_DELAY = 1             # Jeda antar loop utama (detik)
ERROR_SLEEP_DELAY = 5            # Jeda jika terjadi error loop (detik)
API_REQUEST_TIMEOUT = 10         # Timeout request API (detik)
API_RECV_WINDOW = 10000          # RecvWindow untuk CCXT / Binance

# ==============================================================================
# --- SECTION 3: AI BRAIN & PROMPT ENGINE ---
# ==============================================================================
AI_MODEL_NAME = 'deepseek/deepseek-v3.2' 
AI_TEMPERATURE = 0.0             # 0.0 agar AI konsisten & tidak halusinasi
AI_CONFIDENCE_THRESHOLD = 75     # Minimal confidence score untuk eksekusi
AI_SYSTEM_ROLE = "You are an elite Crypto Trading AI capable of Adaptive Multi-Strategy Execution. You specialize in identifying Trend Following, Mean Reversion, and Volatility Breakout setups, with an uncompromising focus on Risk Management and Capital Preservation."
AI_BASE_URL = "https://openrouter.ai/api/v1"
AI_APP_URL = "https://github.com/KaleksananBarqi/Bot-Trading-Easy-Peasy"
AI_APP_TITLE = "Bot Trading Easy Peasy"

# Sentiment Analysis Config
ENABLE_SENTIMENT_ANALYSIS = True
AI_SENTIMENT_MODEL = 'google/gemini-2.0-flash-exp:free' # Model hemat cost untuk analisa berita

# Vision AI (Chart Pattern)
USE_PATTERN_RECOGNITION = True
AI_VISION_MODEL = 'meta-llama/llama-4-maverick' # Model hemat cost namun capable untuk vision
AI_VISION_TEMPERATURE = 0.0

Sentiment_Provider = 'RSS_Feed'  # Pilihan: 'RSS_Feed'
OnChain_Provider = 'DefiLlama'   # Pilihan: 'DefiLlama'

# ==============================================================================
# --- SECTION 4: EXTERNAL DATA SOURCES ---
# ==============================================================================
CMC_FNG_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"

# Websocket URLs
WS_URL_FUTURES_LIVE = "wss://fstream.binance.com/stream?streams="
WS_URL_FUTURES_TESTNET = "wss://stream.binancefuture.com/stream?streams="
WS_KEEP_ALIVE_INTERVAL = 1800    # Detik untuk refresh listen key

# News & RSS Config
NEWS_MAX_PER_SOURCE = 2
NEWS_RETENTION_LIMIT = 15
NEWS_MAX_AGE_HOURS = 6      # Filter berita: hanya 1 jam terakhir
RSS_FEED_URLS = [
    "https://www.theblock.co/rss.xml",
    "https://cryptoslate.com/feed/",
    "https://blockworks.co/feed/",
    "https://news.bitcoin.com/feed/",
    "https://u.today/rss",
    "https://www.newsbtc.com/feed/",
    "https://dailyhodl.com/feed/",
    "https://beincrypto.com/feed/",
]

# ==============================================================================
# --- SECTION 5: GLOBAL TRADING RISK MANAGEMENT ---
# ==============================================================================
USE_DYNAMIC_SIZE = True         # Set True untuk aktifkan Compounding
RISK_PERCENT_PER_TRADE = 3       # % dari saldo per trade jika Dynamic True
DEFAULT_AMOUNT_USDT = 10         # Besar posisi awal (Cadangan jika dynamic False)
MIN_ORDER_USDT = 5                

DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' # 'isolated' atau 'cross'
MAX_POSITIONS_PER_CATEGORY = 5   # Limit posisi per sektor koin

# Cooldown Logic
COOLDOWN_IF_PROFIT = 3600        # Jeda setelah profit (detik) - ride the trend
COOLDOWN_IF_LOSS = 7200          # Jeda setelah loss (detik) - cooling down

# Whale & Money Flow
WHALE_THRESHOLD_USDT = 100000    # Transaksi > $100k dianggap Whale
WHALE_HISTORY_LIMIT = 10
STABLECOIN_INFLOW_THRESHOLD_PERCENT = 0.05

# ==============================================================================
# --- SECTION 6: TECHNICAL ANALYSIS & INDICATORS ---
# ==============================================================================
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 300

# Setup Context (Pattern Recognition)
TIMEFRAME_SETUP = '30m'      
LIMIT_SETUP = 100

# Interval khusus untuk update News, F&G, dan Stablecoin Inflow
# Terpisah dari TIMEFRAME_TREND agar lebih fleksibel.
SENTIMENT_UPDATE_INTERVAL = '1h'

# BTC Global Trend Filter
BTC_SYMBOL = 'BTC/USDT'
BTC_EMA_PERIOD = 21             # EMA 200 sebagai trend king filter

# Indicator Parameters
EMA_TREND_MAJOR = 200
EMA_FAST = 14           
EMA_SLOW = 50          
RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
ADX_PERIOD = 14
VOL_MA_PERIOD = 20               # Filter volume transaksi
BB_LENGTH = 20
BB_STD = 2.0 
STOCHRSI_LEN = 14
STOCHRSI_K = 3
STOCHRSI_D = 3

# Correlation Rules
CORRELATION_THRESHOLD_BTC = 0.7  # Jika < 0.5, koin dianggap "jalan sendiri"
CORRELATION_PERIOD = 30          # Jumlah candle untuk cek korelasi
DEFAULT_CORRELATION_HIGH = 0.99

# ==============================================================================
# --- SECTION 7: EXECUTION & ORDER MANAGEMENT ---
# ==============================================================================
# SL/TP Percent Defaults (Safety Fallback)
DEFAULT_SL_PERCENT = 0.015       # 1.5%
DEFAULT_TP_PERCENT = 0.025       # 2.5%

# ATR Based SL/TP Multipliers (Primary)
ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 1.5
ATR_MULTIPLIER_TP1 = 2.2

# Order Management
ORDER_SLTP_RETRIES = 3           # Re-try pasang SL/TP jika gagal
ORDER_SLTP_RETRY_DELAY = 2       # Jeda antar percobaan (detik)
LIMIT_ORDER_EXPIRY_SECONDS = 147600 # ~41 Jam

# ==============================================================================
# --- SECTION 8: SPECIFIC STRATEGY SETTINGS ---
# ==============================================================================
# Liquidity Hunt
# USE_LIQUIDITY_HUNT Removed (Obsolete)
TRAP_SAFETY_SL = 1.2             # Jarak Safety SL Dari Entry Baru (ATR)           

AVAILABLE_STRATEGIES = {
    # 1. Fokus pada Pattern + Trend (The Conservative)
    'PATTERN_CONFLUENCE_TREND': "Strategi ini mewajibkan keselarasan antara Macro Trend {config.TIMEFRAME_TREND} dan visual pattern di {config.TIMEFRAME_SETUP}. RECOMMENDED EXECUTION: [MARKET] untuk menangkap momentum breakout yang valid.",

    # 2. Fokus pada Breakout Volatilitas (The Aggressive)
    'VOLATILITY_BREAKOUT_ADVANCED': "Mendeteksi breakout signifikan dengan volume tinggi dan ADX > 25. RECOMMENDED EXECUTION: [MARKET] karena harga bergerak cepat dan jarang pullback dalam waktu dekat.",

    # 3. Fokus pada Reversal & Liquidity (The Contrarian)
    'LIQUIDITY_REVERSAL_MASTER': "Mencari pembalikan arah di area Pivot (S1/R1) atau Liquidity Sweep. RECOMMENDED EXECUTION: [LIQUIDITY_HUNT] untuk mendapatkan harga terbaik saat 'Stop Hunt' terjadi, dengan R:R yang jauh lebih superior.",

    # 4. Fokus pada Sentimen & Whale Flow (The Follow-the-Money)
    'SMART_MONEY_FLOW': "Mengikuti jejak uang besar (Whale/Institutional). Jika data on-chain bullish kuat tapi harga masih dipahamin 'murah' (konsolidasi), gunakan [LIQUIDITY_HUNT]. Jika harga sudah mulai lari, gunakan [MARKET].",

    # 5. Fallback/Standard
    #'STANDARD_MULTI_CONFIRMATION': "Analisa teknikal seimbang. Evaluasi Risk:Reward (R:R) dari opsi MARKET vs LIQUIDITY_HUNT. Pilih yang memberikan R:R terbaik dan probabilitas sukses tertinggi.",

    # 6. Fokus pada Sideways & Reversal (The Ranger)
    'BB_BOUNCE': "Jika ADX sedang lemah/sideways (< 20), fokus pada setup Reversal di area BB Top (Upper Band) atau BB Bottom (Lower Band). Sangat disarankan menggunakan [LIQUIDITY_HUNT] untuk mendapatkan harga entry terbaik saat terjadi pantulan."
}

# ==============================================================================
# --- SECTION 9: COIN REGISTRY ---
# ==============================================================================
# CATATAN: Jika leverage/amount tiap koin tidak diisi, akan memakai default dari Section 5
DAFTAR_KOIN = [
    # --- Kategori: LAYER 1 ---
    {"symbol": "XRP/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 5},
    {"symbol": "SOL/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 5},
    {"symbol": "BTC/USDT", "category": "KING", "leverage": 15, "margin_type": "isolated", "amount": 5},
    {"symbol": "ETH/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 5},
    
    # --- Kategori: MEMECOIN ---
    {"symbol": "DOGE/USDT", "category": "MEME", "leverage": 15, "margin_type": "isolated", "amount": 5},
]
