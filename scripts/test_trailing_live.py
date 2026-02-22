"""
🧪 Manual Trailing Stop Test Script
====================================
Skrip ini untuk menguji fitur Native Trailing Stop secara langsung di Binance Demo.

CARA PAKAI:
1. Buka posisi manual di Binance Testnet (misal BUY BTC/USDT)
2. Jalankan skrip ini: python scripts/test_trailing_live.py
3. Skrip akan:
   - Deteksi posisi terbuka
   - Hitung activation price (80% menuju TP)
   - Pasang TRAILING_STOP_MARKET dengan activationPrice ke Binance
"""

import asyncio
import sys
import os

# Setup path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

import ccxt.async_support as ccxt
import config


async def main():
    print("=" * 60)
    print("🧪 TRAILING STOP MANUAL TEST")
    print("=" * 60)

    # 1. Setup Exchange
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
        print("🧪 Mode: DEMO (Testnet)")
    else:
        print("⚠️  Mode: LIVE!")

    try:
        # 2. Ambil posisi terbuka
        positions = await exchange.fetch_positions()
        active = [p for p in positions if abs(float(p['contracts'])) > 0]

        if not active:
            print("\n❌ Tidak ada posisi terbuka!")
            print("💡 Buka posisi di Binance Demo terlebih dahulu, lalu jalankan skrip ini lagi.")
            return

        print(f"\n📊 Ditemukan {len(active)} posisi terbuka:\n")

        for i, pos in enumerate(active):
            symbol = pos['symbol']
            side = pos['side'].upper()  # 'long' -> 'LONG'
            entry_price = float(pos['entryPrice'])
            qty = abs(float(pos['contracts']))
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))

            print(f"  [{i+1}] {symbol}")
            print(f"      Side: {side}")
            print(f"      Entry: {entry_price}")
            print(f"      Qty: {qty}")
            print(f"      uPnL: {unrealized_pnl:+.4f} USDT")

        # 3. Pilih posisi
        if len(active) == 1:
            chosen = active[0]
            print(f"\n✅ Auto-select: {chosen['symbol']}")
        else:
            idx = int(input(f"\nPilih posisi [1-{len(active)}]: ")) - 1
            chosen = active[idx]

        symbol = chosen['symbol']
        side = chosen['side'].upper()
        entry_price = float(chosen['entryPrice'])
        qty = abs(float(chosen['contracts']))

        # 4. Hitung TP dan Activation Price
        # Ambil ATR atau gunakan default TP%
        # Untuk simplicity, kita hitung TP berdasarkan config
        atr_tp_multiplier = config.ATR_MULTIPLIER_TP1
        atr_sl_multiplier = config.TRAP_SAFETY_SL

        # Fetch harga saat ini untuk estimasi ATR
        ticker = await exchange.fetch_ticker(symbol)
        current_price = float(ticker['last'])

        # Coba hitung dari ATR (simplified: gunakan % default jika tidak ada ATR)
        # Default: TP = entry ± DEFAULT_TP_PERCENT
        tp_percent = config.DEFAULT_TP_PERCENT
        
        if side == 'LONG':
            tp_price = entry_price * (1 + tp_percent)
        else:
            tp_price = entry_price * (1 - tp_percent)

        # Hitung activation price (80% menuju TP)
        distance = abs(tp_price - entry_price)
        threshold = config.TRAILING_ACTIVATION_THRESHOLD  # 0.80

        if side == 'LONG':
            activation_price = entry_price + (distance * threshold)
        else:
            activation_price = entry_price - (distance * threshold)

        # Callback rate
        callback_rate = config.TRAILING_CALLBACK_RATE
        rate_percent = round(callback_rate * 100, 1)
        rate_percent = max(rate_percent, config.NATIVE_TRAILING_MIN_RATE)
        rate_percent = min(rate_percent, config.NATIVE_TRAILING_MAX_RATE)

        print(f"\n{'=' * 60}")
        print(f"🎯 TRAILING STOP PLAN")
        print(f"{'=' * 60}")
        print(f"  Symbol:           {symbol}")
        print(f"  Side:             {side}")
        print(f"  Entry:            {entry_price}")
        print(f"  Current Price:    {current_price}")
        print(f"  TP (estimated):   {tp_price:.4f}")
        print(f"  Distance to TP:   {distance:.4f}")
        print(f"  80% Threshold:    {threshold * 100}%")
        print(f"  Activation Price: {activation_price:.4f}")
        print(f"  Callback Rate:    {rate_percent}%")
        print(f"  Quantity:         {qty}")
        print(f"{'=' * 60}")

        confirm = input("\n🚀 Pasang trailing stop? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("❌ Dibatalkan.")
            return

        # 5. Pasang TRAILING_STOP_MARKET
        side_api = 'sell' if side == 'LONG' else 'buy'

        params = {
            'callbackRate': rate_percent,
            'activationPrice': exchange.price_to_precision(symbol, activation_price),
            'reduceOnly': True,
            'workingType': 'MARK_PRICE'
        }

        print(f"\n📤 Mengirim order ke Binance...")
        print(f"   Type: TRAILING_STOP_MARKET")
        print(f"   Side: {side_api}")
        print(f"   Qty:  {qty}")
        print(f"   Params: {params}")

        order = await exchange.create_order(
            symbol=symbol,
            type='TRAILING_STOP_MARKET',
            side=side_api,
            amount=qty,
            price=None,
            params=params
        )

        print(f"\n✅ TRAILING STOP BERHASIL DIPASANG!")
        print(f"   Order ID: {order['id']}")
        print(f"   Status:   {order.get('status', 'N/A')}")
        print(f"\n💡 Trailing akan aktif ketika harga mencapai {activation_price:.4f}")
        print(f"   Setelah aktif, trailing akan mengikuti dengan callback {rate_percent}%")

    except Exception as e:
        print(f"\n💀 ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())
