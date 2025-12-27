# file: backtest.py
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import json
import os
from typing import Dict, List, Tuple, Optional
import config

warnings.filterwarnings('ignore')

class BacktestEngine:
    def __init__(self, initial_capital: float = 10000, commission: float = 0.0004):
        """
        Inisialisasi engine backtest
        
        Args:
            initial_capital: Modal awal dalam USDT
            commission: Komisi trading (0.04% untuk Binance Futures)
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.trades = []
        self.equity_curve = []
        self.current_positions = {}
        
        # Parameter dari config
        self.config = config
        
    def calculate_indicators(self, df: pd.DataFrame, 
                           timeframe: str = '5m') -> pd.DataFrame:
        """
        Menghitung semua indikator yang digunakan dalam strategi
        
        Args:
            df: DataFrame OHLCV
            timeframe: Timeframe data ('5m' atau '1h')
            
        Returns:
            DataFrame dengan kolom indikator tambahan
        """
        df = df.copy()
        
        # EMA untuk trend
        df['EMA_FAST'] = ta.ema(df['close'], length=config.EMA_FAST)
        df['EMA_SLOW'] = ta.ema(df['close'], length=config.EMA_SLOW)
        
        if timeframe == '1h':
            df['EMA_MAJOR'] = ta.ema(df['close'], length=config.EMA_TREND_MAJOR)
        
        # ATR untuk stop loss dan take profit
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=config.ATR_PERIOD)
        
        # ADX untuk kekuatan trend
        adx = ta.adx(df['high'], df['low'], df['close'], length=config.ADX_PERIOD)
        df['ADX'] = adx[f'ADX_{config.ADX_PERIOD}']
        
        # RSI
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # Bollinger Bands
        bb = ta.bbands(df['close'], length=config.BB_LENGTH, std=config.BB_STD)
        df['BBL'] = bb[f'BBL_{config.BB_LENGTH}_{config.BB_STD}']
        df['BBM'] = bb[f'BBM_{config.BB_LENGTH}_{config.BB_STD}']
        df['BBU'] = bb[f'BBU_{config.BB_LENGTH}_{config.BB_STD}']
        
        # Stochastic RSI
        stoch_rsi = ta.stochrsi(df['close'], 
                               length=config.STOCHRSI_LEN,
                               rsi_length=config.STOCHRSI_LEN,
                               k=config.STOCHRSI_K,
                               d=config.STOCHRSI_D)
        df['STOCH_K'] = stoch_rsi.iloc[:, 0]
        df['STOCH_D'] = stoch_rsi.iloc[:, 1]
        
        # Volume MA
        df['VOL_MA'] = df['volume'].rolling(window=config.VOL_MA_PERIOD).mean()
        df['VOL_RATIO'] = df['volume'] / df['VOL_MA']
        
        # Menandai volume tinggi
        df['HIGH_VOLUME'] = df['VOL_RATIO'] > 1.2
        
        return df
    
    def calculate_btc_trend(self, btc_data: pd.DataFrame) -> pd.Series:
        """
        Menghitung trend BTC untuk filter global
        
        Args:
            btc_data: Data OHLCV BTC
            
        Returns:
            Series dengan trend BTC ('BULLISH', 'BEARISH', 'NEUTRAL')
        """
        btc_data = btc_data.copy()
        btc_data['EMA_BTC'] = ta.ema(btc_data['close'], length=config.BTC_EMA_PERIOD)
        
        trend = pd.Series('NEUTRAL', index=btc_data.index)
        trend[btc_data['close'] > btc_data['EMA_BTC']] = 'BULLISH'
        trend[btc_data['close'] < btc_data['EMA_BTC']] = 'BEARISH'
        
        return trend
    
    def check_entry_signal(self, df_5m: pd.DataFrame, 
                          df_1h: pd.DataFrame,
                          btc_trend: str,
                          symbol: str,
                          current_idx: int) -> Dict:
        """
        Mengecek sinyal entry berdasarkan strategi
        
        Returns:
            Dictionary dengan informasi sinyal atau None
        """
        # Pastikan kita tidak di akhir data
        if current_idx < 2 or current_idx >= len(df_5m) - 1:
            return None
        
        # Data untuk analisis
        current = df_5m.iloc[current_idx]
        prev = df_5m.iloc[current_idx - 1]
        
        # Filter cooldown (dalam bar)
        if hasattr(self, 'last_entry_bar'):
            if current_idx - self.last_entry_bar < 60:  # 60 bar 5m = 5 jam
                return None
        
        # Filter trend BTC
        allowed_signal = "BOTH"
        if symbol != config.BTC_SYMBOL:
            if btc_trend == "BULLISH":
                allowed_signal = "LONG_ONLY"
            elif btc_trend == "BEARISH":
                allowed_signal = "SHORT_ONLY"
        
        # Filter trend major (1h)
        current_1h = df_1h.iloc[-1]
        is_coin_uptrend_h1 = current_1h['close'] > current_1h.get('EMA_MAJOR', current_1h['close'])
        
        # Variabel indikator
        adx_val = current['ADX']
        current_price = current['close']
        current_rsi = current['RSI']
        ema_fast = current['EMA_FAST']
        is_volume_valid = current['HIGH_VOLUME']
        
        signal = None
        strategy_type = "NONE"
        
        # 1. TREND TRAP STRATEGY
        if config.USE_TREND_TRAP_STRATEGY and adx_val > config.TREND_TRAP_ADX_MIN:
            
            # LONG: Trend H1 naik + M5 pullback
            if allowed_signal in ["LONG_ONLY", "BOTH"] and is_coin_uptrend_h1:
                is_pullback_zone = (current_price < ema_fast) and (current_price > current['BBL'])
                rsi_pass = (current_rsi >= config.TREND_TRAP_RSI_LONG_MIN) and \
                          (current_rsi <= config.TREND_TRAP_RSI_LONG_MAX)
                
                if is_pullback_zone and rsi_pass:
                    signal = "LONG"
                    strategy_type = f"TREND_PULLBACK (RSI {current_rsi:.1f})"
            
            # SHORT: Trend H1 turun + M5 pullback naik
            elif allowed_signal in ["SHORT_ONLY", "BOTH"] and not is_coin_uptrend_h1:
                is_pullback_zone = (current_price > ema_fast) and (current_price < current['BBU'])
                rsi_pass = (current_rsi >= config.TREND_TRAP_RSI_SHORT_MIN) and \
                          (current_rsi <= config.TREND_TRAP_RSI_SHORT_MAX)
                
                if is_pullback_zone and rsi_pass:
                    signal = "SHORT"
                    strategy_type = f"TREND_PULLBACK (RSI {current_rsi:.1f})"
        
        # 2. SIDEWAYS STRATEGY (BB BOUNCE)
        if not signal and config.USE_SIDEWAYS_SCALP and adx_val < config.SIDEWAYS_ADX_MAX:
            # Buy di BB bawah
            if current_price <= current['BBL'] and current['STOCH_K'] < 20:
                if allowed_signal in ["LONG_ONLY", "BOTH"]:
                    signal = "LONG"
                    strategy_type = "BB_BOUNCE_BOTTOM"
            
            # Sell di BB atas
            elif current_price >= current['BBU'] and current['STOCH_K'] > 80:
                if allowed_signal in ["SHORT_ONLY", "BOTH"]:
                    signal = "SHORT"
                    strategy_type = "BB_BOUNCE_TOP"
        
        if signal:
            # Hitung parameter trade
            atr = current['ATR']
            entry_price = current_price
            
            if config.USE_LIQUIDITY_HUNT:
                # Mode Liquidity Hunt: entry di level SL retail
                retail_sl_dist = atr * config.ATR_MULTIPLIER_SL
                if signal == "LONG":
                    entry_price = current_price - retail_sl_dist
                else:
                    entry_price = current_price + retail_sl_dist
            
            # Hitung SL dan TP
            if signal == "LONG":
                sl_price = entry_price - (atr * config.ATR_MULTIPLIER_SL)
                tp_price = entry_price + (atr * config.ATR_MULTIPLIER_TP1)
                side_api = 'buy'
            else:
                sl_price = entry_price + (atr * config.ATR_MULTIPLIER_SL)
                tp_price = entry_price - (atr * config.ATR_MULTIPLIER_TP1)
                side_api = 'sell'
            
            return {
                'signal': signal,
                'strategy': strategy_type,
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'side': side_api,
                'timestamp': df_5m.index[current_idx],
                'adx': adx_val,
                'rsi': current_rsi,
                'volume_valid': is_volume_valid,
                'atr': atr
            }
        
        return None
    
    def calculate_position_size(self, entry_price: float, 
                              sl_price: float, 
                              risk_per_trade: float = 0.02) -> Tuple[float, float]:
        """
        Menghitung ukuran posisi berdasarkan risiko
        
        Args:
            entry_price: Harga entry
            sl_price: Harga stop loss
            risk_per_trade: Risiko per trade (2% default)
            
        Returns:
            (jumlah_koin, nilai_usdt)
        """
        # Risiko dalam USDT
        risk_usdt = self.capital * risk_per_trade
        
        # Jarak SL
        if entry_price > sl_price:  # LONG
            sl_distance = entry_price - sl_price
        else:  # SHORT
            sl_distance = sl_price - entry_price
        
        # Jumlah koin yang bisa dibeli
        if sl_distance > 0:
            coin_amount = risk_usdt / sl_distance
        else:
            coin_amount = 0
        
        # Nilai posisi dalam USDT
        position_value = coin_amount * entry_price
        
        # Batasi dengan maksimal 10% dari modal
        max_position = self.capital * 0.1
        if position_value > max_position:
            position_value = max_position
            coin_amount = max_position / entry_price
        
        return coin_amount, position_value
    
    def run_backtest(self, 
                    symbol_data: Dict[str, pd.DataFrame],
                    btc_data: pd.DataFrame,
                    start_date: str,
                    end_date: str):
        """
        Menjalankan backtest untuk semua simbol
        
        Args:
            symbol_data: Dictionary dengan data untuk setiap simbol
            btc_data: Data BTC untuk filter trend
            start_date: Tanggal mulai backtest
            end_date: Tanggal akhir backtest
        """
        print("🚀 Memulai Backtest...")
        print(f"📅 Periode: {start_date} hingga {end_date}")
        print(f"💰 Modal Awal: ${self.initial_capital:,.2f}")
        print("=" * 50)
        
        # Inisialisasi
        self.trades = []
        self.equity_curve = []
        self.capital = self.initial_capital
        
        # Hitung trend BTC
        btc_trend_series = self.calculate_btc_trend(btc_data)
        
        # Loop untuk setiap simbol
        for symbol_config in config.DAFTAR_KOIN:
            symbol = symbol_config['symbol']
            leverage = symbol_config.get('leverage', config.DEFAULT_LEVERAGE)
            amount_usdt = symbol_config.get('amount', config.DEFAULT_AMOUNT_USDT)
            
            print(f"\n🔍 Analisis: {symbol} (Leverage: {leverage}x)")
            
            if symbol not in symbol_data:
                print(f"⚠️ Data untuk {symbol} tidak ditemukan, skip...")
                continue
            
            # Ambil data untuk simbol ini
            df_5m = symbol_data[symbol].get('5m')
            df_1h = symbol_data[symbol].get('1h')
            
            if df_5m is None or df_1h is None:
                print(f"⚠️ Data timeframe tidak lengkap untuk {symbol}, skip...")
                continue
            
            # Filter berdasarkan tanggal
            df_5m = df_5m[(df_5m.index >= start_date) & (df_5m.index <= end_date)]
            df_1h = df_1h[(df_1h.index >= start_date) & (df_1h.index <= end_date)]
            
            if len(df_5m) < 100:
                print(f"⚠️ Data terlalu sedikit untuk {symbol}, skip...")
                continue
            
            # Hitung indikator
            df_5m = self.calculate_indicators(df_5m, '5m')
            df_1h = self.calculate_indicators(df_1h, '1h')
            
            # Align 1h data dengan 5m data
            df_1h_aligned = df_1h.reindex(df_5m.index, method='ffill')
            
            # Simpan sebagai atribut untuk akses di check_entry_signal
            self.last_entry_bar = -999
            
            # Loop melalui setiap bar 5m
            for i in range(100, len(df_5m) - 1):
                current_time = df_5m.index[i]
                
                # Dapatkan trend BTC saat ini
                btc_trend = "NEUTRAL"
                if current_time in btc_trend_series.index:
                    btc_trend = btc_trend_series.loc[current_time]
                
                # Cek sinyal entry
                signal_info = self.check_entry_signal(
                    df_5m, df_1h_aligned, btc_trend, symbol, i
                )
                
                if signal_info:
                    # Hitung ukuran posisi
                    coin_amount, position_value = self.calculate_position_size(
                        signal_info['entry_price'],
                        signal_info['sl_price']
                    )
                    
                    # Skip jika posisi terlalu kecil
                    if position_value < config.MIN_ORDER_USDT:
                        continue
                    
                    # Simulasikan trade
                    entry_time = df_5m.index[i]
                    entry_price = signal_info['entry_price']
                    sl_price = signal_info['sl_price']
                    tp_price = signal_info['tp_price']
                    
                    # Cari exit point (SL atau TP)
                    exit_found = False
                    exit_type = None
                    exit_price = None
                    exit_time = None
                    
                    for j in range(i + 1, min(i + 500, len(df_5m))):  # Max 500 bar forward
                        future_bar = df_5m.iloc[j]
                        
                        if signal_info['signal'] == "LONG":
                            # Cek TP
                            if future_bar['high'] >= tp_price:
                                exit_type = "TP"
                                exit_price = tp_price
                                exit_time = df_5m.index[j]
                                exit_found = True
                                break
                            # Cek SL
                            elif future_bar['low'] <= sl_price:
                                exit_type = "SL"
                                exit_price = sl_price
                                exit_time = df_5m.index[j]
                                exit_found = True
                                break
                        
                        else:  # SHORT
                            # Cek TP
                            if future_bar['low'] <= tp_price:
                                exit_type = "TP"
                                exit_price = tp_price
                                exit_time = df_5m.index[j]
                                exit_found = True
                                break
                            # Cek SL
                            elif future_bar['high'] >= sl_price:
                                exit_type = "SL"
                                exit_price = sl_price
                                exit_time = df_5m.index[j]
                                exit_found = True
                                break
                    
                    # Jika tidak exit dalam 500 bar, exit di harga terakhir
                    if not exit_found:
                        exit_type = "TIME_EXIT"
                        exit_price = df_5m.iloc[min(i + 500, len(df_5m) - 1)]['close']
                        exit_time = df_5m.index[min(i + 500, len(df_5m) - 1)]
                    
                    # Hitung P&L
                    if signal_info['signal'] == "LONG":
                        pnl_percent = ((exit_price - entry_price) / entry_price) * 100 * leverage
                    else:
                        pnl_percent = ((entry_price - exit_price) / entry_price) * 100 * leverage
                    
                    pnl_usdt = (position_value * pnl_percent) / 100
                    
                    # Kurangi komisi
                    commission_total = position_value * self.commission * 2  # Entry dan exit
                    pnl_usdt -= commission_total
                    
                    # Update modal
                    self.capital += pnl_usdt
                    
                    # Catat trade
                    trade = {
                        'symbol': symbol,
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'side': signal_info['signal'],
                        'strategy': signal_info['strategy'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'exit_type': exit_type,
                        'position_value': position_value,
                        'pnl_usdt': pnl_usdt,
                        'pnl_percent': pnl_percent,
                        'leverage': leverage,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'adx': signal_info['adx'],
                        'rsi': signal_info['rsi'],
                        'atr': signal_info['atr'],
                        'volume_valid': signal_info['volume_valid']
                    }
                    
                    self.trades.append(trade)
                    self.last_entry_bar = i
                    
                    # Update equity curve
                    self.equity_curve.append({
                        'timestamp': exit_time,
                        'equity': self.capital,
                        'pnl_cumulative': self.capital - self.initial_capital
                    })
                    
                    # Skip beberapa bar setelah entry (cooldown)
                    i += 10
        
        print("\n✅ Backtest selesai!")
    
    def generate_report(self):
        """Generate laporan hasil backtest"""
        if not self.trades:
            print("❌ Tidak ada trade yang dieksekusi dalam periode ini")
            return
        
        # Konversi ke DataFrame
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Hitung metrik
        total_trades = len(trades_df)
        winning_trades = trades_df[trades_df['pnl_usdt'] > 0]
        losing_trades = trades_df[trades_df['pnl_usdt'] <= 0]
        
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl_usdt'].sum()
        avg_win = winning_trades['pnl_usdt'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl_usdt'].mean() if len(losing_trades) > 0 else 0
        
        profit_factor = abs(winning_trades['pnl_usdt'].sum() / losing_trades['pnl_usdt'].sum()) if len(losing_trades) > 0 and losing_trades['pnl_usdt'].sum() != 0 else 0
        
        max_win = trades_df['pnl_usdt'].max()
        max_loss = trades_df['pnl_usdt'].min()
        
        # Sharpe Ratio (sederhana)
        if len(equity_df) > 1:
            equity_df['returns'] = equity_df['equity'].pct_change()
            sharpe_ratio = equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(365*24*12) if equity_df['returns'].std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max Drawdown
        equity_df['equity_peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['equity_peak']) / equity_df['equity_peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # Tampilkan laporan
        print("\n" + "="*60)
        print("📊 LAPORAN BACKTEST STRATEGI PULLBACK SNIPER")
        print("="*60)
        
        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"   Total Modal Awal: ${self.initial_capital:,.2f}")
        print(f"   Total Modal Akhir: ${self.capital:,.2f}")
        print(f"   Total Profit/Loss: ${total_pnl:,.2f} ({((self.capital/self.initial_capital)-1)*100:.2f}%)")
        print(f"   Total Trade: {total_trades}")
        
        print(f"\n🎯 WIN RATE & RISK-REWARD:")
        print(f"   Win Rate: {win_rate:.2f}%")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Average Win: ${avg_win:.2f}")
        print(f"   Average Loss: ${avg_loss:.2f}")
        print(f"   Risk/Reward (Avg): {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "   Risk/Reward: N/A")
        
        print(f"\n⚡ MAXIMUM & DRAWDOWN:")
        print(f"   Maximum Win: ${max_win:.2f}")
        print(f"   Maximum Loss: ${max_loss:.2f}")
        print(f"   Maximum Drawdown: {max_drawdown:.2f}%")
        print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")
        
        print(f"\n📊 DISTRIBUSI EXIT TYPE:")
        exit_counts = trades_df['exit_type'].value_counts()
        for exit_type, count in exit_counts.items():
            percentage = count / total_trades * 100
            print(f"   {exit_type}: {count} trades ({percentage:.1f}%)")
        
        print(f"\n🏆 BEST PERFORMING SYMBOLS:")
        symbol_perf = trades_df.groupby('symbol')['pnl_usdt'].sum().sort_values(ascending=False)
        for symbol, pnl in symbol_perf.head(5).items():
            print(f"   {symbol}: ${pnl:.2f}")
        
        print(f"\n📈 BEST STRATEGIES:")
        strategy_perf = trades_df.groupby('strategy')['pnl_usdt'].sum().sort_values(ascending=False)
        for strategy, pnl in strategy_perf.head(5).items():
            print(f"   {strategy}: ${pnl:.2f}")
        
        # Visualisasi
        self.plot_results(trades_df, equity_df)
        
        # Simpan hasil ke CSV
        trades_df.to_csv('backtest_results.csv', index=False)
        print(f"\n💾 Hasil backtest disimpan ke 'backtest_results.csv'")
    
    def plot_results(self, trades_df: pd.DataFrame, equity_df: pd.DataFrame):
        """Plot hasil backtest"""
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        
        # 1. Equity Curve
        ax1 = axes[0, 0]
        ax1.plot(equity_df['timestamp'], equity_df['equity'], linewidth=2)
        ax1.set_title('Equity Curve', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Waktu')
        ax1.set_ylabel('Equity (USDT)')
        ax1.grid(True, alpha=0.3)
        ax1.fill_between(equity_df['timestamp'], equity_df['equity'], self.initial_capital, 
                        where=equity_df['equity'] >= self.initial_capital, 
                        facecolor='green', alpha=0.3)
        ax1.fill_between(equity_df['timestamp'], equity_df['equity'], self.initial_capital, 
                        where=equity_df['equity'] < self.initial_capital, 
                        facecolor='red', alpha=0.3)
        
        # 2. Drawdown
        ax2 = axes[0, 1]
        ax2.fill_between(equity_df['timestamp'], equity_df['drawdown'], 0, 
                        where=equity_df['drawdown'] <= 0, 
                        facecolor='red', alpha=0.5)
        ax2.set_title('Drawdown', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Waktu')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        # 3. Distribusi P&L
        ax3 = axes[1, 0]
        colors = ['green' if x > 0 else 'red' for x in trades_df['pnl_usdt']]
        ax3.hist(trades_df['pnl_usdt'], bins=30, color=colors, edgecolor='black', alpha=0.7)
        ax3.axvline(x=0, color='black', linestyle='--', linewidth=1)
        ax3.set_title('Distribusi Profit/Loss', fontsize=12, fontweight='bold')
        ax3.set_xlabel('P&L (USDT)')
        ax3.set_ylabel('Frekuensi')
        ax3.grid(True, alpha=0.3)
        
        # 4. Win Rate per Symbol
        ax4 = axes[1, 1]
        symbol_stats = trades_df.groupby('symbol').apply(
            lambda x: pd.Series({
                'win_rate': (x['pnl_usdt'] > 0).sum() / len(x) * 100,
                'total_trades': len(x)
            })
        ).sort_values('win_rate', ascending=False).head(10)
        
        bars = ax4.bar(symbol_stats.index, symbol_stats['win_rate'], 
                      color=['green' if x > 50 else 'orange' for x in symbol_stats['win_rate']])
        ax4.set_title('Win Rate per Symbol (Top 10)', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Symbol')
        ax4.set_ylabel('Win Rate (%)')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(True, alpha=0.3)
        
        # Tambah angka di atas bar
        for bar, trade_count in zip(bars, symbol_stats['total_trades']):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}% ({trade_count})', ha='center', va='bottom', fontsize=8)
        
        # 5. Monthly Returns
        ax5 = axes[2, 0]
        trades_df['month'] = trades_df['exit_time'].dt.to_period('M')
        monthly_pnl = trades_df.groupby('month')['pnl_usdt'].sum()
        
        colors_month = ['green' if x > 0 else 'red' for x in monthly_pnl]
        ax5.bar(monthly_pnl.index.astype(str), monthly_pnl.values, color=colors_month)
        ax5.set_title('Profit/Loss Bulanan', fontsize=12, fontweight='bold')
        ax5.set_xlabel('Bulan')
        ax5.set_ylabel('P&L (USDT)')
        ax5.tick_params(axis='x', rotation=45)
        ax5.grid(True, alpha=0.3)
        
        # 6. Exit Type Distribution
        ax6 = axes[2, 1]
        exit_counts = trades_df['exit_type'].value_counts()
        ax6.pie(exit_counts.values, labels=exit_counts.index, autopct='%1.1f%%',
               colors=['green', 'red', 'gray'])
        ax6.set_title('Distribusi Tipe Exit', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig('backtest_results.png', dpi=150, bbox_inches='tight')
        plt.show()

# Fungsi untuk load data (contoh)
def load_sample_data(symbols: List[str], start_date: str, end_date: str) -> Dict:
    """
    Fungsi untuk load data historis.
    Dalam implementasi nyata, Anda bisa menggunakan:
    1. ccxt untuk fetch dari exchange
    2. CSV file yang sudah didownload
    3. Database tick data
    
    Returns:
        Dictionary dengan data untuk setiap simbol
    """
    print("⚠️  Fungsi load_sample_data adalah placeholder.")
    print("Untuk backtest nyata, Anda perlu implementasi:")
    print("1. Download data dari Binance menggunakan ccxt")
    print("2. Load dari file CSV yang sudah ada")
    print("3. Gunakan library seperti yfinance untuk crypto")
    
    # Contoh struktur return (harus diganti dengan data nyata)
    sample_data = {}
    
    for symbol in symbols:
        # Buat data dummy untuk contoh
        dates = pd.date_range(start=start_date, end=end_date, freq='5min')
        np.random.seed(42)
        
        # Generate price data dengan random walk
        prices = []
        price = 100  # harga awal
        for _ in range(len(dates)):
            change = np.random.normal(0, 0.001)  # 0.1% perubahan rata-rata
            price *= (1 + change)
            prices.append(price)
        
        df_5m = pd.DataFrame({
            'open': [p * 0.999 for p in prices],
            'high': [p * 1.002 for p in prices],
            'low': [p * 0.998 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates)
        
        # Resample untuk 1h data
        df_1h = df_5m.resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        sample_data[symbol] = {
            '5m': df_5m,
            '1h': df_1h
        }
    
    # Generate BTC data
    dates = pd.date_range(start=start_date, end=end_date, freq='1h')
    btc_prices = []
    price = 30000
    for _ in range(len(dates)):
        change = np.random.normal(0, 0.002)
        price *= (1 + change)
        btc_prices.append(price)
    
    btc_data = pd.DataFrame({
        'open': [p * 0.999 for p in btc_prices],
        'high': [p * 1.003 for p in btc_prices],
        'low': [p * 0.997 for p in btc_prices],
        'close': btc_prices,
        'volume': np.random.randint(10000, 50000, len(dates))
    }, index=dates)
    
    return sample_data, btc_data

# Main execution
if __name__ == "__main__":
    print("🔧 BACKTEST ENGINE - PULLBACK SNIPER STRATEGY")
    print("="*60)
    
    # Konfigurasi backtest
    START_DATE = "2024-01-01"
    END_DATE = "2024-03-01"
    INITIAL_CAPITAL = 10000
    
    # Inisialisasi backtest engine
    backtester = BacktestEngine(
        initial_capital=INITIAL_CAPITAL,
        commission=0.0004  # 0.04% commission
    )
    
    # Dapatkan simbol dari config
    symbols = [coin['symbol'] for coin in config.DAFTAR_KOIN]
    
    # Load data (ini adalah placeholder - perlu implementasi nyata)
    print("\n📥 Memuat data historis...")
    symbol_data, btc_data = load_sample_data(symbols, START_DATE, END_DATE)
    
    # Jalankan backtest
    backtester.run_backtest(
        symbol_data=symbol_data,
        btc_data=btc_data,
        start_date=START_DATE,
        end_date=END_DATE
    )
    
    # Generate laporan
    backtester.generate_report()