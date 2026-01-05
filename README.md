# 🤖 Easy Peasy Trading Bot: Hybrid Sniper Strategy

<img width="1249" height="882" alt="Image" src="https://github.com/user-attachments/assets/9627dc67-76d4-4c80-8904-efe8f8c1d33c" />

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Binance](https://img.shields.io/badge/Binance-Futures-yellow?style=for-the-badge&logo=binance)
![Strategy](https://img.shields.io/badge/Strategy-Hybrid%20Sniper-red?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)

## 📖 Easy Peasy Trading Bot (Smart Hybrid Edition)
Easy Peasy Trading Bot adalah sistem trading algoritmik otomatis untuk pasar Binance Futures. Dibangun menggunakan Python, bot ini menerapkan pendekatan Hybrid Strategy yang adaptif: mampu beralih strategi saat pasar Trending maupun Sideways.

Versi terbaru ini dilengkapi dengan **"Smart Correlation Engine"** dan **"Sector Risk Management"**, membuat bot mampu membedakan mana koin yang harus patuh pada tren Bitcoin dan mana koin yang sedang "Decoupled" (bergerak mandiri), serta mencegah penumpukan risiko pada satu kategori koin saja.

## 🚀 Fitur Unggulan

### 1. 🧠 Hybrid Logic Engine
Bot tidak terpaku pada satu gaya trading. Menggunakan ADX (Average Directional Index) sebagai otak utama:
*   **Trend Mode (ADX > 25):** Mengaktifkan strategi Trend Trap Pullback. Bot menunggu harga koreksi cantik ke area EMA sebelum ikut tren.
*   **Sideways Mode (ADX < 20):** Mengaktifkan strategi BB Bounce Scalp. Bot melakukan jual-beli cepat (ping-pong) di area batas Bollinger Bands saat pasar tenang.

### 2. 👑 Smart King BTC & Auto-Decoupling (NEW!)
Bot ini memiliki hierarki, namun sekarang lebih cerdas:
*   **Correlation Filter:** Bot menghitung korelasi pergerakan Altcoin terhadap Bitcoin secara real-time.
*   **Strict Mode (High Correlation):** Jika koin bergerak searah dengan BTC (Korelasi > 0.5), bot akan patuh pada tren BTC (King Filter). Jika BTC Bearish, bot dilarang Long.
*   **Decoupled Mode (Low Correlation):** Jika koin terdeteksi bergerak mandiri/berbeda arah dari BTC (Korelasi < 0.5), fitur Auto-Decouple aktif. Bot diizinkan mengambil sinyal (Long/Short) meskipun berlawanan dengan tren BTC. Cocok untuk koin yang sedang dipompa bandar atau ada berita khusus.

### 3. ⚖️ Sector Exposure Limit (NEW!)
Manajemen risiko tingkat lanjut berbasis kategori koin.
*   Anda bisa mengelompokkan koin (contoh: L1, MEME, AI, PAYMENT).
*   **Max Position per Category:** Bot membatasi jumlah posisi terbuka dalam satu sektor. Contoh: Jika sudah ada posisi Long di DOGE, bot tidak akan mengambil posisi di SHIB meskipun ada sinyal, untuk mencegah risiko berlebih di sektor Meme.

### 4. 🔫 Sniper / Liquidity Hunt
Fitur "Anti-Retail" andalan. Alih-alih masuk di harga sekarang (Market), bot menghitung jarak ATR untuk memprediksi letak Stop Loss retail trader. Bot akan memasang Limit Order di area likuiditas tersebut untuk mendapatkan harga diskon terbaik ("Sniper Entry") dan mengurangi risiko drawdown.

### 5. 🛡️ Guardian Safety Monitor
Sistem keamanan berbasis Event-Driven Asyncio:
*   Mendeteksi "Ghost Orders" (order nyangkut tanpa posisi).
*   Memastikan setiap posisi terbuka PASTI memiliki Hard Stop Loss (SL) dan Take Profit (TP).
*   Membersihkan Limit Order Sniper yang sudah kadaluarsa agar margin tidak tertahan.

### 6. 💰 Dynamic Compounding
Manajemen uang otomatis. Bot membaca saldo wallet secara real-time dan menggunakan persentase risiko (default 5%) dari saldo Available. Jika akun tumbuh, ukuran posisi otomatis membesar (Compounding).

### 7. 📱 Telegram Integration
Laporan lengkap real-time langsung ke saku Anda:
*   Notifikasi Status Bot & WebSocket.
*   **Detailed Signal:** Menampilkan data teknikal (RSI, ADX), Status Korelasi BTC (🔗 Linked / 🔓 Decoupled), dan Sektor Koin.
*   Laporan PnL (Profit/Loss) otomatis saat posisi ditutup.

## 📊 Performa Backtest (Simulasi)

Berdasarkan pengujian data historis (1 - 30 Des 2025):

| Metric | Value |
| :--- | :--- |
| **Modal Awal** | $100.00 |
| **Net Profit** | **+$4,976.46** 🚀 |
| **Total Trade** | 1,206 Trades |
| **Win Rate** | **65.09%** |
| **Profit Factor** | 3.85 |
| **Top Coin** | ZEC/USDT (Champion 🏆) |

> *Disclaimer: Hasil masa lalu tidak menjamin kinerja masa depan. Backtest menggunakan data historis optimal.*

---

## 🛠️ Cara Install (Untuk Pemula)

Ikuti langkah ini satu per satu. Jangan terburu-buru.

### Persiapan
Pastikan komputer/laptop Anda sudah terinstall:
1.  **Python** (Versi 3.10 ke atas). [Download di sini](https://www.python.org/downloads/).
2.  **Git** (Opsional, untuk clone repo).

### Langkah 1: Download / Clone Repository
Buka terminal (CMD atau PowerShell), lalu arahkan ke folder di mana Anda ingin menyimpan bot.
```bash
gh repo clone KaleksananBarqi/Bot-Trading-Easy-Peasy-Binance

```

*(Atau cukup download ZIP dari GitHub dan ekstrak).*

### Langkah 2: Buat Virtual Environment (Wajib)

Ini agar library bot tidak bentrok dengan sistem komputer lain.

```bash
# Untuk Windows
python -m venv venv
.\venv\Scripts\activate

# Untuk Linux/Mac
python3 -m venv venv
source venv/bin/activate

```

*Tanda berhasil: Di terminal akan muncul tulisan `(venv)` di sebelah kiri.*

### Langkah 3: Install Dependencies

Install semua "kebutuhan" bot yang ada di file `requirements.txt`.

```bash
pip install -r requirements.txt

```

### Langkah 4: Konfigurasi API Key

1. Buat file baru bernama `.env` di dalam folder project.
2. Buka file `.env` dengan Notepad/VS Code, lalu isi data berikut (Dapatkan dari Binance & BotFather Telegram):

```env
# Binance API (Pilih mau pakai Testnet atau Live)
BINANCE_API_KEY=masukan_api_key_asli_disini
BINANCE_SECRET_KEY=masukan_secret_key_asli_disini

# Binance Testnet (Untuk latihan/demo)
BINANCE_TESTNET_KEY=masukan_key_testnet_disini
BINANCE_TESTNET_SECRET=masukan_secret_testnet_disini

# Telegram Config
TELEGRAM_TOKEN=123456:ABC-DefGhiJklmNoPqrStu...
TELEGRAM_CHAT_ID=123456789

```

### Langkah 5: Sesuaikan Config (Opsional)

Buka file `config.py`. Anda bisa mengubah:

* `PAKAI_DEMO = True` (Ubah ke `False` jika ingin pakai uang asli).
* `RISK_PERCENT_PER_TRADE = 5.0` (Resiko per trade).
* `DAFTAR_KOIN` (List koin yang ingin ditradingkan).

### Langkah 6: Jalankan Bot 🚀

```bash
python main.py

```

Jika berhasil, akan muncul pesan di terminal:
`✅ WebSocket Connected! System Online.`

---

## ⚠️ Disclaimer (Penting!)

Bot ini adalah alat bantu trading (tools), bukan mesin pencetak uang ajaib.

1. **Resiko Tinggi:** Trading Futures memiliki resiko likuidasi (uang habis).
2. **DYOR (Do Your Own Research):** Penulis tidak bertanggung jawab atas kerugian finansial yang terjadi akibat penggunaan kode ini.
3. **Gunakan Testnet:** Sangat disarankan mencoba di akun DEMO (Testnet) minimal 1 minggu sebelum menggunakan uang asli.

---

## 👨‍💻 Author & Credits

**Developed by Kaleksanan Barqi Aji Massani**
*Customer Success & Tech Enthusiast*

* **Logic Core:** Based on Hybrid Price Action (Trend + Mean Reversion).
* **Special Thanks:** To Open Source Community (CCXT, Pandas TA) & Crypto Analyst Mentors.