# [FILE: config.py]
import os
from dotenv import load_dotenv

load_dotenv()

# --- 1. AKUN & API ---
PAKAI_DEMO = False 
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AI_API_KEY = os.getenv("AI_API_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")

# --- 1.B AI & DATA SOURCE CONFIG ---
AI_MODEL_NAME = 'xiaomi/mimo-v2-flash:free' # atau model lain jika tersedia
AI_TEMPERATURE = 0.0     # [BARU] 0.0 agar AI konsisten & tidak halusinasi
AI_CONFIDENCE_THRESHOLD = 80       # Minimal confidence untuk eksekusi
Sentiment_Provider = 'RSS_Feed'    # Diganti dari CryptoPanic ke RSS
OnChain_Provider = 'DefiLlama'
WHALE_THRESHOLD_USDT = 100000      # Transaksi > $100k dianggap Whale

# [REFACTORED] AI & DATA SOURCE
AI_BASE_URL = "https://openrouter.ai/api/v1"
AI_APP_URL = "https://github.com/KaleksananBarqi/Bot-Trading-Easy-Peasy"
AI_APP_TITLE = "Bot Trading Easy Peasy"
AI_SYSTEM_ROLE = "You are an expert Crypto Trading AI with a focus on Risk Management and Trend Following."

CMC_FNG_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
API_REQUEST_TIMEOUT = 10
NEWS_MAX_PER_SOURCE = 2
NEWS_RETENTION_LIMIT = 15

DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"
STABLECOIN_INFLOW_THRESHOLD_PERCENT = 0.05
WHALE_HISTORY_LIMIT = 10
DEFAULT_CORRELATION_HIGH = 0.99

# --- RSS FEEDS CONFIG ---
RSS_FEED_URLS = [
    # 1. Media Besar & Berita Umum
    "https://www.theblock.co/rss.xml",
    "https://cryptoslate.com/feed/",
    "https://blockworks.co/feed/",
    "https://news.bitcoin.com/feed/",
    
    # 2. Market Updates (Cepat)
    "https://u.today/rss",
    "https://www.newsbtc.com/feed/",
    "https://dailyhodl.com/feed/",
    "https://beincrypto.com/feed/",
    
    # 3. Aggregators (Cheat Code)
    "https://news.google.com/rss/search?q=cryptocurrency+when:1h&hl=en-US&gl=US&ceid=US:en",
    "https://www.reddit.com/r/CryptoCurrency/top/.rss?t=hour"
]

# --- WEBSOCKET CONFIG ---
WS_URL_FUTURES_LIVE = "wss://fstream.binance.com/stream?streams="
WS_URL_FUTURES_TESTNET = "wss://stream.binancefuture.com/stream?streams="
WS_KEEP_ALIVE_INTERVAL = 1800  # Detik untuk refresh listen key
API_RECV_WINDOW = 10000        # RecvWindow untuk CCXT

# --- 2. GLOBAL RISK & SYSTEM FILES ---
LOG_FILENAME = 'bot_trading.log'
TRACKER_FILENAME = 'safety_tracker.json'
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 10      # Cadangan jika dynamic false / error
  
# --- SETTING DYNAMIC SIZING (COMPOUNDING) ---
USE_DYNAMIC_SIZE = False       # Set True untuk aktifkan compounding
RISK_PERCENT_PER_TRADE = 5  # Bot akan pakai 5% dari saldo USDT Available per trade
# Setingan buat pair correlation
MAX_POSITIONS_PER_CATEGORY = 1   # Maksimal 1 posisi per "Sektor"
CORRELATION_THRESHOLD_BTC = 0.5  # Jika korelasi < 0.5, anggap "Jalan Sendiri" (Abaikan BTC Trend)
CORRELATION_PERIOD = 30 # Jumlah candle H1 untuk cek kemiripan dengan BTC
# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'    # Timeframe khusus untuk menentukan trend BTC
BTC_EMA_PERIOD = 200     # EMA King Filter

# --- 4. STRATEGI INDIKATOR (PARAMETER) ---
EMA_TREND_MAJOR = 200
EMA_FAST = 14           
EMA_SLOW = 50          
RSI_PERIOD = 14         # [REFACTORED]
ADX_PERIOD = 14
VOL_MA_PERIOD = 20      # Digunakan untuk filter volume
BB_LENGTH = 20
BB_STD = 2.0 
STOCHRSI_LEN = 14
STOCHRSI_K = 3
STOCHRSI_D = 3

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 300
ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 1.5
ATR_MULTIPLIER_TP1 = 2.0
MIN_ORDER_USDT = 5           
ORDER_TYPE = 'market'     
COOLDOWN_IF_PROFIT = 3600 # kalau profit cooldownnya 1 jam untuk ride the trend
COOLDOWN_IF_LOSS = 7200 # kalau loss coodldownya 2 jam untuk cooling down 
CONCURRENCY_LIMIT = 20
ORDER_SLTP_RETRIES = 3      # Jumlah percobaan pasang SL/TP jika gagal
ORDER_SLTP_RETRY_DELAY = 2  # Detik jeda antar percobaan
ERROR_SLEEP_DELAY = 5       # Detik jeda jika terjadi error loop
LOOP_SLEEP_DELAY = 1        # Jeda loop normal

# [REFACTORED] EXECUTOR DEFAULTS
DEFAULT_SL_PERCENT = 0.015   # 1%
DEFAULT_TP_PERCENT = 0.025   # 2%
LIMIT_ORDER_EXPIRY_SECONDS = 147600 # ~41 Jam

# --- 6. SETTING STRATEGI SNIPER (MODIFIED) ---
# A. Sniper / Liquidity Hunt Strategy
USE_LIQUIDITY_HUNT = True
# Seberapa jauh entry digeser dari harga SL awal (dalam satuan ATR)
# Jarak Safety SL baru setelah entry sniper kejemput (dalam satuan ATR)
TRAP_SAFETY_SL = 1.2

# B. Trend Trap
USE_TREND_TRAP_STRATEGY = True  
TREND_TRAP_ADX_MIN = 20         

# C. Sideways Scalp
USE_SIDEWAYS_SCALP = True       
SIDEWAYS_ADX_MAX = 25           

AVAILABLE_STRATEGIES = {
    'STRATEGY A (SCALP TREND M15)': "Trend Following M15 confirmed by H1 Trend. Valid ADX > 20",
    'STRATEGY B (SIDEWAYS SCALP M15)': "BB Bounce Strategy. Valid ADX < 25.",
    'STANDARD': "Analisa umum jika tidak ada setup spesifik yang valid. Fokus pada konfluensi teknikal dan sentimen.",
}

# --- 7. DAFTAR KOIN ---
# Jika leverage/amount tidak diisi, akan memakai DEFAULT dari Section 2
DAFTAR_KOIN = [
    # --- Kategori: KING (Market Mover) ---
    #{"symbol": "BTC/USDT", "category": "KING", "leverage": 30, "margin_type": "cross", "amount": 50},
    
    # --- Kategori: LAYER 1 (Smart Contract Platform) ---
    # Blockchain utama tempat aplikasi (dApps) dibangun
    #{"symbol": "ETH/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "cross", "amount": 40},
    #{"symbol": "SOL/USDT", "category": "LAYER_1", "leverage": 30, "margin_type": "isolated", "amount": 15},
    #{"symbol": "BNB/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "AVAX/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 5},
    #{"symbol": "ADA/USDT", "category": "LAYER_1", "leverage": 10, "margin_type": "isolated", "amount": 15},
    #{"symbol": "SUI/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "isolated", "amount": 15},
    #{"symbol": "TRX/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "isolated", "amount": 15},
    
    # Kategori: PAYMENT SPECIALIST (New Gen L1)
    # XPL (Plasma) adalah L1, tapi fokus utamanya adalah infrastruktur pembayaran stablecoin.
    #{"symbol": "XPL/USDT", "category": "LAYER_1", "leverage": 5, "margin_type": "isolated", "amount": 10}, 

    # --- Kategori: INFRASTRUCTURE / ORACLE ---
    # Jembatan data antara dunia nyata dan blockchain (Bukan L1)
    #{"symbol": "LINK/USDT", "category": "ORACLE", "leverage": 20, "margin_type": "isolated", "amount": 15},

    # --- Kategori: LEGACY PAYMENT ---
    # Koin generasi lama yang fungsi utamanya transfer value
    #{"symbol": "XRP/USDT", "category": "PAYMENT_LEGACY", "leverage": 10, "margin_type": "isolated", "amount": 15},
    #{"symbol": "LTC/USDT", "category": "PAYMENT_LEGACY", "leverage": 10, "margin_type": "isolated", "amount": 5},
    
    # --- Kategori: MEMECOIN ---
    # Berbasis komunitas, tanpa utilitas teknis berat
    {"symbol": "DOGE/USDT", "category": "MEME", "leverage": 15, "margin_type": "isolated", "amount": 5},
    #{"symbol": "1000PEPE/USDT", "category": "MEME", "leverage": 20, "margin_type": "isolated", "amount": 5},
    
    # --- Kategori: PRIVACY ---
    # Fokus pada anonimitas
    #{"symbol": "ZEC/USDT", "category": "PRIVACY", "leverage": 10, "margin_type": "isolated", "amount": 15},
]
