
import logging
import sys
import os
import requests
import asyncio
from datetime import datetime, timedelta, timezone
from src import config

# ==========================================
# CUSTOM LOGGER & TIME UTILS (WIB TIME)
# ==========================================
WIB_OFFSET = timezone(timedelta(hours=7))

def get_wib_now():
    """Mengembalikan datetime sekarang dalam WIB (UTC+7)."""
    return datetime.now(timezone.utc).astimezone(WIB_OFFSET)

def convert_dt_to_wib(dt):
    """Mengubah datetime (UTC/Naive) ke WIB."""
    if dt is None: return None
    if dt.tzinfo is None:
        # Assume UTC if naive, or system local? 
        # Better safe: assume UTC if coming from timestamp, or local if coming from now()
        # Let's standardize on UTC input for safety everywhere in this bot
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB_OFFSET)

def convert_timestamp_to_wib_str(ts, fmt='%a %b %d %H:%M:%S %Y'):
    """Mengubah unix timestamp ke string WIB."""
    if not ts: return "-"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(WIB_OFFSET)
    return dt.strftime(fmt)

def wib_time(*args):
    """Converter untuk logging agar menggunakan WIB."""
    return get_wib_now().timetuple()

def setup_logger():
    # [FIX] Force UTF-8 untuk Windows Console agar emoji tidak crash
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Reset handlers if exist (to prevent duplicates during reload)
    if logger.handlers:
        logger.handlers = []

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')
    formatter.converter = wib_time 

    # File Handler
    file_handler = logging.FileHandler(config.LOG_FILENAME, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

# ==========================================
# TELEGRAM NOTIFIER
# ==========================================
async def kirim_tele(pesan: str, alert: bool = False, channel: str = 'default') -> None:
    """
    Kirim pesan ke Telegram.
    :param channel: 'default' (Sinyal Utama) atau 'sentiment' (Analisa Berita)
    """
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        
        # Tentukan Token & ChatID berdasarkan channel
        bot_token = config.TELEGRAM_TOKEN
        chat_id = config.TELEGRAM_CHAT_ID
        
        if channel == 'sentiment':
            if config.TELEGRAM_TOKEN_SENTIMENT and config.TELEGRAM_CHAT_ID_SENTIMENT:
                bot_token = config.TELEGRAM_TOKEN_SENTIMENT
                chat_id = config.TELEGRAM_CHAT_ID_SENTIMENT
            else:
                # Fallback atau skip jika credentials sentimen tidak ada
                logger.warning("⚠️ Credentials Sentiment Telegram kosong, menggunakan default channel.")
                # Kita bisa memilih untuk tetap kirim ke default atau return.
                # Sesuai request user: "beda untuk dikirimnya". Jika kosong, lebih aman tetap kirim (fallback) atau log error.
                # Mari kita gunakan fallback ke default agar info tidak hilang, tapi beri log warning.
        
        data = {
            'chat_id': chat_id, 
            'text': f"{prefix}{pesan}", 
            'parse_mode': 'HTML'
        }
        
        # Message Thread ID logic
        if channel == 'default' and config.TELEGRAM_MESSAGE_THREAD_ID:
            data['message_thread_id'] = config.TELEGRAM_MESSAGE_THREAD_ID
        elif channel == 'sentiment' and config.TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT:
            data['message_thread_id'] = config.TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        response = await asyncio.to_thread(requests.post, url, data=data, timeout=10)
        if response.status_code != 200:
            error_details = response.text
            logger.error(f"❌ Telegram Send Failed ({channel}) Status {response.status_code}: {error_details}")
            
            # Additional Hint for User
            if response.status_code == 400 and "chat not found" in error_details:
                logger.warning(f"💡 HINT: Pastikan Bot Token '{bot_token[:5]}...' sudah di-invite ke Chat ID '{chat_id}'!")
            elif response.status_code == 401:
                logger.warning(f"💡 HINT: Token Bot mungkin salah atau expired.")
    except Exception as e:
        logger.error(f"❌ Telegram Exception: {e}")

def kirim_tele_sync(pesan):
    """
    Fungsi khusus untuk kirim notif saat bot mati/crash.
    Menggunakan requests biasa (blocking) agar pesan pasti terkirim sebelum process kill.
    """
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': config.TELEGRAM_CHAT_ID, 
            'text': pesan, 
            'parse_mode': 'HTML'
        }
        if config.TELEGRAM_MESSAGE_THREAD_ID:
            data['message_thread_id'] = config.TELEGRAM_MESSAGE_THREAD_ID
        # Timeout 5 detik agar bot tidak hang selamanya jika internet mati
        requests.post(url, data=data, timeout=5) 
        print("✅ Notifikasi Telegram terkirim (Sync).")
    except Exception as e:
        print(f"❌ Gagal kirim notif exit: {e}")

# ==========================================
# FORMATTING TOOLS
# ==========================================
import time

# ... (rest of imports)

def get_next_rounded_time(interval_str: str) -> float:
    """
    Calculate the next fixed-time alignment timestamp (Unix Epoch based).
    Example: interval '1h' -> Returns next X:00:00 timestamp.
    """
    interval_seconds = parse_timeframe_to_seconds(interval_str)
    if interval_seconds <= 0: interval_seconds = 60
    
    now = time.time()
    # Calculate next aligned timestamp
    next_time = ((int(now) // interval_seconds) + 1) * interval_seconds
    return next_time

def format_currency(num: float | None) -> str:
    if num is None: return "0.00"
    return f"{num:,.2f}"

def parse_timeframe_to_seconds(tf_str: str) -> int:
    """
    Convert timeframe string (e.g. '1m', '1h') to seconds.
    Default to 60s if invalid.
    """
    if not tf_str: return 60
    
    unit = tf_str[-1].lower()
    try:
        val = int(tf_str[:-1])
    except ValueError:
        return 60
        
    if unit == 's': return val
    elif unit == 'm': return val * 60
    elif unit == 'h': return val * 3600
    elif unit == 'd': return val * 86400
    else: return 60


# ==========================================
# CONFIG HELPERS
# ==========================================

def get_coin_config(symbol: str) -> dict | None:
    """
    Cari konfigurasi koin dari config.DAFTAR_KOIN secara langsung
    (tanpa cache map) agar selalu mendapatkan data terbaru.
    Return None jika tidak ditemukan.
    """
    for coin in config.DAFTAR_KOIN:
        if coin.get('symbol') == symbol:
            return coin
    return None
def get_coin_leverage(symbol: str) -> int:
    """
    Ambil leverage untuk symbol tertentu.
    Return config.DEFAULT_LEVERAGE jika tidak ditemukan.
    """
    coin_cfg = get_coin_config(symbol)
    if coin_cfg:
        return coin_cfg.get('leverage', config.DEFAULT_LEVERAGE)
    return config.DEFAULT_LEVERAGE
