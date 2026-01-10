# 🤖 Easy Peasy Trading Bot: AI-Powered Hybrid Sniper

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Binance](https://img.shields.io/badge/Binance-Futures-yellow?style=for-the-badge&logo=binance)
![AI](https://img.shields.io/badge/AI-DeepSeek%2FOpenAI-blueviolet?style=for-the-badge)
![Strategy](https://img.shields.io/badge/Strategy-Hybrid%20Sniper-red?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)

## 📖 Easy Peasy Trading Bot (AI-Integrated Edition)

**Easy Peasy Trading Bot** adalah sistem trading algoritmik otomatis untuk pasar Binance Futures. Dibangun menggunakan Python, bot ini menerapkan pendekatan Hybrid Strategy yang adaptif dan kini diperkuat oleh **Artificial Intelligence**.

Versi terbaru ini tidak hanya mengandalkan indikator teknikal, tetapi juga dilengkapi dengan **"AI Brain"**, **"Sentiment Analysis"**, dan **"On-Chain Detector"**. Bot mampu membaca berita global, mendeteksi pergerakan paus (Whale), serta menganalisis kondisi psikologis pasar (Fear & Greed) sebelum mengambil keputusan trading.

---

## 🚀 Fitur Unggulan

### 1. 🧠 AI-Powered Decision Brain (NEW!)
Bot terintegrasi dengan LLM (via OpenRouter/DeepSeek/OpenAI) untuk memvalidasi sinyal.
*   **Fundamental & Technical Fusion:** AI menganalisis data teknikal (RSI, ADX, EMA) yang digabungkan dengan sentimen pasar untuk memberikan keputusan: `BUY`, `SELL`, atau `WAIT`.
*   **Confidence Score:** Trade hanya dieksekusi jika AI memberikan skor keyakinan (confidence) yang tinggi.

### 2. 📰 Global Sentiment & News Analysis (NEW!)
Jangan trading buta melawan arus berita.
*   **Fear & Greed Index:** Mengambil data real-time dari CoinMarketCap untuk mengetahui psikologi pasar.
*   **News Aggregator:** Bot membaca headline berita kripto terbaru (RSS Feed) untuk mendeteksi sentimen positif/negatif secara global.

### 3. 🐋 Whale & On-Chain Detector (NEW!)
Mendeteksi jejak uang besar (Smart Money).
*   **Whale Alert:** Memantau transaksi besar di pasar secara real-time via WebSocket.
*   **Stablecoin Inflow:** (Integrasi DefiLlama) Memantau arus masuk uang (USDT/USDC) ke exchange sebagai tanda potensi pump pasar.

### 4. ⚡ Hybrid Logic Engine
Menggunakan ADX (Average Directional Index) sebagai otak teknikal utama:
*   **Trend Mode (ADX > 25):** Mengaktifkan strategi Trend Trap Pullback. Bot menunggu harga koreksi cantik ke area EMA sebelum ikut tren.
*   **Sideways Mode (ADX < 20):** Mengaktifkan strategi BB Bounce Scalp. Bot melakukan jual-beli cepat (ping-pong) di area batas Bollinger Bands saat pasar tenang.

### 5. 👑 Smart King BTC & Auto-Decoupling
Bot memiliki hierarki korelasi yang cerdas:
*   **Strict Mode:** Jika korelasi Altcoin terhadap BTC tinggi (> 0.5), bot patuh pada tren BTC. Jika BTC Bearish, dilarang Long.
*   **Decoupled Mode:** Jika koin terdeteksi bergerak mandiri (Korelasi < 0.5), fitur Auto-Decouple aktif. Bot diizinkan mengambil sinyal berlawanan dengan BTC.

### 6. ⚖️ Sector Exposure Limit
Manajemen risiko tingkat lanjut berbasis kategori koin.
*   Anda bisa mengelompokkan koin (contoh: L1, MEME, AI).
*   **Max Position per Category:** Mencegah penumpukan risiko pada satu sektor saja (misal: tidak akan *all-in* di koin Meme secara bersamaan).

### 7. 🔫 Sniper / Liquidity Hunt
Fitur "Anti-Retail" andalan. Bot menghitung jarak ATR untuk memprediksi letak Stop Loss retail trader, lalu memasang Limit Order di area likuiditas tersebut untuk mendapatkan harga diskon terbaik ("Sniper Entry").

### 8. 🛡️ Guardian Safety Monitor
Sistem keamanan berbasis Event-Driven Asyncio:
*   Mendeteksi "Ghost Orders".
*   Memastikan setiap posisi memiliki Hard Stop Loss (SL) dan Take Profit (TP).
*   Pembersihan otomatis order yang kadaluarsa.

### 9. 📱 Advanced Telegram Integration
Laporan lengkap real-time langsung ke saku Anda:
*   **AI Reasoning:** Menampilkan alasan kenapa AI mengambil keputusan tersebut.
*   **Sentiment Data:** Laporan Fear & Greed Index dan berita terhangat.
*   **PnL Report:** Laporan keuntungan otomatis.

---

## 📊 Performa Backtest
Berdasarkan pengujian data historis (1 - 30 Des 2025):

| Metric | Value |
| :--- | :--- |
| **Modal Awal** | $100.00 |
| **Net Profit** | **+$4,976.46** 🚀 |
| **Total Trade** | 1,206 Trades |
| **Win Rate** | **65.09%** |
| **Profit Factor** | 3.85 |
| **Top Coin** | ZEC/USDT (Champion 🏆) |

> *Disclaimer: Simulasi Backtesting Hanya Menggunakan Data Tehnikal dan Tanpa Menggunakan AI dll.*

---

## 🛠️ Cara Install

Ikuti langkah ini satu per satu.

### Persiapan
Pastikan komputer/laptop Anda sudah terinstall:
1.  **Python** (Versi 3.10 ke atas).
2.  **Git**.

### Langkah 1: Clone Repository
```bash
gh repo clone KaleksananBarqi/Bot-Trading-Easy-Peasy-Binance
cd Bot-Trading-Easy-Peasy-Binance
```

### Langkah 2: Buat Virtual Environment
**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Langkah 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Langkah 4: Konfigurasi API Key (.env)
Buat file `.env` dan isi data berikut (Dapatkan API Key dari provider masing-masing):

```ini
# --- BINANCE (Exchange) ---
BINANCE_API_KEY=masukan_api_key_asli_disini
BINANCE_SECRET_KEY=masukan_secret_key_asli_disini
# Jika pakai Testnet
BINANCE_TESTNET_KEY=key_testnet
BINANCE_TESTNET_SECRET=secret_testnet

# --- TELEGRAM (Notifikasi) ---
TELEGRAM_TOKEN=123456:ABC-Def...
TELEGRAM_CHAT_ID=123456789

# --- AI & SENTIMENT (New Features) ---
# Dapatkan di: https://openrouter.ai/keys
AI_API_KEY=sk-or-v1-xxxxxxxx...
AI_MODEL_NAME=deepseek/deepseek-r1:free

# Dapatkan di: https://coinmarketcap.com/api/
CMC_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx
```

### Langkah 5: Sesuaikan Config
Buka file `config.py`. Atur parameter trading, daftar koin, dan manajemen risiko sesuai selera.

### Langkah 6: Jalankan Bot 🚀
```bash
python main.py
```
Jika berhasil, akan muncul pesan:
> `🧠 AI Brain Initialized ✅ WebSocket Connected! System Online.`

---

## ⚠️ Disclaimer
> **Resiko Tinggi:** Trading Futures memiliki resiko likuidasi yang signfikan.
>
> **DYOR (Do Your Own Research):** Penulis tidak bertanggung jawab atas kerugian finansial yang mungkin terjadi.
>
> **AI Hallucination:** Keputusan AI tidak 100% akurat. Selalu gunakan Stop Loss dan Money Management yang bijak.

## 👨‍💻 Author & Credits
**Developed by Kaleksanan Barqi Aji Massani**
*Customer Success & Tech Enthusiast*

*   **Core Logic:** Hybrid Price Action + AI Analysis.
*   **Credits:** CCXT, Pandas TA, OpenAI/OpenRouter, CoinMarketCap API.