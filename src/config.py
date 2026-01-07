# [FILE: config.py]
import os
from dotenv import load_dotenv

load_dotenv()

# --- 1. AKUN & API ---
PAKAI_DEMO = True 
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- WEBSOCKET CONFIG ---
WS_URL_FUTURES_LIVE = "wss://fstream.binance.com/stream?streams="
WS_URL_FUTURES_TESTNET = "wss://stream.binancefuture.com/stream?streams="
WS_KEEP_ALIVE_INTERVAL = 1800  # Detik untuk refresh listen key

# --- 2. GLOBAL RISK & SYSTEM FILES ---
LOG_FILENAME = 'bot_trading.log'
TRACKER_FILENAME = 'safety_tracker.json'
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 10      # Cadangan jika dynamic false / error
  
# --- SETTING DYNAMIC SIZING (COMPOUNDING) ---
USE_DYNAMIC_SIZE = True       # Set True untuk aktifkan compounding
RISK_PERCENT_PER_TRADE = 10  # Bot akan pakai 5% dari saldo USDT Available per trade
# Setingan buat pair correlation
MAX_POSITIONS_PER_CATEGORY = 1   # Maksimal 1 posisi per "Sektor"
CORRELATION_THRESHOLD_BTC = 0.5  # Jika korelasi < 0.5, anggap "Jalan Sendiri" (Abaikan BTC Trend)
CORRELATION_PERIOD = 30 # Jumlah candle H1 untuk cek kemiripan dengan BTC
# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'    # Timeframe khusus untuk menentukan trend BTC
BTC_EMA_PERIOD = 50     # EMA King Filter

# --- 4. STRATEGI INDIKATOR (PARAMETER) ---
EMA_TREND_MAJOR = 50
EMA_FAST = 21           
EMA_SLOW = 50          
ADX_PERIOD = 14
ADX_LIMIT_TREND  = 30 
ADX_LIMIT_CHOPPY = 20 
VOL_MA_PERIOD = 20      # Digunakan untuk filter volume
BB_LENGTH = 20
BB_STD = 2.0 
STOCHRSI_LEN = 14
STOCHRSI_K = 3
STOCHRSI_D = 3
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '5m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 100
ENTRY_PRICE_TOLERANCE = 0.5 
ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 1.0
ATR_MULTIPLIER_TP1 = 2.2
MIN_ORDER_USDT = 5           
ORDER_TYPE = 'market'     
COOLDOWN_IF_PROFIT = 3600 # kalau profit cooldownnya 1 jam untuk ride the trend
COOLDOWN_IF_LOSS = 18000 # kalau loss coodldownya 5 jam untuk cooling down 
CONCURRENCY_LIMIT = 20
ORDER_SLTP_RETRIES = 3      # Jumlah percobaan pasang SL/TP jika gagal
ORDER_SLTP_RETRY_DELAY = 2  # Detik jeda antar percobaan
ERROR_SLEEP_DELAY = 5       # Detik jeda jika terjadi error loop

# --- 6. SETTING STRATEGI SNIPER (MODIFIED) ---
# A. Sniper / Liquidity Hunt Strategy
USE_LIQUIDITY_HUNT = True
# Seberapa jauh entry digeser dari harga SL awal (dalam satuan ATR)
# Jarak Safety SL baru setelah entry sniper kejemput (dalam satuan ATR)
TRAP_SAFETY_SL = 1.0

# B. Trend Trap
USE_TREND_TRAP_STRATEGY = True  
TREND_TRAP_ADX_MIN = 25         
TREND_TRAP_RSI_LONG_MIN = 40    
TREND_TRAP_RSI_LONG_MAX = 60    # <--- Ubah ini jika ingin lebih agresif di Bull Market  
TREND_TRAP_RSI_SHORT_MIN = 40   # <--- Ubah ini jika ingin lebih agresif di Bear Market
TREND_TRAP_RSI_SHORT_MAX = 60   

# C. Sideways Scalp
USE_SIDEWAYS_SCALP = True       
SIDEWAYS_ADX_MAX = 20           

# --- 7. DAFTAR KOIN ---
# Jika leverage/amount tidak diisi, akan memakai DEFAULT dari Section 2
DAFTAR_KOIN = [
    # --- Kategori: KING (Market Mover) ---
    {"symbol": "BTC/USDT", "category": "KING", "leverage": 30, "margin_type": "cross", "amount": 50},
    
    # --- Kategori: LAYER 1 (Smart Contract Platform) ---
    # Blockchain utama tempat aplikasi (dApps) dibangun
    {"symbol": "ETH/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "cross", "amount": 40},
    {"symbol": "SOL/USDT", "category": "LAYER_1", "leverage": 30, "margin_type": "isolated", "amount": 15},
    {"symbol": "BNB/USDT", "category": "LAYER_1", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "AVAX/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "ADA/USDT", "category": "LAYER_1", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "SUI/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "TRX/USDT", "category": "LAYER_1", "leverage": 20, "margin_type": "isolated", "amount": 15},
    
    # Kategori: PAYMENT SPECIALIST (New Gen L1)
    # XPL (Plasma) adalah L1, tapi fokus utamanya adalah infrastruktur pembayaran stablecoin.
    {"symbol": "XPL/USDT", "category": "LAYER_1", "leverage": 10, "margin_type": "isolated", "amount": 10}, 

    # --- Kategori: INFRASTRUCTURE / ORACLE ---
    # Jembatan data antara dunia nyata dan blockchain (Bukan L1)
    {"symbol": "LINK/USDT", "category": "ORACLE", "leverage": 20, "margin_type": "isolated", "amount": 15},

    # --- Kategori: LEGACY PAYMENT ---
    # Koin generasi lama yang fungsi utamanya transfer value
    {"symbol": "XRP/USDT", "category": "PAYMENT_LEGACY", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "LTC/USDT", "category": "PAYMENT_LEGACY", "leverage": 10, "margin_type": "isolated", "amount": 5},
    
    # --- Kategori: MEMECOIN ---
    # Berbasis komunitas, tanpa utilitas teknis berat
    {"symbol": "DOGE/USDT", "category": "MEME", "leverage": 30, "margin_type": "isolated", "amount": 5},
    {"symbol": "PEPE/USDT", "category": "MEME", "leverage": 20, "margin_type": "isolated", "amount": 5},
    
    # --- Kategori: PRIVACY ---
    # Fokus pada anonimitas
    {"symbol": "ZEC/USDT", "category": "PRIVACY", "leverage": 10, "margin_type": "isolated", "amount": 15},
]