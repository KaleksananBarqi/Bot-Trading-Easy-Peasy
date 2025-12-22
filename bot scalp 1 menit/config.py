import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- 1. AKUN & API ---
PAKAI_DEMO = True  # Ubah ke False jika mau pakai uang asli (LIVE)

# API TESTNET (DEMO)
API_KEY_DEMO = os.getenv("BINANCE_TESTNET_KEY")
SECRET_KEY_DEMO = os.getenv("BINANCE_TESTNET_SECRET")

# API LIVE (REAL)
API_KEY_LIVE = os.getenv("BINANCE_API_KEY")
SECRET_KEY_LIVE = os.getenv("BINANCE_SECRET_KEY")

# TELEGRAM
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================================================
# 2. MANAJEMEN UANG & RISIKO
# =========================================================

# --- A. Dynamic Position Sizing ---
USE_DYNAMIC_SIZE = False         
RISK_PERCENT_PER_TRADE = 100    
MARGIN_PER_POSISI_FIXED = 10    # Modal fixed per trade dalam USDT (Fallback)
LEVERAGE = 15                   

# --- B. Daily Max Loss ---
MAX_DAILY_LOSS_PERCENT = 10.0   

# --- C. Auto Move to Break-Even ---
AUTO_MOVE_TO_BE = True          
MOVE_TO_BE_TRIGGER_PERCENT = 1.0 
BE_BUFFER_PERCENT = 0.1

# =========================================================
# 3. PENGATURAN STRATEGI (THE SCALPING KING)
# =========================================================
EMA_TREND_MAJOR = 50    
EMA_FAST = 13           
EMA_SLOW = 21           
WAJIB_EMA_CROSS = False 

ADX_PERIOD = 14
ADX_LIMIT  = 22         

RSI_PERIOD    = 14
RSI_MIN_LONG  = 60      
RSI_MAX_LONG  = 90      
RSI_MAX_SHORT = 40      
RSI_MIN_SHORT = 20

# =========================================================
# 4. PENGATURAN TEKNIKAL & EKSEKUSI (UPDATED)
# =========================================================

# --- A. Timeframe ---
TIMEFRAME_TREND = '1h'      
TIMEFRAME_EXEC = '15m'      
LIMIT_TREND = 500           
LIMIT_EXEC = 100            

# --- B. Parameter Kalkulasi Trade (ATR) ---
ATR_PERIOD = 14             
ATR_MULTIPLIER_ENTRY_IDEAL = 0.2  
ATR_MULTIPLIER_ENTRY_KONSER = 0.5 
ATR_MULTIPLIER_SL = 2.0     
ATR_MULTIPLIER_TP1 = 2.0    
ATR_MULTIPLIER_TP2 = 3.0    
ATR_MULTIPLIER_TP3 = 6.0    

# --- C. Execution Strategy (NEW: MAKER FEE SAVER) ---
# 'LIMIT'  = Coba pasang Limit order dulu (Hemat Fee). Jika tak kejemput, baru market.
# 'MARKET' = Langsung Hajar Kanan/Kiri (Cepat, tapi Fee Mahal & Slippage).
ENTRY_ORDER_TYPE = 'LIMIT' 

# Jika pakai LIMIT, berapa detik menunggu sebelum cancel dan ganti ke Market?
LIMIT_WAIT_SECONDS = 10 

# --- D. Spread Protection (NEW) ---
# Jika spread (Ask - Bid) lebih besar dari X%, batalkan trade.
# Contoh: 0.5% (Untuk menghindari koin yang sedang 'kocak' atau tidak likuid)
MAX_SPREAD_PERCENT = 0.5

# --- E. Flexible Take Profit Config (NEW) ---
# Atur persentase porsi yang dijual di setiap TP.
# Total harus 100% (atau 1.0). Jika tidak ingin pakai TP3, set ke 0.
# Contoh 1 (3 TP): TP1=0.5 (50%), TP2=0.3 (30%), TP3=0.2 (20%)
# Contoh 2 (Cuma TP1): TP1=1.0 (100%), TP2=0, TP3=0
# Contoh 3 (TP1 & TP2): TP1=0.7 (70%), TP2=0.3 (30%), TP3=0

TP_ALLOCATION = {
    'TP1': 1,  # % Jual di TP1
    'TP2': 0,  # % Jual di TP2
    'TP3': 0   # % Jual di TP3
}

# --- F. Pengaturan Bot & Loop ---
MIN_ORDER_USDT = 5          # Binance biasanya butuh min $5
COOLDOWN_PER_SYMBOL_SECONDS = 900 
SCAN_DELAY_PER_COIN_SECONDS = 0.5 
CONCURRENCY_LIMIT = 20
ORDER_SLTP_RETRIES = 5
ORDER_SLTP_RETRY_DELAY = 2
POSITION_POLL_RETRIES = 6
POSITION_POLL_DELAY = 0.5

# =========================================================
# 5. PENGATURAN CONVICTION SCORE
# =========================================================
SCORE_BASE = 6                  
SCORE_ADX_STRONG_THRESHOLD = 30 
SCORE_ADX_STRONG_VALUE = 1      
SCORE_RSI_ROOM_LONG_THRESHOLD = 70 
SCORE_RSI_ROOM_LONG_VALUE = 1
SCORE_RSI_ROOM_SHORT_THRESHOLD = 30 
SCORE_RSI_ROOM_SHORT_VALUE = 1
SCORE_MAX = 10                  

# =========================================================
# 6. DAFTAR PAIR KOIN
# =========================================================
DAFTAR_KOIN = [
    {"symbol": "BTC/USDT"},
    {"symbol": "ETH/USDT"},
    {"symbol": "SOL/USDT"},
    {"symbol": "BNB/USDT"},
    {"symbol": "XRP/USDT"},
    {"symbol": "DOGE/USDT"},
    {"symbol": "ADA/USDT"},
    {"symbol": "AVAX/USDT"},
    {"symbol": "LINK/USDT"},
    {"symbol": "MATIC/USDT"},
    {"symbol": "DOT/USDT"},
    {"symbol": "TRX/USDT"},
    {"symbol": "LTC/USDT"},
    {"symbol": "NEAR/USDT"},
    {"symbol": "ATOM/USDT"},
    {"symbol": "SUI/USDT"},
    {"symbol": "APT/USDT"},
    {"symbol": "ARB/USDT"},
    {"symbol": "OP/USDT"},
    {"symbol": "FET/USDT"},
    {"symbol": "RNDR/USDT"},
    {"symbol": "INJ/USDT"},
    {"symbol": "TIA/USDT"},
    {"symbol": "SEI/USDT"},
    {"symbol": "PEPE/USDT"},
    {"symbol": "BEAT/USDT"},
    {"symbol": "RIVER/USDT"},
    {"symbol": "POWER/USDT"},
    {"symbol": "ANIME/USDT"},
    {"symbol": "ASR/USDT"},
    {"symbol": "CYS/USDT"},
    {"symbol": "RAVE/USDT"},
    {"symbol": "TRUTH/USDT"},
    {"symbol": "AKE/USDT"},
    {"symbol": "ALPINE/USDT"},
    {"symbol": "H/USDT"},
    {"symbol": "XPIN/USDT"},
    {"symbol": "NIGHT/USDT"},
    {"symbol": "BANK/USDT"},
    {"symbol": "AVNT/USDT"},
    {"symbol": "EPIC/USDT"},
    {"symbol": "MET/USDT"},
    {"symbol": "MYX/USDT"},
    {"symbol": "LYN/USDT"},
    {"symbol": "YGG/USDT"},
    # Tambahkan koin lain di sini
]