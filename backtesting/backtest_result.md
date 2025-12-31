# 🚀 Laporan Backtest: Pullback Sniper Strategy

**Tanggal Generate:** 31 Desember 2025
**File Konfigurasi:** `backtest_results/config_20251231_105256.json`

---

## 1. Ringkasan Eksekutif

| Metrik | Nilai |
| :--- | :--- |
| **Total Profit/Loss** | **+1,060,001,321.11%** 🚀 |
| **Modal Akhir** | **$1,060,001,421.11** |
| **Win Rate** | **64.76%** |
| **Profit Factor** | **3.69** |
| **Total Trades** | 3,788 |
| **Max Drawdown** | -12.51% |

---

## 2. Konfigurasi Backtest

* **Periode:** 01 Oktober 2025 - 30 Desember 2025
* **Modal Awal:** $100.00
* **Jumlah Simbol:** 12 Pair (USDT)
* **Leverage:**
    * 20x: ETH
    * 15x: SOL, BNB
    * 10x: XRP, ADA, DOGE, TRX, LTC, AVAX, LINK, ZEC, BTC

---

## 3. Detail Performa (Performance Metrics)

### 💰 Finansial
* **Modal Awal:** `$100.00`
* **Modal Akhir:** `$1,060,001,421.11`
* **Net Profit:** `$1,060,001,321.11`
* **Rata-rata Win:** `$592,597.95`
* **Rata-rata Loss:** `$-294,862.50`

### 🎯 Statistik Trading
* **Win Rate:** `64.76%`
* **Profit Factor:** `3.69`
* **Risk/Reward (Avg):** `2.01`
* **Sharpe Ratio:** `153.14`

### ⚡ Risiko
* **Maximum Win (Single Trade):** `$20,195,211.12`
* **Maximum Loss (Single Trade):** `$-11,614,712.32`
* **Maximum Drawdown:** `-12.51%`

---

## 4. Distribusi Exit
Bagaimana trade ditutup oleh sistem:

* **Take Profit (TP):** 2,452 trades (64.7%)
* **Stop Loss (SL):** 1,335 trades (35.2%)
* **Time Exit:** 1 trades (0.0%)

---

## 5. Performa Aset (Top 5 Symbols)
Simbol dengan kontribusi profit terbesar:

1.  🥇 **ZEC/USDT:** `$1,025,021,659.24` (Dominasi Utama)
2.  🥈 **LINK/USDT:** `$24,954,783.17`
3.  🥉 **AVAX/USDT:** `$6,715,901.82`
4.  **LTC/USDT:** `$2,354,715.38`
5.  **DOGE/USDT:** `$467,977.00`

---

## 6. Performa Strategi
Logic entry mana yang menghasilkan profit terbaik:

| Nama Strategi | Total Profit ($) |
| :--- | :--- |
| **BB_BOUNCE_TOP** | $175,822,600.03 |
| **BB_BOUNCE_BOTTOM** | $175,496,070.35 |
| **TREND_PULLBACK (RSI 52.1)** | $36,652,168.10 |
| **TREND_PULLBACK (RSI 50.6)** | $35,835,326.13 |
| **TREND_PULLBACK (RSI 51.1)** | $34,047,164.81 |

---

> **📝 Catatan Analisis:**
> Hasil backtest menunjukkan pertumbuhan yang **sangat ekstrem** ($100 menjadi $1 Miliar dalam 3 bulan). Kemungkinan besar disebabkan oleh pengaturan *compounding* (bunga berbunga) yang agresif tanpa batasan *max position size*. Dalam kondisi *real market*, likuiditas mungkin tidak akan menampung ukuran posisi sebesar ini pada ZEC/USDT.