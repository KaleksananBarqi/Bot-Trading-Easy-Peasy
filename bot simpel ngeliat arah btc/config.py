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
 
# --- 2. GLOBAL RISK (Hanya untuk backup) ---
# Settingan per koin ada di bawah (DAFTAR_KOIN), tapi ini default
# jika kamu lupa memasukkan parameter di list.
DEFAULT_LEVERAGE = 10
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 10

MAX_DAILY_LOSS_PERCENT = 70   

# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1h'
BTC_EMA_PERIOD = 50             
BTC_CHECK_INTERVAL = 300        

# --- 4. STRATEGI INDIKATOR ---
EMA_TREND_MAJOR = 34    
EMA_FAST = 13           
EMA_SLOW = 21          

ADX_PERIOD = 14
ADX_LIMIT  = 22         

RSI_PERIOD    = 14
RSI_MIN_LONG  = 60      
RSI_MAX_LONG  = 90      
RSI_MAX_SHORT = 40      
RSI_MIN_SHORT = 20

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 100            

ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 2.0     
ATR_MULTIPLIER_TP1 = 2.0    

MIN_ORDER_USDT = 5           
ORDER_TYPE = 'market'     
COOLDOWN_PER_SYMBOL_SECONDS = 900 
CONCURRENCY_LIMIT = 20

# Order / Retry
ORDER_SLTP_RETRIES = 5
ORDER_SLTP_RETRY_DELAY = 2
POSITION_POLL_RETRIES = 6
POSITION_POLL_DELAY = 0.5

# --- 6. DAFTAR KOIN (CUSTOM PER KOIN) ---
# Format: symbol, leverage, margin_type (cross/isolated), amount (USDT per entry)
DAFTAR_KOIN = [
    # Koin Utama (Berani Besar)
    {"symbol": "BTC/USDT", "leverage": 20, "margin_type": "cross", "amount": 50},
    {"symbol": "ETH/USDT", "leverage": 20, "margin_type": "cross", "amount": 40},
    {"symbol": "SOL/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    {"symbol": "BNB/USDT", "leverage": 15, "margin_type": "isolated", "amount": 30},
    
    # Altcoin Mid (Sedang)
    {"symbol": "XRP/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "ADA/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "DOGE/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "TRX/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "LTC/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    {"symbol": "AVAX/USDT", "leverage": 10, "margin_type": "isolated", "amount": 15},
    
    # Koin Volatil / Baru (Kecil & Aman)
    {"symbol": "SUI/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "APT/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "HYPE/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "ENA/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
    {"symbol": "SEI/USDT", "leverage": 5, "margin_type": "isolated", "amount": 10},
]