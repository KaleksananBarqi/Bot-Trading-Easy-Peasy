# [FILE: src/config.py]

# ... (Kode sebelumnya tetap sama)

# --- 1.B AI & DATA SOURCE CONFIG ---
# Ubah persona AI agar berpikir seperti Swing Trader
AI_SYSTEM_ROLE = "You are an expert Crypto Swing Trading AI. You focus on Daily Trends, patience, and High Risk-to-Reward setups. You ignore market noise."

# ...

# --- 2. GLOBAL RISK & SYSTEM FILES ---
DEFAULT_LEVERAGE = 5          # [UBAH] Swing wajib leverage rendah (3x - 5x) agar tidak mudah kena likuidasi
DEFAULT_MARGIN_TYPE = 'isolated' 
DEFAULT_AMOUNT_USDT = 20      # [UBAH] Sesuaikan size, biasanya swing butuh margin lebih besar per posisi

# ...

# --- 3. FILTER BTC (GLOBAL TREND) ---
BTC_SYMBOL = 'BTC/USDT'
BTC_TIMEFRAME = '1d'          # [PENTING] Tren utama dilihat dari DAILY (D1)
BTC_EMA_PERIOD = 50           # Filter tren jangka panjang

# --- 5. TEKNIKAL & EKSEKUSI ---
TIMEFRAME_TREND = '1d'        # [PENTING] Analisa tren per koin menggunakan Daily
TIMEFRAME_EXEC = '1h'         # [PENTING] Eksekusi (cari entry) di H1 atau H4 (H1 lebih presisi untuk sniper)
LIMIT_TREND = 200             
LIMIT_EXEC = 500

ATR_PERIOD = 14             
ATR_MULTIPLIER_SL = 2.0       # [UBAH] Stop Loss lebar (2x ATR) untuk memberi "ruang napas" pada volatilitas harian
ATR_MULTIPLIER_TP1 = 5.0      # [UBAH] Target Profit besar (Min RR 1:2.5). Kita incar "Home Run"

MIN_ORDER_USDT = 10           
ORDER_TYPE = 'limit'          # [SARAN] Gunakan Limit Order untuk entry yang lebih sabar
COOLDOWN_IF_PROFIT = 43200    # [UBAH] 12 Jam. Setelah profit, istirahat dulu, jangan greedy.
COOLDOWN_IF_LOSS = 3600       # 1 Jam. Jika kena SL, re-evaluasi sebentar.

# ...

# --- 6. SETTING STRATEGI SNIPER (MODIFIED) ---
# A. Sniper / Liquidity Hunt Strategy
USE_LIQUIDITY_HUNT = True     # Tetap True, karena kita mau entry di pucuk shadow (wick) saat pullback
TRAP_SAFETY_SL = 1.0          # Geser SL lebih aman

# B. Trend Trap (INI KUNCI SWING)
USE_TREND_TRAP_STRATEGY = True  
TREND_TRAP_ADX_MIN = 20       # Turunkan sedikit agar tren awal terdeteksi

# C. Sideways Scalp (MATIKAN)
USE_SIDEWAYS_SCALP = False    # [PENTING] Matikan! Swing trader tidak main di pasar sideways/choppy.

# ... (Daftar Koin sesuaikan dengan leverage baru, misal semua set ke 5x atau 10x max)