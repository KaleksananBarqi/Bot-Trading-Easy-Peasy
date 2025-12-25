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
 
# --- 2. GLOBAL RISK ---
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 10  

# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'
BTC_EMA_PERIOD = 50             
BTC_CHECK_INTERVAL = 300        

# --- 4. STRATEGI INDIKATOR (UPDATED) ---
EMA_TREND_MAJOR = 50    
EMA_FAST = 13           
EMA_SLOW = 21          

ADX_PERIOD = 14
ADX_LIMIT  = 20  # Sedikit dilonggarkan karena filter volume sudah ketat       

# [NEW] VOLUME FILTER
VOL_MA_PERIOD = 20

# [NEW] BOLLINGER BANDS (FILTER OVEREXTENDED)
BB_LENGTH = 20
BB_STD = 2.0

# [NEW] STOCHASTIC RSI (SENSITIVE TRIGGER)
STOCHRSI_LEN = 14
STOCHRSI_K = 3
STOCHRSI_D = 3
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 100            

ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 2.0     
ATR_MULTIPLIER_TP1 = 4.0    

MIN_ORDER_USDT = 5           
ORDER_TYPE = 'market'     
COOLDOWN_PER_SYMBOL_SECONDS = 900 
CONCURRENCY_LIMIT = 20

# Order / Retry
ORDER_SLTP_RETRIES = 5
ORDER_SLTP_RETRY_DELAY = 2
POSITION_POLL_RETRIES = 6
POSITION_POLL_DELAY = 0.5

# --- 6. DAFTAR KOIN ---
DAFTAR_KOIN = [
    {"symbol": "BTC/USDT", "leverage": 20, "margin_type": "cross", "amount": 50},
    {"symbol": "ETH/USDT", "leverage": 20, "margin_type": "cross", "amount": 40},
    {"symbol": "SOL/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "BNB/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "XRP/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "ADA/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "DOGE/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "TRX/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "LTC/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "AVAX/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "SUI/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "APT/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "HYPE/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "ENA/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "SEI/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
]