# file: data_fetcher.py (REVISI)
import ccxt
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time
import os
import json
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class HistoricalDataFetcher:
    """
    Kelas untuk mengambil data historis dari Binance untuk keperluan backtesting
    """
    
    def __init__(self, use_testnet: bool = False):
        """
        Inisialisasi fetcher data
        
        Args:
            use_testnet: True untuk menggunakan testnet Binance
        """
        if use_testnet:
            self.exchange = ccxt.binance({
                'apiKey': 'test_key',
                'secret': 'test_secret',
                'enableRateLimit': True,
                'options': {'defaultType': 'future'},
                'urls': {'api': 'https://testnet.binancefuture.com'}
            })
        else:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {'defaultType': 'future'}
            })
        
        # Cache untuk menyimpan data yang sudah di-fetch
        self.data_cache = {}
        
        # Mapping timeframe ke milliseconds
        self.timeframe_ms = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
        }
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, 
                   start_date: str, end_date: str) -> pd.DataFrame:
        """
        Mengambil data OHLCV dari Binance
        
        Args:
            symbol: Pair trading (contoh: 'BTC/USDT')
            timeframe: Timeframe data ('5m', '1h', dll)
            start_date: Tanggal mulai (format: 'YYYY-MM-DD')
            end_date: Tanggal akhir (format: 'YYYY-MM-DD')
            
        Returns:
            DataFrame dengan kolom OHLCV
        """
        print(f"📥 Mengambil data {symbol} {timeframe} dari {start_date} hingga {end_date}")
        
        try:
            # Konversi tanggal ke timestamp
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
            
            all_data = []
            current_ts = start_ts
            
            # Binance limit: 1000 candles per request
            limit = 1000
            
            # Hitung interval waktu per request
            timeframe_ms = self.timeframe_ms.get(timeframe, 60 * 60 * 1000)  # Default 1h
            chunk_ms = limit * timeframe_ms
            
            retry_count = 0
            max_retries = 3
            
            while current_ts < end_ts:
                try:
                    # Hitung end timestamp untuk chunk ini
                    chunk_end = min(current_ts + chunk_ms, end_ts)
                    
                    # Fetch data
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_ts,
                        limit=limit
                    )
                    
                    if not ohlcv:
                        print(f"⚠️ Tidak ada data untuk {symbol} pada {timeframe}")
                        break
                    
                    # Konversi ke DataFrame
                    chunk_df = pd.DataFrame(
                        ohlcv, 
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    )
                    
                    # Konversi timestamp ke datetime
                    chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'], unit='ms')
                    chunk_df.set_index('timestamp', inplace=True)
                    
                    # Filter hanya data dalam range yang diminta
                    chunk_df = chunk_df[chunk_df.index <= pd.to_datetime(end_ts, unit='ms')]
                    
                    all_data.append(chunk_df)
                    
                    # Update current timestamp untuk iterasi berikutnya
                    last_ts = chunk_df.index[-1]
                    current_ts = int(last_ts.timestamp() * 1000) + timeframe_ms
                    
                    # Jeda untuk menghindari rate limit
                    time.sleep(self.exchange.rateLimit / 1000)
                    
                    retry_count = 0  # Reset retry count setelah sukses
                    
                    print(f"   ✓ Diambil {len(chunk_df)} bar, total: {len(pd.concat(all_data) if all_data else [])}")
                    
                except ccxt.NetworkError as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"❌ Gagal mengambil data setelah {max_retries} percobaan: {e}")
                        break
                    print(f"⚠️ Network error, retry {retry_count}/{max_retries}...")
                    time.sleep(5)
                    
                except ccxt.ExchangeError as e:
                    print(f"❌ Exchange error: {e}")
                    break
                    
                except Exception as e:
                    print(f"❌ Error tidak terduga: {e}")
                    break
            
            if not all_data:
                print(f"❌ Tidak ada data yang berhasil diambil untuk {symbol}")
                return pd.DataFrame()
            
            # Gabungkan semua chunk
            full_df = pd.concat(all_data)
            
            # Hapus duplikat
            full_df = full_df[~full_df.index.duplicated(keep='first')]
            
            # Urutkan berdasarkan waktu
            full_df = full_df.sort_index()
            
            # Pastikan data dalam range yang diminta
            mask = (full_df.index >= pd.to_datetime(start_date)) & (full_df.index <= pd.to_datetime(end_date))
            full_df = full_df[mask]
            
            print(f"✅ Selesai: {len(full_df)} bar data untuk {symbol} {timeframe}")
            
            return full_df
            
        except Exception as e:
            print(f"❌ Error dalam fetch_ohlcv: {e}")
            return pd.DataFrame()
    
    def fetch_all_symbols_data(self, symbols: List[str], 
                              start_date: str, end_date: str,
                              timeframes: List[str] = None) -> Dict:
        """
        Mengambil data untuk semua simbol dalam berbagai timeframe
        
        Args:
            symbols: List simbol trading
            start_date: Tanggal mulai
            end_date: Tanggal akhir
            timeframes: List timeframe yang dibutuhkan (default: ['5m', '1h'])
            
        Returns:
            Dictionary dengan struktur {symbol: {timeframe: DataFrame}}
        """
        if timeframes is None:
            timeframes = ['5m', '1h']
        
        all_data = {}
        
        total_symbols = len(symbols)
        total_tasks = total_symbols * len(timeframes)
        current_task = 0
        
        for symbol in symbols:
            print(f"\n{'='*60}")
            print(f"📊 Memproses {symbol} ({symbols.index(symbol) + 1}/{total_symbols})")
            print(f"{'='*60}")
            
            symbol_data = {}
            
            for tf in timeframes:
                current_task += 1
                print(f"\n[{current_task}/{total_tasks}] Mengambil {symbol} {tf}...")
                
                # Cek cache dulu
                cache_key = f"{symbol}_{tf}_{start_date}_{end_date}"
                if cache_key in self.data_cache:
                    print(f"   ✓ Menggunakan data dari cache")
                    df = self.data_cache[cache_key]
                else:
                    # Fetch dari exchange
                    df = self.fetch_ohlcv(symbol, tf, start_date, end_date)
                    
                    # Simpan ke cache
                    if not df.empty:
                        self.data_cache[cache_key] = df
                
                if not df.empty:
                    symbol_data[tf] = df
                else:
                    print(f"   ⚠️ Data {symbol} {tf} kosong, skip...")
            
            if symbol_data:
                all_data[symbol] = symbol_data
        
        return all_data
    
    def save_data_to_csv(self, data_dict: Dict, base_path: str = 'historical_data'):
        """
        Menyimpan data ke file CSV untuk penggunaan ulang
        
        Args:
            data_dict: Dictionary data dari fetch_all_symbols_data
            base_path: Path folder penyimpanan
        """
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        
        saved_files = []
        
        for symbol, timeframes in data_dict.items():
            symbol_folder = os.path.join(base_path, symbol.replace('/', '_'))
            if not os.path.exists(symbol_folder):
                os.makedirs(symbol_folder)
            
            for tf, df in timeframes.items():
                if isinstance(df, pd.DataFrame):
                    filename = os.path.join(symbol_folder, f"{tf}.csv")
                    df.to_csv(filename)
                    saved_files.append(filename)
                    print(f"💾 Disimpan: {filename} ({len(df)} bar)")
                else:
                    print(f"⚠️ Warning: Data untuk {symbol} {tf} bukan DataFrame, tipe: {type(df)}")
        
        # Simpan metadata
        metadata = {
            'total_symbols': len(data_dict),
            'symbols': list(data_dict.keys()),
            'timeframes': list(next(iter(data_dict.values())).keys()) if data_dict else [],
            'saved_files': saved_files,
            'timestamp': datetime.now().isoformat()
        }
        
        metadata_file = os.path.join(base_path, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n📁 Metadata disimpan: {metadata_file}")
        
        return saved_files
    
    def load_data_from_csv(self, base_path: str = 'historical_data') -> Dict:
        """
        Memuat data dari file CSV yang sudah disimpan
        
        Args:
            base_path: Path folder data
            
        Returns:
            Dictionary dengan struktur yang sama seperti fetch_all_symbols_data
        """
        if not os.path.exists(base_path):
            print(f"❌ Folder {base_path} tidak ditemukan")
            return {}
        
        all_data = {}
        
        # Load metadata
        metadata_file = os.path.join(base_path, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            print(f"📂 Memuat data dari {metadata_file}")
        else:
            metadata = {}
            print(f"⚠️ Metadata tidak ditemukan, mencoba scan folder...")
        
        # Scan semua folder dalam base_path
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            
            if os.path.isdir(item_path) and not item.endswith('__pycache__'):
                symbol = item.replace('_', '/')
                symbol_data = {}
                
                # Cari file CSV dalam folder
                for file in os.listdir(item_path):
                    if file.endswith('.csv'):
                        tf = file.replace('.csv', '')
                        filepath = os.path.join(item_path, file)
                        
                        try:
                            df = pd.read_csv(filepath, index_col='timestamp', parse_dates=True)
                            symbol_data[tf] = df
                            print(f"   ✓ {symbol} {tf}: {len(df)} bar")
                        except Exception as e:
                            print(f"   ❌ Gagal memuat {filepath}: {e}")
                
                if symbol_data:
                    all_data[symbol] = symbol_data
        
        print(f"✅ Berhasil memuat data untuk {len(all_data)} simbol")
        
        return all_data
    
    def get_btc_data(self, start_date: str, end_date: str, 
                    timeframe: str = '1h') -> pd.DataFrame:
        """
        Mengambil data BTC khusus untuk filter trend
        
        Args:
            start_date: Tanggal mulai
            end_date: Tanggal akhir
            timeframe: Timeframe data (default: '1h')
            
        Returns:
            DataFrame data BTC
        """
        print(f"\n🎯 Mengambil data BTC/USDT untuk filter trend...")
        
        cache_key = f"BTC/USDT_{timeframe}_{start_date}_{end_date}"
        if cache_key in self.data_cache:
            print(f"   ✓ Menggunakan data BTC dari cache")
            return self.data_cache[cache_key]
        
        btc_df = self.fetch_ohlcv('BTC/USDT', timeframe, start_date, end_date)
        
        if not btc_df.empty:
            self.data_cache[cache_key] = btc_df
        
        return btc_df

    def fetch_fear_and_greed_history(self, limit: int = 0) -> pd.DataFrame:
        """
        Mengambil data historis Fear & Greed Index

        Args:
            limit: Jumlah hari (0 = semua data)

        Returns:
            DataFrame dengan index tanggal dan kolom 'value', 'classification'
        """
        print(f"\n🧠 Mengambil Data Fear & Greed Index (Source: alternative.me)...")
        url = f"https://api.alternative.me/fng/?limit={limit}&format=json"

        try:
            response = requests.get(url)
            data = response.json()

            if data['metadata']['error']:
                print(f"❌ API Error: {data['metadata']['error']}")
                return pd.DataFrame()

            records = []
            for item in data['data']:
                dt = datetime.fromtimestamp(int(item['timestamp']))
                records.append({
                    'timestamp': dt.strftime('%Y-%m-%d'),
                    'fng_value': int(item['value']),
                    'fng_class': item['value_classification']
                })

            df = pd.DataFrame(records)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)

            print(f"✅ Berhasil mengambil {len(df)} hari data Sentimen.")
            return df

        except Exception as e:
            print(f"❌ Gagal mengambil Fear & Greed: {e}")
            return pd.DataFrame()
    
    def validate_data(self, data_dict: Dict) -> Dict:
        """
        Validasi dan cleaning data
        
        Args:
            data_dict: Dictionary data
            
        Returns:
            Dictionary data yang sudah divalidasi
        """
        validated_data = {}
        
        for symbol, timeframes in data_dict.items():
            validated_timeframes = {}
            
            for tf, df in timeframes.items():
                if not isinstance(df, pd.DataFrame) or df.empty:
                    print(f"⚠️ {symbol} {tf}: Data kosong atau bukan DataFrame, skip...")
                    continue
                
                # 1. Cek missing values
                missing = df.isnull().sum().sum()
                if missing > 0:
                    print(f"⚠️ {symbol} {tf}: {missing} missing values, melakukan fill...")
                    df = df.fillna(method='ffill').fillna(method='bfill')
                
                # 2. Cek duplikat timestamp
                duplicates = df.index.duplicated().sum()
                if duplicates > 0:
                    print(f"⚠️ {symbol} {tf}: {duplicates} duplikat, menghapus...")
                    df = df[~df.index.duplicated(keep='first')]
                
                # 3. Cek gap dalam data
                if tf == '5m':
                    expected_freq = '5min'
                elif tf == '1h':
                    expected_freq = '1H'
                else:
                    expected_freq = None
                
                if expected_freq:
                    # Buat date range lengkap
                    full_range = pd.date_range(
                        start=df.index.min(),
                        end=df.index.max(),
                        freq=expected_freq
                    )
                    
                    missing_timestamps = full_range.difference(df.index)
                    if len(missing_timestamps) > 0:
                        print(f"⚠️ {symbol} {tf}: {len(missing_timestamps)} timestamp hilang")
                        
                        # Interpolasi data yang hilang
                        df = df.reindex(full_range)
                        df = df.interpolate(method='linear')
                        df = df.fillna(method='ffill').fillna(method='bfill')
                
                # 4. Validasi harga (tidak boleh nol atau negatif)
                price_cols = ['open', 'high', 'low', 'close']
                for col in price_cols:
                    if (df[col] <= 0).any():
                        print(f"⚠️ {symbol} {tf}: Harga {col} <= 0 ditemukan, memperbaiki...")
                        # Ganti dengan nilai sebelumnya
                        mask = df[col] <= 0
                        df.loc[mask, col] = np.nan
                        df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
                
                # 5. Validasi high >= low
                invalid_hl = (df['high'] < df['low']).sum()
                if invalid_hl > 0:
                    print(f"⚠️ {symbol} {tf}: {invalid_hl} bar dengan high < low, memperbaiki...")
                    # Swap jika high < low
                    mask = df['high'] < df['low']
                    df.loc[mask, ['high', 'low']] = df.loc[mask, ['low', 'high']].values
                
                validated_timeframes[tf] = df
            
            if validated_timeframes:
                validated_data[symbol] = validated_timeframes
        
        return validated_data
    
    def get_data_summary(self, data_dict: Dict) -> pd.DataFrame:
        """
        Membuat summary statistik dari data
        
        Args:
            data_dict: Dictionary data
            
        Returns:
            DataFrame dengan summary
        """
        summary_data = []
        
        for symbol, timeframes in data_dict.items():
            for tf, df in timeframes.items():
                if not isinstance(df, pd.DataFrame) or df.empty:
                    continue
                    
                summary_data.append({
                    'Symbol': symbol,
                    'Timeframe': tf,
                    'Start Date': df.index.min().strftime('%Y-%m-%d'),
                    'End Date': df.index.max().strftime('%Y-%m-%d'),
                    'Total Bars': len(df),
                    'Avg Daily Bars': len(df) / ((df.index.max() - df.index.min()).days + 1) if len(df) > 0 else 0,
                    'Price Start': df['close'].iloc[0] if len(df) > 0 else 0,
                    'Price End': df['close'].iloc[-1] if len(df) > 0 else 0,
                    'Price Change %': ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100) if len(df) > 0 and df['close'].iloc[0] > 0 else 0,
                    'Avg Volume': df['volume'].mean() if len(df) > 0 else 0,
                    'Missing Values': df.isnull().sum().sum(),
                    'Duplicates': df.index.duplicated().sum()
                })
        
        summary_df = pd.DataFrame(summary_data)
        return summary_df

# Fungsi utama untuk menjalankan pengambilan data
def fetch_and_save_data():
    """
    Fungsi utama untuk mengambil dan menyimpan data
    """
    import config  # Import konfigurasi dari bot
    
    print("="*60)
    print("📊 HISTORICAL DATA FETCHER - PULLBACK SNIPER BOT")
    print("="*60)
    
    # Konfigurasi
    START_DATE = "2024-01-01"
    END_DATE = "2024-04-01"
    TIMEFRAMES = ['5m', '1h']  # Timeframe yang dibutuhkan untuk strategi
    
    # Ambil simbol dari config bot (hanya beberapa untuk testing)
    SYMBOLS = [coin['symbol'] for coin in config.DAFTAR_KOIN]  # Hanya 3 simbol pertama untuk testing
    
    # Tambahkan BTC untuk filter trend
    SYMBOLS.append('BTC/USDT')
    
    print(f"📅 Periode: {START_DATE} hingga {END_DATE}")
    print(f"🎯 Jumlah simbol: {len(SYMBOLS)}")
    print(f"⏱️  Timeframe: {TIMEFRAMES}")
    print(f"💾 Folder data: historical_data/")
    print("\n" + "="*60)
    
    # Inisialisasi fetcher
    fetcher = HistoricalDataFetcher(use_testnet=False)
    
    # Opsi 1: Load data dari cache/CSV jika sudah ada
    print("\n1. Mencoba memuat data dari cache...")
    cached_data = fetcher.load_data_from_csv('historical_data')
    
    if cached_data:
        print(f"\n✅ Data ditemukan di cache untuk {len(cached_data)} simbol")
        
        # Pisahkan data BTC dari data lainnya
        btc_data = cached_data.get('BTC/USDT', None)
        symbol_data = {k: v for k, v in cached_data.items() if k != 'BTC/USDT'}
        
        # Validasi data
        symbol_data = fetcher.validate_data(symbol_data)
        
        # Tampilkan summary
        summary = fetcher.get_data_summary(symbol_data)
        print("\n📈 Data Summary:")
        print(summary.to_string())
        
        if btc_data is not None:
            print(f"\n🎯 Data BTC/USDT: {len(btc_data.get('1h', pd.DataFrame()))} bar")

        # Cek F&G data
        fng_file = os.path.join('historical_data', 'fear_greed.csv')
        if os.path.exists(fng_file):
            print(f"🧠 Data Fear & Greed ditemukan.")
        else:
            print(f"⚠️ Data Fear & Greed TIDAK ditemukan di cache.")

        # Tanya user apakah perlu update data
        # update = input("\n🔄 Update data terbaru? (y/n): ").lower().strip()
        update = 'n' # Force no update for automation, change to input() if interactive

        if update == 'y':
            print("\n2. Memperbarui data...")
            # Ambil data terbaru
            new_data = fetcher.fetch_all_symbols_data(
                SYMBOLS, START_DATE, END_DATE, TIMEFRAMES
            )
            
            # Ambil F&G
            fng_df = fetcher.fetch_fear_and_greed_history()
            if not fng_df.empty:
                fng_df.to_csv(os.path.join('historical_data', 'fear_greed.csv'))

            # Simpan data yang diperbarui
            print("\n3. Menyimpan data ke CSV...")
            fetcher.save_data_to_csv(new_data)
            
            return new_data
        else:
            # Load F&G if exists to return struct
            if os.path.exists(fng_file):
                cached_data['sentiment'] = pd.read_csv(fng_file, index_col='timestamp', parse_dates=True)
            return cached_data
    else:
        # Opsi 2: Fetch data baru dari exchange
        print("\n2. Mengambil data dari Binance...")
        
        # Ambil data untuk semua simbol
        all_data = fetcher.fetch_all_symbols_data(
            SYMBOLS, START_DATE, END_DATE, TIMEFRAMES
        )
        
        # Ambil F&G
        fng_df = fetcher.fetch_fear_and_greed_history()
        if not fng_df.empty:
            fng_df.to_csv(os.path.join('historical_data', 'fear_greed.csv'))
            all_data['sentiment'] = fng_df

        # Validasi data
        # Note: validate_data expects dict of dicts, but sentiment is just a DF.
        # We should exclude it from validation loop or handle it inside.
        # For simplicity, let's keep it separate in logic, but here we just pass symbols.
        symbol_data_only = {k:v for k,v in all_data.items() if k != 'sentiment'}
        validated_sym_data = fetcher.validate_data(symbol_data_only)
        
        # Merge back
        final_data = validated_sym_data
        if 'sentiment' in all_data:
            final_data['sentiment'] = all_data['sentiment']

        # Tampilkan summary
        summary = fetcher.get_data_summary(final_data)
        print("\n📈 Data Summary:")
        print(summary.to_string())
        
        # Simpan ke CSV untuk penggunaan berikutnya
        print("\n3. Menyimpan data ke CSV...")
        fetcher.save_data_to_csv(final_data)
        
        return final_data

if __name__ == "__main__":
    # Jalankan fetcher
    data = fetch_and_save_data()
    
    # Contoh bagaimana menggunakan data di backtest
    if data:
        print(f"\n🎯 Data siap untuk backtest:")
        print(f"   - {len(data)} simbol trading tersimpan")
        print(f"\n📁 Data dapat diakses dari backtest.py dengan:")
        print("""
from data_fetcher import HistoricalDataFetcher

fetcher = HistoricalDataFetcher()
all_data = fetcher.load_data_from_csv('historical_data')
        """)
    else:
        print("\n⚠️ Data tidak lengkap, periksa koneksi internet atau coba lagi.")