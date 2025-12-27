# file: backtest_runner.py (REVISI)
"""
File utama untuk menjalankan backtest dengan data historis
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
import os
import sys

# Tambahkan path untuk import modul
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings('ignore')

from data_fetcher import HistoricalDataFetcher
from backtest import BacktestEngine
import config

def run_complete_backtest():
    """
    Fungsi utama untuk menjalankan backtest lengkap
    """
    print("="*60)
    print("🚀 BACKTEST RUNNER - PULLBACK SNIPER STRATEGY")
    print("="*60)
    
    # 1. Konfigurasi Backtest
    START_DATE = "2024-01-01"
    END_DATE = "2024-03-01"
    INITIAL_CAPITAL = 10000
    
    print(f"\n1. KONFIGURASI BACKTEST")
    print(f"   📅 Periode: {START_DATE} hingga {END_DATE}")
    print(f"   💰 Modal Awal: ${INITIAL_CAPITAL:,.2f}")
    print(f"   🎯 Jumlah Simbol: {len(config.DAFTAR_KOIN)}")
    
    # 2. Load atau Fetch Data
    print(f"\n2. MEMUAT DATA HISTORIS")
    
    fetcher = HistoricalDataFetcher()
    
    # Coba load dari cache dulu
    print("   🔍 Mencari data di cache...")
    all_data = fetcher.load_data_from_csv('historical_data')
    
    if not all_data:
        print("   ⚠️ Tidak ada data di cache, jalankan data_fetcher.py terlebih dahulu")
        print("   Atau tekan Enter untuk mengambil data sekarang...")
        input()
        
        # Import dan jalankan fungsi fetch
        from data_fetcher import fetch_and_save_data
        all_data = fetch_and_save_data()
    
    if not all_data:
        print("❌ Tidak ada data untuk backtest, keluar...")
        return None
    
    # Pisahkan BTC data
    btc_data_dict = all_data.get('BTC/USDT', None)
    
    # Ekstrak DataFrame BTC dari dictionary
    if btc_data_dict and isinstance(btc_data_dict, dict):
        btc_data = btc_data_dict.get('1h', None)
    else:
        btc_data = None
    
    # Hapus BTC dari symbol_data
    symbol_data = {k: v for k, v in all_data.items() if k != 'BTC/USDT'}
    
    # Validasi data
    symbol_data = fetcher.validate_data(symbol_data)
    
    # Filter simbol yang memiliki data lengkap
    valid_symbols = []
    for symbol, timeframes in symbol_data.items():
        if '5m' in timeframes and '1h' in timeframes:
            valid_symbols.append(symbol)
        else:
            print(f"   ⚠️ {symbol}: Data tidak lengkap, skip...")
    
    print(f"   ✅ {len(valid_symbols)} simbol memiliki data lengkap")
    
    if len(valid_symbols) == 0:
        print("❌ Tidak ada simbol dengan data lengkap, keluar...")
        return None
    
    # Filter DAFTAR_KOIN hanya untuk simbol yang valid
    valid_coins = [coin for coin in config.DAFTAR_KOIN if coin['symbol'] in valid_symbols]
    
    # Update config.DAFTAR_KOIN untuk backtest
    original_daftar_koin = config.DAFTAR_KOIN.copy()
    config.DAFTAR_KOIN = valid_coins
    
    # 3. Jalankan Backtest
    print(f"\n3. MENJALANKAN BACKTEST")
    
    backtester = BacktestEngine(
        initial_capital=INITIAL_CAPITAL,
        commission=0.0004  # 0.04% commission
    )
    
    # Jalankan backtest
    try:
        backtester.run_backtest(
            symbol_data=symbol_data,
            btc_data=btc_data,
            start_date=START_DATE,
            end_date=END_DATE
        )
    except Exception as e:
        print(f"❌ Error saat menjalankan backtest: {e}")
        # Restore original config
        config.DAFTAR_KOIN = original_daftar_koin
        return None
    
    # 4. Generate Report
    print(f"\n4. GENERATE LAPORAN")
    backtester.generate_report()
    
    # 5. Simpan Konfigurasi Backtest
    print(f"\n5. MENYIMPAN HASIL")
    
    # Buat folder results jika belum ada
    results_dir = 'backtest_results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Generate timestamp untuk nama file
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Simpan konfigurasi yang digunakan
    config_dict = {
        'start_date': START_DATE,
        'end_date': END_DATE,
        'initial_capital': INITIAL_CAPITAL,
        'commission': 0.0004,
        'symbols_tested': valid_symbols,
        'total_symbols': len(valid_symbols),
        'btc_data_available': btc_data is not None and not btc_data.empty,
        'timestamp': timestamp
    }
    
    config_file = os.path.join(results_dir, f'config_{timestamp}.json')
    with open(config_file, 'w') as f:
        import json
        json.dump(config_dict, f, indent=2)
    
    print(f"   💾 Konfigurasi disimpan: {config_file}")
    print(f"\n✅ Backtest selesai! Hasil tersimpan di folder '{results_dir}'")
    
    # Restore original config
    config.DAFTAR_KOIN = original_daftar_koin
    
    return backtester

def run_simple_backtest():
    """
    Versi sederhana backtest untuk testing
    """
    print("="*60)
    print("🧪 SIMPLE BACKTEST (Testing)")
    print("="*60)
    
    # Konfigurasi
    START_DATE = "2024-01-01"
    END_DATE = "2024-01-07"  # Hanya 1 minggu untuk testing cepat
    INITIAL_CAPITAL = 1000
    
    print(f"Periode: {START_DATE} hingga {END_DATE}")
    print(f"Modal: ${INITIAL_CAPITAL}")
    
    # Buat data dummy untuk testing
    print("\nMembuat data dummy untuk testing...")
    
    # Buat data BTC
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq='1h')
    np.random.seed(42)
    
    btc_prices = []
    price = 45000
    for _ in range(len(dates)):
        change = np.random.normal(0, 0.001)
        price *= (1 + change)
        btc_prices.append(price)
    
    btc_data = pd.DataFrame({
        'open': [p * 0.999 for p in btc_prices],
        'high': [p * 1.002 for p in btc_prices],
        'low': [p * 0.998 for p in btc_prices],
        'close': btc_prices,
        'volume': np.random.randint(10000, 50000, len(dates))
    }, index=dates)
    
    # Buat data untuk beberapa simbol
    symbol_data = {}
    
    # Hanya gunakan 2 simbol untuk testing
    test_symbols = config.DAFTAR_KOIN[:2]
    
    for coin_config in test_symbols:
        symbol = coin_config['symbol']
        
        # Buat data 5m
        dates_5m = pd.date_range(start=START_DATE, end=END_DATE, freq='5min')
        prices_5m = []
        price = 100 if 'BTC' not in symbol else 45000
        
        for _ in range(len(dates_5m)):
            change = np.random.normal(0, 0.0005)
            price *= (1 + change)
            prices_5m.append(price)
        
        df_5m = pd.DataFrame({
            'open': [p * 0.999 for p in prices_5m],
            'high': [p * 1.0015 for p in prices_5m],
            'low': [p * 0.9985 for p in prices_5m],
            'close': prices_5m,
            'volume': np.random.randint(1000, 10000, len(dates_5m))
        }, index=dates_5m)
        
        # Buat data 1h dari data 5m
        df_1h = df_5m.resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        symbol_data[symbol] = {
            '5m': df_5m,
            '1h': df_1h
        }
        
        print(f"✓ {symbol}: {len(df_5m)} bar 5m, {len(df_1h)} bar 1h")
    
    # Jalankan backtest
    backtester = BacktestEngine(
        initial_capital=INITIAL_CAPITAL,
        commission=0.0004
    )
    
    print("\n🚀 Menjalankan backtest...")
    backtester.run_backtest(
        symbol_data=symbol_data,
        btc_data=btc_data,
        start_date=START_DATE,
        end_date=END_DATE
    )
    
    print("\n📊 Generate report...")
    backtester.generate_report()
    
    return backtester

if __name__ == "__main__":
    print("\nPILIHAN BACKTEST:")
    print("1. Backtest Lengkap (dengan data real dari Binance)")
    print("2. Backtest Sederhana (dengan data dummy untuk testing)")
    print("3. Keluar")
    
    choice = input("\nPilih opsi (1/2/3): ").strip()
    
    if choice == "1":
        backtester = run_complete_backtest()
    elif choice == "2":
        backtester = run_simple_backtest()
    elif choice == "3":
        print("Keluar...")
    else:
        print("Pilihan tidak valid, menjalankan backtest sederhana...")
        backtester = run_simple_backtest()