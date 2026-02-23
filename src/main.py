
import asyncio
import json
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
from src.utils.helper import logger, setup_logger
from src.modules.mongo_manager import MongoManager
import src.modules.trading_engine as engine

# Re-init logger for master
logger = setup_logger()

# Disable noisy logging from httpx/telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

async def check_auth(update: Update) -> bool:
    """Security check to only allow authorized user (from TELEGRAM_CHAT_ID)."""
    user_id = str(update.effective_chat.id)
    if user_id != str(config.TELEGRAM_CHAT_ID):
        await update.message.reply_text("⛔ Unauthorized user.")
        return False
    return True

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    if engine.is_running:
        await update.message.reply_text("⚠️ Trading Engine was already RUNNING.")
        return
        
    await update.message.reply_text("🚀 Starting Trading Engine worker...")
    
    # We don't await the engine start as it's an infinite loop inside.
    # We just trigger the engine.
    started = await engine.start_engine()
    if started:
        await update.message.reply_text("✅ Trading Engine successfully started.")
    else:
        await update.message.reply_text("❌ Failed to start Trading Engine.")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    if not engine.is_running:
        await update.message.reply_text("⚠️ Trading Engine is already STOPPED.")
        return
        
    await update.message.reply_text("🛑 Stopping Trading Engine. Please wait, closing active streams...")
    
    stopped = await engine.stop_engine()
    if stopped:
        await update.message.reply_text("✅ Trading Engine successfully stopped.")
    else:
        await update.message.reply_text("❌ Failed to stop Trading Engine.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    mongo = MongoManager()
    is_demo = mongo.get_is_demo()
    koin_list = mongo.get_daftar_koin()
    
    run_status = "🟢 RUNNING" if engine.is_running else "🔴 STOPPED"
    mode_str = "🧪 DEMO (Testnet)" if is_demo else "💰 REAL (Live)"
    
    koin_symbols = [k.get('symbol', '?') for k in koin_list]
    koin_count = len(koin_symbols)
    
    msg = (
        f"📊 <b>BOT STATUS</b>\n"
        f"Engine: {run_status}\n"
        f"Mode: {mode_str}\n"
        f"Koin Dipantau: {koin_count}\n"
        f"List: {', '.join(koin_symbols)[:100]}...\n"
    )
    
    await update.message.reply_html(msg)

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Penggunaan: /mode [demo/real]")
        return
        
    mode_input = context.args[0].lower()
    if mode_input not in ['demo', 'real']:
        await update.message.reply_text("❌ Mode harus 'demo' atau 'real'.")
        return
        
    target_demo = (mode_input == 'demo')
    
    mongo = MongoManager()
    mongo.set_is_demo(target_demo)
    
    await update.message.reply_text(f"✅ Mode berhasil diubah ke {mode_input.upper()}.")
    
    if engine.is_running:
        await update.message.reply_text("⏳ Restarting engine to apply new API Keys...")
        await engine.stop_engine()
        await asyncio.sleep(2)  # Give time to cleanup connections
        await engine.start_engine()
        await update.message.reply_text("✅ Engine restarted successfully.")

async def cmd_addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    raw_text = ' '.join(context.args).strip()
    if not raw_text:
        await update.message.reply_text(
            "ℹ️ Penggunaan:\n"
            "Simple: /addcoin BTC/USDT LAYER1 20 10\n"
            "Advanced: /addcoin {\"symbol\": \"BTC/USDT\", \"category\": \"LAYER1\", \"leverage\": 20, ...}"
        )
        return
        
    koin_data = {}
    
    # Try parsing as JSON first
    if raw_text.startswith('{') and raw_text.endswith('}'):
        try:
            koin_data = json.loads(raw_text)
        except json.JSONDecodeError:
            await update.message.reply_text("❌ Format JSON tidak valid.")
            return
    else:
        # Simple format parsing
        parts = raw_text.split()
        if len(parts) < 4:
            await update.message.reply_text("❌ Format simple butuh 4 parameter: [simbol] [kategori] [leverage] [amount]")
            return
            
        try:
            symbol = parts[0].upper()
            category = parts[1].upper()
            leverage = int(parts[2])
            amount = float(parts[3])
            
            koin_data = {
                "symbol": symbol,
                "category": category,
                "leverage": leverage,
                "margin_type": "isolated",
                "amount": amount,
                "btc_corr": True,
                "keywords": [symbol.split('/')[0].lower()]
            }
        except ValueError:
            await update.message.reply_text("❌ Invalid value untuk leverage (harus bulat) atau amount (harus angka).")
            return
            
    # Save to MongoDB
    if "symbol" not in koin_data:
        await update.message.reply_text("❌ Koin data harus memiliki 'symbol'.")
        return
        
    mongo = MongoManager()
    success = mongo.add_koin(koin_data)
    
    if success:
        await update.message.reply_text(f"✅ Koin {koin_data['symbol']} berhasil ditambahkan/diupdate.")
    else:
        await update.message.reply_text("❌ Gagal menyimpan data ke database.")

async def cmd_delcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Penggunaan: /delcoin [simbol]")
        return
        
    symbol = context.args[0].upper()
    mongo = MongoManager()
    
    success = mongo.remove_koin(symbol)
    if success:
        await update.message.reply_text(f"✅ Koin {symbol} berhasil dihapus dari daftar.")
    else:
        await update.message.reply_text(f"❌ Koin {symbol} tidak ditemukan dalam daftar.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    
    help_text = (
        "🤖 <b>EASY PEASY BOT REMOTE CONTROL</b>\n\n"
        "🟢 /start - Jalankan Trading Engine\n"
        "🔴 /stop - Hentikan Trading Engine\n"
        "📊 /status - Lihat status engine & config\n"
        "⚙️ /mode [demo/real] - Pindah environment\n"
        "➕ /addcoin [symbol] [kategori] [lev] [amt] - Tambah koin\n"
        "➖ /delcoin [symbol] - Hapus koin\n"
    )
    await update.message.reply_html(help_text)

def main():
    """Bot Master Entry Point."""
    if not config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN belum di set di .env")
        return

    logger.info("Initializing Master Telegram Bot listener...")
    
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("addcoin", cmd_addcoin))
    app.add_handler(CommandHandler("delcoin", cmd_delcoin))
    app.add_handler(CommandHandler("help", cmd_help))
    
    logger.info("✅ Master Listener is ready. Waiting for commands on Telegram...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # Pastikan dependensi asyncio / uvloop berjalan baik di windows
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    main()