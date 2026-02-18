AVAILABLE_STRATEGIES = {
    # 1. Fokus pada Pattern + Trend (The Conservative)
    'PATTERN_CONFLUENCE_TREND': "Strategi ini mewajibkan keselarasan antara Macro Trend {config.TIMEFRAME_TREND} dan visual pattern di {config.TIMEFRAME_SETUP}. RECOMMENDED EXECUTION: [MARKET] untuk menangkap momentum breakout yang valid.",

    # 2. Fokus pada Breakout Volatilitas (The Aggressive)
    'VOLATILITY_BREAKOUT_ADVANCED': "Mendeteksi breakout signifikan dengan volume tinggi dan ADX > 25. RECOMMENDED EXECUTION: [MARKET] karena harga bergerak cepat dan jarang pullback dalam waktu dekat.",

    # 3. Fokus pada Reversal & Liquidity (The Contrarian)
    'LIQUIDITY_REVERSAL_MASTER': "Mencari pembalikan arah di area Pivot (S1/R1) atau Liquidity Sweep. RECOMMENDED EXECUTION: [LIQUIDITY_HUNT] untuk mendapatkan harga terbaik saat 'Stop Hunt' terjadi, dengan R:R yang jauh lebih superior.",

    # 4. Fokus pada Sentimen & Whale Flow (The Follow-the-Money)
    'SMART_MONEY_FLOW': "Mengikuti jejak uang besar (Whale/Institutional). Jika data on-chain bullish kuat tapi harga masih dipahamin 'murah' (konsolidasi), gunakan [LIQUIDITY_HUNT]. Jika harga sudah mulai lari, gunakan [MARKET].",

    # 5. Fallback/Standard
    'STANDARD_MULTI_CONFIRMATION': "Analisa teknikal seimbang. Evaluasi Risk:Reward (R:R) dari opsi MARKET vs LIQUIDITY_HUNT. Pilih yang memberikan R:R terbaik dan probabilitas sukses tertinggi.",

    # 6. Fokus pada Sideways & Reversal (The Ranger)
    'BB_BOUNCE': "Jika ADX sedang lemah/sideways (< 20), fokus pada setup Reversal di area BB Top (Upper Band) atau BB Bottom (Lower Band). Sangat disarankan menggunakan [LIQUIDITY_HUNT] untuk mendapatkan harga entry terbaik saat terjadi pantulan."
}