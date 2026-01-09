
import logging
import sys
import os
import requests
import asyncio
from datetime import datetime, timedelta, timezone
import config

# ==========================================
# CUSTOM LOGGER (WIB TIME)
# ==========================================
def wib_time(*args):
    utc_dt = datetime.now(timezone.utc)
    wib_dt = utc_dt + timedelta(hours=7)
    return wib_dt.timetuple()

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
async def kirim_tele(pesan, alert=False):
    try:
        prefix = "⚠️ <b>SYSTEM ALERT</b>\n" if alert else ""
        await asyncio.to_thread(requests.post,
                                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                                data={'chat_id': config.TELEGRAM_CHAT_ID, 'text': f"{prefix}{pesan}", 'parse_mode': 'HTML'})
    except: pass

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
        # Timeout 5 detik agar bot tidak hang selamanya jika internet mati
        requests.post(url, data=data, timeout=5) 
        print("✅ Notifikasi Telegram terkirim (Sync).")
    except Exception as e:
        print(f"❌ Gagal kirim notif exit: {e}")

# ==========================================
# FORMATTING TOOLS
# ==========================================
    if num is None: return "0.00"
    return f"{num:,.2f}"

def parse_timeframe_to_seconds(tf_str):
    """
    Convert timeframe string (e.g. '1m', '1h') to seconds.
    Default to 60s if invalid.
    """
    if not tf_str: return 60
    
    unit = tf_str[-1].lower()
    try:
        val = int(tf_str[:-1])
    except:
        return 60
        
    if unit == 's': return val
    elif unit == 'm': return val * 60
    elif unit == 'h': return val * 3600
    elif unit == 'd': return val * 86400
    else: return 60
