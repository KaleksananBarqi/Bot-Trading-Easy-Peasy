import os
from dotenv import load_dotenv

load_dotenv()
# strategi pullback sniper

# --- 1. AKUN & API ---
PAKAI_DEMO = True 
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- 2. GLOBAL RISK ---
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 10  

# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'
BTC_EMA_PERIOD = 50             
BTC_CHECK_INTERVAL = 300
USE_BTC_CORRELATION = True
CORRELATION_THRESHOLD_BTC = 0.7

# --- AI CONFIG ---
AI_CONFIDENCE_THRESHOLD = 70
ENABLE_MARKET_ORDERS = False
AVAILABLE_STRATEGIES = {
    'TREND_PULLBACK': 'Trend Pullback Strategy',
    'BB_BOUNCE': 'Bollinger Band Bounce'
}

# --- 4. STRATEGI INDIKATOR ---
EMA_TREND_MAJOR = 200   
EMA_FAST = 7           
EMA_SLOW = 21          

# ADX FILTER
ADX_PERIOD = 14
ADX_LIMIT_TREND  = 30 
ADX_LIMIT_CHOPPY = 20 

# VOLUME FILTER
VOL_MA_PERIOD = 20

# BOLLINGER BANDS
BB_LENGTH = 20
BB_STD = 2.0

# STOCHASTIC RSI
STOCHRSI_LEN = 14
STOCHRSI_K = 3
STOCHRSI_D = 3
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 300            

# SETTING RR 1:2 (FIXED)
ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 2.0
ATR_MULTIPLIER_TP1 = 2.5

MIN_ORDER_USDT = 5           
ORDER_TYPE = 'market'     # Ini akan otomatis di-override jadi 'limit' jika Liquidity Hunt aktif
COOLDOWN_PER_SYMBOL_SECONDS = 300 
CONCURRENCY_LIMIT = 20

# RETRY SETTINGS
ORDER_SLTP_RETRIES = 5
ORDER_SLTP_RETRY_DELAY = 2
POSITION_POLL_RETRIES = 6
POSITION_POLL_DELAY = 0.5

# --- 6. SETTING STRATEGI SNIPER (PENTING) ---

# MODE LIQUIDITY HUNT (Anti-Retail / Jaring Bawah)
USE_LIQUIDITY_HUNT = True  # WAJIB TRUE untuk Winrate Tinggi
TRAP_SAFETY_SL = 0.5       

# LOGIKA ENTRY: TREND TRAP
USE_TREND_TRAP_STRATEGY = True  
TREND_TRAP_ADX_MIN = 20         
TREND_TRAP_RSI_LONG_MIN = 40    
TREND_TRAP_RSI_LONG_MAX = 60    
TREND_TRAP_RSI_SHORT_MIN = 40   
TREND_TRAP_RSI_SHORT_MAX = 60   

# LOGIKA SIDEWAYS (BB BOUNCE)
USE_SIDEWAYS_SCALP = True       
SIDEWAYS_ADX_MAX = 25           

# --- 7. DAFTAR KOIN (HANYA KOIN LIKUID UNTUK WINRATE TINGGI) ---
DAFTAR_KOIN = [
    {"symbol": "BTC/USDT", "leverage": 30, "margin_type": "cross", "amount": 50},
    {"symbol": "ETH/USDT", "leverage": 20, "margin_type": "cross", "amount": 40},
    {"symbol": "SOL/USDT", "leverage": 30, "margin_type": "isolated", "amount": 15},
    {"symbol": "BNB/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "AVAX/USDT", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "ADA/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "SUI/USDT", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "TRX/USDT", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "XPL/USDT", "leverage": 10, "margin_type": "isolated", "amount": 10},
    {"symbol": "LINK/USDT", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "XRP/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "LTC/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "DOGE/USDT", "leverage": 30, "margin_type": "isolated", "amount": 15},
    {"symbol": "PEPE/USDT", "leverage": 20, "margin_type": "isolated", "amount": 15},
    {"symbol": "ZEC/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
]