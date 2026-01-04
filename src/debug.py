import asyncio
import ccxt.async_support as ccxt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def debug_account():
    print("🕵️‍♂️ MEMULAI DIAGNOSA AKUN...")
    
    # 1. Setup Exchange (Sesuai Config Bot)
    use_demo = True # Kita asumsikan Demo sesuai screenshot
    api_key = os.getenv("BINANCE_TESTNET_KEY")
    secret = os.getenv("BINANCE_TESTNET_SECRET")
    
    print(f"🔑 Menggunakan API Key (Depan): {api_key[:10]}...")
    
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'future'}
    })
    
    if use_demo:
        exchange.enable_demo_trading(True)
        print("🌍 Mode: TESTNET (DEMO)")
    else:
        print("🌍 Mode: LIVE (REAL)")

    try:
        # 2. Cek Saldo (Untuk mencocokkan dengan screenshot)
        balance = await exchange.fetch_balance()
        usdt_free = balance['USDT']['free']
        usdt_total = balance['USDT']['total']
        print(f"\n💰 SALDO DI BOT:")
        print(f"   Free : ${usdt_free:,.2f}")
        print(f"   Total: ${usdt_total:,.2f}")
        print("   (Coba cocokkan angka ini dengan saldo di HP kamu!)")

        # 3. Cek Posisi AVAX
        print(f"\n🔍 CEK POSISI AVAX/USDT:")
        positions = await exchange.fetch_positions(['AVAX/USDT'])
        for pos in positions:
            if float(pos['contracts']) > 0:
                print(f"   ✅ Ada Posisi: {pos['side']} {pos['contracts']} AVAX")
                print(f"   Entry Price: {pos['entryPrice']}")
            else:
                print("   ❌ Tidak ada posisi aktif.")

        # 4. Cek Order (MATA ELANG - RAW API)
        print(f"\n🦅 CEK ORDER (RAW API - AVAXUSDT):")
        # Ini metode yang sama persis dengan yang kita pakai di main.py
        raw_orders = await exchange.fapiPrivateGetOpenOrders({'symbol': 'AVAXUSDT'})
        
        print(f"   Jumlah Order Ditemukan: {len(raw_orders)}")
        
        if len(raw_orders) > 0:
            for o in raw_orders:
                print(f"   - ID: {o['orderId']} | Type: {o['type']} | Status: {o['status']} | ReduceOnly: {o['reduceOnly']}")
        else:
            print("   ⚠️ API MEMANG MENGEMBALIKAN KOSONG (0 ORDER).")
            print("   Artinya: Di akun yang terhubung API key ini, memang tidak ada order.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_account())