# 🦅 GOLDEN SWING TREND STRATEGY

## 📊 Deskripsi Strategi
Strategi ini dirancang untuk Swing Trading harian dengan probabilitas tinggi (High Winrate). Fokus utamanya adalah "Trend Following" pada timeframe besar (H4/Daily) dan mencari entry point presisi saat koreksi (pullback).

**Prinsip Utama:** "The Trend is Your Friend until it Bends."

---

## 🛠️ Konfigurasi Indikator
1.  **Trend Filter (Timeframe H4/Daily)**
    *   **EMA 50 & EMA 200**: Digunakan untuk menentukan arah tren utama.
    *   *Bullish*: Harga > EMA 50 > EMA 200.
    *   *Bearish*: Harga < EMA 50 < EMA 200.

2.  **Momentum & Entry (Timeframe H1)**
    *   **RSI (14)**: Tidak boleh dalam kondisi Extreme saat Entry (Hindari Buy di Overbought).
    *   **StochRSI**: Cari Cross Up di area Oversold (<20) untuk Buy saat Uptrend.

3.  **Volume**
    *   Pastikan volume meningkat saat terjadi pergerakan searah tren (Validasi kekuatan tren).

---

## 🎯 Aturan Entry (Long/Buy)
1.  **Syarat Tren**: Harga berada di atas EMA 200 dan EMA 50 pada Timeframe H4.
2.  **Fase Koreksi**: Tunggu harga melakukan *pullback* (turun) mendekati **EMA 50** atau **Support Level** terdekat.
3.  **Trigger**:
    *   Terbentuk pola candlestick pembalikan (Hammer, Bullish Engulfing, Morning Star) di area support/EMA.
    *   ATAU StochRSI cross up dari area oversold.
4.  **Validasi AI**: Sentiment market harus "Neutral" atau "Greed" (hindari entry saat "Extreme Fear" kecuali untuk reversal).

## 🎯 Aturan Entry (Short/Sell)
1.  **Syarat Tren**: Harga berada di bawah EMA 200 dan EMA 50 pada Timeframe H4.
2.  **Fase Koreksi**: Tunggu harga naik (*pullback*) mendekati **EMA 50** atau **Resistance Level**.
3.  **Trigger**:
    *   Terbentuk pola candlestick reversal (Shooting Star, Bearish Engulfing) di area resistance/EMA.
    *   ATAU StochRSI cross down dari area overbought.

---

## 🛡️ Manajemen Risiko (Money Management)
*   **Stop Loss (SL)**: 
    *   Ditempatkan sedikit di bawah *Swing Low* terakhir (untuk Buy) atau di atas *Swing High* terakhir (untuk Sell).
    *   Gunakan ATR Multiplier 2.0 untuk memberi ruang napas (avoid stop hunt).
*   **Take Profit (TP)**:
    *   **TP 1**: Rasio Risk:Reward 1:1.5 (Amankan sebagian profit).
    *   **TP 2**: Rasio Risk:Reward 1:3 atau saat menyentuh Resistance major berikutnya.
    *   **Trailing Stop**: Aktifkan saat harga sudah Running Profit > 1R.

## 🤖 Instruksi untuk AI (Prompt)
"Analisa tren pada H4. Jika Bullish, abaikan sinyal sell jangka pendek. Fokus cari titik pantul di support dinamis (EMA). Prioritaskan setup yang memiliki Risk:Reward minimal 1:2."
