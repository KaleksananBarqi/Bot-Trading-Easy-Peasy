
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
async def kirim_tele(pesan, alert=False, channel='default'):
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
        
        def send_request():
            data = {
                'chat_id': chat_id, 
                'text': f"{prefix}{pesan}", 
                'parse_mode': 'HTML'
            }
            # Message Thread ID hanya support di default channel biasanya, atau jika user set var khusus (belum ada).
            # Asumsi: Sentimen channel mungkin topik terpisah atau grup terpisah. 
            # Jika user set unique Token/ChatID, kemungkinan besar itu channel/grup berbeda.
            # Jadi kita hanya pakai message_thread_id untuk default channel jika ada.
            
            if channel == 'default' and config.TELEGRAM_MESSAGE_THREAD_ID:
                data['message_thread_id'] = config.TELEGRAM_MESSAGE_THREAD_ID
            elif channel == 'sentiment' and config.TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT:
                data['message_thread_id'] = config.TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT
                
            return requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data=data
            )
        
        response = await asyncio.to_thread(send_request)
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
def format_currency(num):
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
