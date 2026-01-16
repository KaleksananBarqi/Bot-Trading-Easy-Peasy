
import asyncio
import os
import sys
import ccxt.async_support as ccxt
import pandas as pd

# Menambahkan folder 'src' ke sys.path agar 'import config' mencari di dalam src/
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)
sys.path.insert(0, project_root)

import config
from src.utils.helper import logger
from src.modules.market_data import MarketDataManager
from src.modules.pattern_recognizer import PatternRecognizer

async def test_vision_real_market():
    """
    Skrip khusus untuk mengetes AI VISION menggunakan data market sungguhan.
    1. Fetch data real dari Binance.
    2. Generate gambar chart.
    3. Analisa oleh AI.
    4. Output nama pattern (jika ada).
    """
    logger.info("🚀 Memulai Test AI Vision dengan Data Market Sungguhan...")

    # 1. Inisialisasi Exchange (Binance)
    exchange = ccxt.binance({
        'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
        'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
            'recvWindow': config.API_RECV_WINDOW
        }
    })
    if config.PAKAI_DEMO:
        exchange.enable_demo_trading(True)

    try:
        # 2. Inisialisasi Market Data & Pattern Recognizer
        market_data = MarketDataManager(exchange)
        pattern_recognizer = PatternRecognizer(market_data)

        # 3. Ambil Data Real untuk satu koin (misal BTC/USDT)
        symbol = "BTC/USDT"
        logger.info(f"📥 Mengambil data real untuk {symbol}...")
        
        # Ambil data OHLCV untuk timeframe setup (sesuai config)
        bars_setup = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_SETUP, limit=config.LIMIT_SETUP)
        
        # Simpan ke market_store agar pattern_recognizer bisa baca
        async with market_data.data_lock:
            if symbol not in market_data.market_store:
                market_data.market_store[symbol] = {}
            market_data.market_store[symbol][config.TIMEFRAME_SETUP] = bars_setup

        # 4. Generate Gambar (Langkah ini mengetes apakah mplfinance jalan)
        logger.info("📸 Mencoba generate gambar chart...")
        img_base64 = pattern_recognizer.generate_chart_image(symbol)
        
        if img_base64:
            logger.info("✅ Gambar berhasil di-generate (Base64 string tersedia).")
            # Simpan preview gambar ke file lokal untuk dicek manual jika perlu
            import base64
            with open("test_vision_chart.png", "wb") as f:
                f.write(base64.b64decode(img_base64))
            logger.info("📂 Preview chart disimpan ke 'test_vision_chart.png'")
        else:
            logger.error("❌ Gagal generate gambar chart.")
            return

        # 5. Analisis oleh AI Vision
        logger.info(f"🧠 Mengirim gambar ke AI Vision ({config.AI_VISION_MODEL})...")
        analysis_result = await pattern_recognizer.analyze_pattern(symbol)
        
        print("\n" + "="*50)
        print(f"HASIL ANALISIS AI UNTUK {symbol}:")
        print("-" * 50)
        print(analysis_result)
        print("="*50 + "\n")

    except Exception as e:
        logger.error(f"❌ Terjadi kesalahan saat testing: {e}")
    finally:
        await exchange.close()
        logger.info("🏁 Test selesai dan koneksi exchange ditutup.")

if __name__ == "__main__":
    if not config.AI_API_KEY:
        print("❌ ERROR: AI_API_KEY tidak ditemukan di .env atau config.py")
        sys.exit(1)
        
    if not config.USE_PATTERN_RECOGNITION:
        print("⚠️ WARNING: USE_PATTERN_RECOGNITION di config.py bernilai False. Mengabaikan dan tetap running test...")
        config.USE_PATTERN_RECOGNITION = True

    asyncio.run(test_vision_real_market())
