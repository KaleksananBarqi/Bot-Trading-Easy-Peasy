# 🤖 Easy Peasy Trading Bot: Liquidity Hunt Specialist

<div align="center">
  <img width="1380" height="962" alt="Image" src="https://github.com/user-attachments/assets/17b117d9-5747-4170-9380-b2fbfa7169c1" />

  <br />
  
  ![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
  ![Binance](https://img.shields.io/badge/Binance-Futures-yellow?style=for-the-badge&logo=binance)
  ![DeepSeek](https://img.shields.io/badge/Brain-DeepSeek%20V3.2-blueviolet?style=for-the-badge)
  ![Vision AI](https://img.shields.io/badge/Vision-Llama%20Vision-ff69b4?style=for-the-badge)
  ![Sentiment AI](https://img.shields.io/badge/Sentiment-Xiaomi%20Mimo-orange?style=for-the-badge)
  ![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)
  ![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-5D6D7E?style=for-the-badge)
</div>

---

## 📖 Tentang Easy Peasy Bot (Liquidity Specialist Edition)

**Easy Peasy Trading Bot** kini telah berevolusi menjadi spesialis **Liquidity Hunt & Pivot Reversal**. Bot ini tidak lagi menebak-nebak arah tren sembarangan, melainkan fokus 100% pada perilaku "Smart Money" yang gemar memburu likuiditas retail (Stop Loss) sebelum membalikkan arah harga.

Dengan arsitektur **Triple AI Core**, seluruh kecerdasan buatan dikerahkan untuk satu tujuan: Validasi pola **Liquidity Sweep** di area Pivot (S1/R1).

### 🧠 The Triple AI Core: Unified for Liquidity Hunt
1.  **Strategic Brain (Logic AI)**: Ditenagai oleh **DeepSeek V3.2**. Bertugas menghitung Pivot Points (S1/R1) dan mendeteksi anomali volume saat harga menyentuh area likuiditas.
2.  **Visual Cortex (Vision AI)**: Ditenagai oleh **Llama-4-Maverick**. Memvalidasi chart candlestick secara visual untuk memastikan pola "Wick Rejection" atau "Fakeout" benar-benar terjadi.
3.  **Sentiment Analyst (Text AI)**: Ditenagai oleh **Xiaomi Mimo V2 Flash**. Memastikan sentimen pasar mendukung skenario reversal (misal: "Fear" ekstrem saat harga menyentuh Support, indikasi pantulan).

---

## 🔥 Bukti Performa: Backtest Januari 2026

Strategi **LIQUIDITY_REVERSAL_MASTER** telah terbukti sangat tangguh dalam simulasi pasar terbaru. Berikut adalah hasil backtest resmi untuk periode **1 Januari 2026 - 31 Januari 2026**.

### 📈 Ringkasan Statistik
| Metrik | Hasil |
| :--- | :--- |
| **Total Profit** | **+$845.42 (+84.54%)** 🚀 |
| **Win Rate** | **84.52%** (71 TP, 13 SL) |
| **Drawdown** | **-1.82%** (Sangat Aman) |
| **Profit Factor** | **7.94** |
| **Total Trade** | 84 Transaksi |

### 🏆 Performa per Koin
*   **SOL/USDT**: Profit **$566.16** (40 trades) - *Best Performer*
*   **BTC/USDT**: Profit **$279.26** (44 trades)

### 📂 Dokumen Hasil Backtest
Hasil detail simulasi telah tersimpan di repository ini:
*   📊 **Visualisasi Equity**: [backtest_results.png](./backtest_results.png)
*   📝 **Detail Transaksi**: [backtest_results.csv](./backtest_results.csv)

> *Analisis Singkat: Strategi Liquidity Hunt bekerja sangat baik di bulan Januari 2026 dengan tingkat kemenangan di atas 80% dan drawdown yang sangat kecil (< 2%). Pergerakan SOL memberikan kontribusi profit terbesar.*

---

## 🚀 Fitur Utama & Keunggulan Strategi

### 1. 🎯 LIQUIDITY_REVERSAL_MASTER Strategy
Ini adalah satu-satunya strategi yang digunakan. Fokusnya sederhana namun mematikan:
*   **Konsep**: Mencari pembalikan arah di area **Pivot (S1/R1)** atau **Liquidity Sweep**.
*   **Mekanisme**: Bot menunggu harga menembus level support/resistance kunci (tempat retail trader menaruh SL), lalu masuk posisi saat harga berbalik (reclaim level).
*   **Kenapa Efektif?**: Mengikuti jejak institusi/paus yang butuh likuiditas besar untuk mengisi order mereka.

### 2. ⚖️ Dual Execution Plan (Anti-Bias AI)
Bot tidak menebak arah. Untuk setiap koin, bot menyiapkan dua jebakan:
*   **Scenario A (Long Trap)**: Entry di bawah S1 (menunggu harga *sweep* ke bawah lalu naik).
*   **Scenario B (Short Trap)**: Entry di atas R1 (menunggu harga *sweep* ke atas lalu turun).
AI akan mengeksekusi skenario yang tervalidasi oleh *price action* real-time.

### 3. 👁️ Vision AI Verification
Tidak hanya angka, Vision AI melihat chart untuk konfirmasi:
*   Apakah candle penembus hanya berupa "ekor" (wick) panjang? (Tanda rejection kuat)
*   Apakah ada divergensi RSI/MACD saat sweep terjadi?

### 4. 🔄 Intelligent Trailing Stop Loss
Mengunci profit secara agresif saat pantulan terjadi:
*   SL bergerak otomatis setiap harga naik 0.75% dari titik terendah (Long).
*   Memastikan profit dari *reversal* tidak berubah menjadi loss jika tren gagal berlanjut.

---

## 🛠️ Instalasi & Konfigurasi

### Persyaratan Sistem & API
*   **Python 3.10+** (Wajib)
*   **Akun Binance Futures**: API Key & Secret Key
*   **AI Provider API**: DeepSeek / OpenRouter
*   **Telegram Bot**: Untuk notifikasi cuan real-time

### 💻 Cara Install (Quick Start)

**1. Clone & Setup**
```bash
git clone https://github.com/KaleksananBarqi/Bot-Trading-Easy-Peasy.git
cd Bot-Trading-Easy-Peasy
python -m venv venv
# Windows: .\venv\Scripts\Activate
# Mac/Linux: source venv/bin/activate
pip install -e .
```

**2. Konfigurasi**
Buat file `.env` dan isi API Key Anda (lihat `.env.example`).

**3. Jalankan Bot**
```bash
python src/main.py
```

---

## 📊 Struktur Proyek

```text
📂 Bot-Trading-Easy-Peasy/
 ├── 📂 src/                     # Source Code Utama
 │    ├── 📂 modules/            # Modul AI (Brain, Vision, Sentiment)
 │    ├── ⚙️ config.py           # Konfigurasi Strategi
 │    └── 🚀 main.py             # Titik Masuk Bot
 ├── 📂 backtesting/             # Sistem Simulasi
 ├── 📜 backtest_results.csv     # Data Historis Jan 2026
 └── 🖼️ backtest_results.png     # Grafik Performa Jan 2026
```

---

## 🤝 Kontribusi & Disclaimer
Bot ini adalah alat bantu eksperimental. Hasil masa lalu (Januari 2026) tidak menjamin kinerja masa depan. Gunakan manajemen risiko yang bijak.

**Developed with ☕ & 🤖 by [Kaleksanan Barqi Aji Massani](https://github.com/KaleksananBarqi)**
