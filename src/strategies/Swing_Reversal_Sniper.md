# 🎯 SNIPER REVERSAL STRATEGY

## 📊 Deskripsi Strategi
Strategi ini berfokus pada "Counter-Trend" atau mencari pembalikan arah saat market mengalami kondisi ekstrim (Overbought/Oversold). Cocok untuk kondisi market sideways atau saat tren sudah terlalu jenuh (exhaustion).

**Prinsip Utama:** "Buy Low, Sell High at Extremes."

---

## 🛠️ Konfigurasi Indikator
1.  **Volatility Filter**
    *   **Bollinger Bands (20, 2)**: Harga harus keluar atau menyentuh Band Atas/Bawah.
    *   Band yang melebar menandakan volatilitas tinggi (bagus untuk swing).

2.  **Momentum & Divergence**
    *   **RSI (14)**:
        *   *Overbought*: > 70 (Potensi Sell).
        *   *Oversold*: < 30 (Potensi Buy).
    *   **Divergence (PENTING)**:
        *   *Bullish Divergence*: Harga membuat Lower Low, tapi RSI membuat Higher Low.
        *   *Bearish Divergence*: Harga membuat Higher High, tapi RSI membuat Lower High.

---

## 🎯 Aturan Entry (Long/Buy - Reversal)
1.  **Kondisi Ekstrim**: Harga menyentuh atau menembus **Lower Bollinger Band**.
2.  **RSI**: RSI berada di bawah 30 (Oversold).
3.  **Konfirmasi Divergen**: Terlihat potensi Bullish Divergence (Opsional tapi sangat kuat).
4.  **Trigger**: Candle ditutup kembali *di dalam* Bollinger Band (Reject Lower Band) dengan formasi Bullish (Pinbar/Engulfing).

## 🎯 Aturan Entry (Short/Sell - Reversal)
1.  **Kondisi Ekstrim**: Harga menyentuh atau menembus **Upper Bollinger Band**.
2.  **RSI**: RSI berada di atas 70 (Overbought).
3.  **Konfirmasi Divergen**: Terlihat potensi Bearish Divergence.
4.  **Trigger**: Candle ditutup kembali *di dalam* Bollinger Band (Reject Upper Band) dengan formasi Bearish.

---

## 🛡️ Manajemen Risiko (Money Management)
*   **Stop Loss (SL)**: 
    *   Strict SL! Tempatkan di atas Swing High terakhir (untuk Sell) atau di bawah Swing Low terakhir (untuk Buy).
    *   Beri jarak buffer 1 ATR.
*   **Take Profit (TP)**:
    *   **TP 1**: Middle Bollinger Band (Basis Line).
    *   **TP 2**: Band sisi berlawanan (Upper Band untuk Buy, Lower Band untuk Sell).
*   **Rasio R:R**: Jangan ambil trade jika R:R kurang dari 1:2.

## 🤖 Instruksi untuk AI (Prompt)
"Cari kondisi market Jenuh (Extreme). Validasi dengan Bollinger Band rejection dan RSI. Pastikan ada Divergence untuk probabilitas tertinggi. Jangan entry melawan tren kuat jika tidak ada tanda pelemahan momentum yang jelas."
