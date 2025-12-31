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
DEFAULT_AMOUNT_USDT = 10  

# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'    # Timeframe khusus untuk menentukan trend BTC
BTC_EMA_PERIOD = 50     # EMA King Filter

# --- 4. STRATEGI INDIKATOR (PARAMETER) ---
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
COOLDOWN_PER_SYMBOL_SECONDS = 300 
CONCURRENCY_LIMIT = 20
ORDER_SLTP_RETRIES = 3      # Jumlah percobaan pasang SL/TP jika gagal
ORDER_SLTP_RETRY_DELAY = 2  # Detik jeda antar percobaan
ERROR_SLEEP_DELAY = 5       # Detik jeda jika terjadi error loop

# --- 6. SETTING STRATEGI SNIPER (MODIFIED) ---
# A. Sniper / Liquidity Hunt Strategy
USE_LIQUIDITY_HUNT = True
# Seberapa jauh entry digeser dari harga SL awal (dalam satuan ATR)
# 0.0 = Entry pas di harga SL awal
SNIPER_ENTRY_BUFFER = 0.005  
# Jarak Safety SL baru setelah entry sniper kejemput (dalam satuan ATR)
TRAP_SAFETY_SL = 1.0

# B. Trend Trap
USE_TREND_TRAP_STRATEGY = True  
TREND_TRAP_ADX_MIN = 25         
TREND_TRAP_RSI_LONG_MIN = 40    
TREND_TRAP_RSI_LONG_MAX = 60    
TREND_TRAP_RSI_SHORT_MIN = 40   
TREND_TRAP_RSI_SHORT_MAX = 60   

# C. Sideways Scalp
USE_SIDEWAYS_SCALP = True       
SIDEWAYS_ADX_MAX = 20           

# --- 7. DAFTAR KOIN ---
# Jika leverage/amount tidak diisi, akan memakai DEFAULT dari Section 2
DAFTAR_KOIN = [
    {"symbol": "BTC/USDT", "leverage": 20, "margin_type": "cross", "amount": 50},
    {"symbol": "ETH/USDT", "leverage": 20, "margin_type": "cross", "amount": 40},
    {"symbol": "SOL/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "BNB/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "XRP/USDT"}, # Contoh tanpa setting khusus, akan ikut DEFAULT
    {"symbol": "ADA/USDT"},
    {"symbol": "DOGE/USDT"},
    {"symbol": "DOT/USDT"},
    {"symbol": "LTC/USDT"},
    {"symbol": "AVAX/USDT"},
    {"symbol": "LINK/USDT"},
    {"symbol": "UNI/USDT"},
    {"symbol": "ATOM/USDT"},
    {"symbol": "ALGO/USDT"},
    {"symbol": "VET/USDT"},
    {"symbol": "FTM/USDT"},
    {"symbol": "NEAR/USDT"},
    {"symbol": "FTM/USDT"},
    {"symbol": "XLM/USDT"},
    {"symbol": "TRX/USDT"},
    {"symbol": "XMR/USDT"},
    {"symbol": "EOS/USDT"},
    {"symbol": "AAVE/USDT"},
]