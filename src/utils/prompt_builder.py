
import config

def format_price(value):
    """
    Format price based on value size to avoid rounding errors on small caps.
    < 1.0   : 5 decimals (0.13779)
    < 50.0  : 4 decimals (24.1234)
    >= 50.0 : 2 decimals (65000.12)
    """
    if not isinstance(value, (int, float)): return str(value)
    if value < 1.0: return f"{value:.5f}"
    if value < 50.0: return f"{value:.4f}"
    return f"{value:.2f}"

def get_trend_narrative(price: float, ema_fast: float, ema_slow: float) -> tuple[str, str]:
    """
    Menghasilkan narasi trend yang jelas berdasarkan posisi Price terhadap kedua EMA.
    
    Returns:
        tuple: (trend_narrative, ema_alignment)
        
    Logic Matrix:
    | Price vs EMA_Fast | Price vs EMA_Slow | Narrative           |
    |-------------------|-------------------|---------------------|
    | Above             | Above             | STRONG BULLISH      |
    | Below             | Below             | STRONG BEARISH      |
    | Below             | Above             | BULLISH PULLBACK    |
    | Above             | Below             | BEARISH BOUNCE      |
    """
    price_above_fast = price > ema_fast
    price_above_slow = price > ema_slow
    
    # EMA Alignment (Fast vs Slow)
    if ema_fast > ema_slow:
        ema_alignment = "BULLISH ALIGNMENT (Fast > Slow)"
    else:
        ema_alignment = "BEARISH ALIGNMENT (Fast < Slow)"
    
    # Trend Narrative based on matrix
    if price_above_fast and price_above_slow:
        trend_narrative = "STRONG BULLISH - Price above both EMAs"
    elif not price_above_fast and not price_above_slow:
        trend_narrative = "STRONG BEARISH - Price below both EMAs"
    elif not price_above_fast and price_above_slow:
        trend_narrative = "BULLISH PULLBACK - Price dipping but still in uptrend"
    elif price_above_fast and not price_above_slow:
        trend_narrative = "BEARISH BOUNCE - Price recovering but still in downtrend"
    else:
        trend_narrative = "UNCLEAR"
    
    return trend_narrative, ema_alignment

def build_market_prompt(symbol, tech_data, sentiment_data, onchain_data, pattern_analysis=None, dual_scenarios=None, show_btc_context=True, sentiment_analysis=None):
    """
    Menyusun prompt untuk AI berdasarkan data teknikal, sentimen, dan on-chain.
    Struktur Baru: Multi-Timeframe (Macro -> Setup -> Execution).
    Args:
    Args:
        dual_scenarios (dict): Result dari calculate_dual_scenarios(), berisi {"long": {...}, "short": {...}}.
        show_btc_context (bool): Jika False, data BTC dan korelasinya akan DISEMBUNYIKAN total dari AI.
        sentiment_analysis (dict): Hasil analisa sentimen AI yang sudah matang (Optional).
    """
    
    # 0. VALIDATION: Critical Data Check
    if not tech_data or tech_data.get('price', 0) == 0:
        return None # Abort signal generation if data is invalid
    
    # ==========================================
    # 1. PARSING DATA (Timeframe Segregation)
    # ==========================================

    # --- A. MACRO VIEW (Trend Timeframe / 1H) ---
    btc_trend = tech_data.get('btc_trend', 'NEUTRAL')
    btc_corr = tech_data.get('btc_correlation', 0)
    market_struct = tech_data.get('market_structure', 'UNKNOWN')
    
    # Pivot Points
    # Pivot Points
    pivots = tech_data.get('pivots')
    pivot_str = "N/A"
    price_vs_s1 = "N/A"
    price_vs_r1 = "N/A"
    
    if pivots:
        pivot_str = f"P={format_price(pivots['P'])}, S1={format_price(pivots['S1'])}, R1={format_price(pivots['R1'])}"
        
        # [NEW] Price Distance Calculation
        s1 = pivots['S1']
        r1 = pivots['R1']
        if s1 > 0:
            dist_s1 = ((tech_data.get('price', 0) - s1) / s1) * 100
            price_vs_s1 = f"{dist_s1:+.2f}% ({'ABOVE' if dist_s1 > 0 else 'BELOW'} S1)"
        if r1 > 0:
            dist_r1 = ((tech_data.get('price', 0) - r1) / r1) * 100
            price_vs_r1 = f"{dist_r1:+.2f}% ({'ABOVE' if dist_r1 > 0 else 'BELOW'} R1)"

    # --- B. EXECUTION DATA (Execution Timeframe / 15m) ---
    price = tech_data.get('price', 0)
    rsi = tech_data.get('rsi', 50)
    adx = tech_data.get('adx', 0)
    
    # EMA Analysis
    ema_fast = tech_data.get('ema_fast', 0)
    ema_slow = tech_data.get('ema_slow', 0)
    ema_pos = tech_data.get('price_vs_ema', 'UNKNOWN')
    trend_major = tech_data.get('trend_major', 'UNKNOWN')
    
    # Generate clear trend narrative for AI
    trend_narrative, ema_alignment = get_trend_narrative(price, ema_fast, ema_slow)
    
    # Volatility & Momentum
    bb_upper = tech_data.get('bb_upper', 0)
    bb_lower = tech_data.get('bb_lower', 0)
    atr = tech_data.get('atr', 0)
    stoch_k = tech_data.get('stoch_k', 50)
    stoch_d = tech_data.get('stoch_d', 50)
    
    # Order Book Depth
    ob_data = tech_data.get('order_book', {})
    ob_imp = "N/A"
    if ob_data:
        bid_vol = ob_data.get('bids_vol_usdt', 0) / 1000 # to K
        ask_vol = ob_data.get('asks_vol_usdt', 0) / 1000 # to K
        imbalance = ob_data.get('imbalance_pct', 0)
        ob_imp = f"Bids: ${bid_vol:.1f}K | Asks: ${ask_vol:.1f}K | Imbalance: {imbalance:+.1f}%"
    
    # Volume & Market Data
    volume = tech_data.get('volume', 0)
    vol_ma = tech_data.get('vol_ma', 0)
    
    # [NEW] Pre-calculate Volume Ratio
    vol_ratio = (volume / vol_ma) if vol_ma > 0 else 0
    vol_threshold = config.VOLUME_SPIKE_MULTIPLIER
    vol_meets_threshold = vol_ratio >= vol_threshold
    funding_rate = tech_data.get('funding_rate', 0)
    funding_rate = tech_data.get('funding_rate', 0)
    open_interest = tech_data.get('open_interest', 'N/A')

    # Wick Rejection
    wick_data = tech_data.get('wick_rejection', {})
    wick_signal = wick_data.get('recent_rejection', 'NONE')
    wick_strength = wick_data.get('rejection_strength', 0)
    wick_str = f"{wick_signal} (Strength: {wick_strength:.1f}x)" if wick_signal != "NONE" else "No Rejection"
    
    # LSD (Long/Short Ratio)
    lsr_data = tech_data.get('lsr', {}) or {}
    lsr_val = lsr_data.get('longShortRatio', 'N/A')
    long_pct = float(lsr_data.get('longAccount', 0)) * 100 if lsr_data.get('longAccount') else 0
    short_pct = float(lsr_data.get('shortAccount', 0)) * 100 if lsr_data.get('shortAccount') else 0

    # [NEW] Parsing Last Candle for Sweep Validation
    last_candle = tech_data.get('last_candle', {})
    last_open = last_candle.get('open', 0)
    last_high = last_candle.get('high', 0)
    last_low = last_candle.get('low', 0)
    last_close = last_candle.get('close', 0)

    # --- C. SENTIMENT & ON-CHAIN ---
    fng_value = sentiment_data.get('fng_value', 50)
    fng_text = sentiment_data.get('fng_text', 'Neutral')
    
    sentiment_section_str = ""
    
    if sentiment_analysis and isinstance(sentiment_analysis, dict):
        # [OPTIMIZED] Use Pre-Calculated AI Sentiment
        s_score = sentiment_analysis.get('sentiment_score', 50)
        s_status = sentiment_analysis.get('overall_sentiment', 'NEUTRAL')
        s_summary = sentiment_analysis.get('summary', 'No summary available.')
        s_risk = sentiment_analysis.get('risk_assessment', 'UNKNOWN')
        
        # [NEW] Additional Fields
        s_phase = sentiment_analysis.get('market_phase', 'UNKNOWN')
        s_smart = sentiment_analysis.get('smart_money_activity', 'UNKNOWN')
        s_retail = sentiment_analysis.get('retail_sentiment', 'UNKNOWN')
        s_drivers = sentiment_analysis.get('key_drivers', [])
        s_drivers_str = ", ".join(s_drivers) if s_drivers else "None"
        
        sentiment_section_str = (
            f"- AI Market Sentiment: {s_status} (Score: {s_score}/100)\n"
            f"- Market Phase: {s_phase}\n"
            f"- Smart Money Activity: {s_smart}\n"
            f"- Retail Sentiment: {s_retail}\n"
            f"- Key Drivers: {s_drivers_str}\n"
            f"- Fear & Greed Index: {fng_value} ({fng_text})\n"
            f"- Risk Assessment: {s_risk}\n"
            f"- Key Context: {s_summary}"
        )
    else:
        # [FALLBACK] Use Raw Data (Mini Mode)
        # Hemat token: Cuma F&G + Stablecoin Inflow, tanpa list berita panjang
        inflow_status = onchain_data.get('stablecoin_inflow', 'Neutral')
        sentiment_section_str = (
            f"- Fear & Greed Index: {fng_value} ({fng_text})\n"
            f"- Stablecoin Inflow: {inflow_status}\n"
            f"- Note: Deep sentiment analysis not available yet (using fallback)."
        )

    # ==========================================
    # 2. CONTEXTUAL LOGIC BUILDER
    # ==========================================
    
    # Strategy List
    strategies = ["AVAILABLE STRATEGIES:"]
    for name, desc in config.AVAILABLE_STRATEGIES.items():
        # [MODIFIED] Dynamically format description to replace placeholders like {config.TIMEFRAME_TREND}
        try:
            formatted_desc = desc.format(config=config)
        except Exception:
            formatted_desc = desc
        strategies.append(f"[{name}]: {formatted_desc}")
    
    # Additional Context
    # strategies.append("\nADDITIONAL RULES:")
    # Additional Context
    
    strat_str = "\n".join(strategies)

    # Dynamic BTC Warning
    btc_instruction = ""
    if show_btc_context and btc_corr >= config.CORRELATION_THRESHOLD_BTC:
        btc_instruction = f"IMPORTANT: High BTC Correlation ({btc_corr:.2f}). Do NOT open positions against BTC Trend ({btc_trend})."

    # ==========================================
    # 2.5 DUAL TRADE SCENARIOS (Long vs Short)
    # ==========================================
    execution_options_str = "N/A"
    if dual_scenarios:
        long_s = dual_scenarios.get('long', {})
        short_s = dual_scenarios.get('short', {})
        
        long_m = long_s.get('market', {})
        long_h = long_s.get('liquidity_hunt', {})
        short_m = short_s.get('market', {})
        short_h = short_s.get('liquidity_hunt', {})
        
        if config.ENABLE_MARKET_ORDERS:
            # Full Mode: Show both Aggressive (Market) and Passive (Limit) for each direction
            execution_options_str = f"""
[EXECUTION SCENARIOS]
SCENARIO A: Buy/Long Setup
  > Option A1 (Aggressive/Market): Entry={format_price(long_m.get('entry', 0))}, SL={format_price(long_m.get('sl', 0))}, TP={format_price(long_m.get('tp', 0))}, R:R=1:{long_m.get('rr', 0)}
  > Option A2 (Passive/Limit): Entry={format_price(long_h.get('entry', 0))}, SL={format_price(long_h.get('sl', 0))}, TP={format_price(long_h.get('tp', 0))}, R:R=1:{long_h.get('rr', 0)}

SCENARIO B: Sell/Short Setup
  > Option B1 (Aggressive/Market): Entry={format_price(short_m.get('entry', 0))}, SL={format_price(short_m.get('sl', 0))}, TP={format_price(short_m.get('tp', 0))}, R:R=1:{short_m.get('rr', 0)}
  > Option B2 (Passive/Limit): Entry={format_price(short_h.get('entry', 0))}, SL={format_price(short_h.get('sl', 0))}, TP={format_price(short_h.get('tp', 0))}, R:R=1:{short_h.get('rr', 0)}
"""
        else:
            # Passive Only Mode: Show only Liquidity Hunt for each direction
            execution_options_str = f"""
[EXECUTION SCENARIOS]
SCENARIO A: Buy/Long Setup
  > Entry={format_price(long_h.get('entry', 0))}, SL={format_price(long_h.get('sl', 0))}, TP={format_price(long_h.get('tp', 0))}, R:R=1:{long_h.get('rr', 0)}

SCENARIO B: Sell/Short Setup
  > Entry={format_price(short_h.get('entry', 0))}, SL={format_price(short_h.get('sl', 0))}, TP={format_price(short_h.get('tp', 0))}, R:R=1:{short_h.get('rr', 0)}
"""

    # ==========================================
    # 2.6 PREPARE PATTERN & RAW DATA
    # ==========================================
    pattern_text = "Not Available"
    raw_stats_str = ""
    
    if isinstance(pattern_analysis, dict):
        # New Format with Raw Data
        pattern_text = pattern_analysis.get('analysis', 'Not Available')
        raw = pattern_analysis.get('raw_data', {})
        if raw:
            raw_stats_str = (
                 f"- [RAW DATA] Last Candle: O={format_price(raw.get('open'))} H={format_price(raw.get('high'))} L={format_price(raw.get('low'))} C={format_price(raw.get('close'))}\n"
                 f"- [INDICATORS] MACD: {raw.get('macd',0):.4f} | Sig: {raw.get('macd_signal',0):.4f} | Hist: {raw.get('macd_hist',0):.4f} | Vol: {raw.get('volume',0):.1f}"
            )
    else:
        # Legacy Format (String only)
        pattern_text = pattern_analysis if pattern_analysis else "Not Available"

    pattern_section_content = f"- Chart Pattern Analysis: {pattern_text}\n"
    if raw_stats_str:
        pattern_section_content += f"{raw_stats_str}\n"
    


    # ==========================================
    # 3. PROMPT CONSTRUCTION
    # ==========================================
    
    # [LOGIC: BTC CORRELATION VISIBILITY]
    # Jika show_btc_context = True, tampilkan data BTC.
    # Jika False (karena rule/correlation low), HILANGKAN TOTAL dari pandangan AI.
    
    macro_section = ""
    btc_instruction_prompt = ""
    
    if show_btc_context:
        macro_section = f"""
--------------------------------------------------
1. MACRO VIEW (TIMEFRAME: {config.TIMEFRAME_TREND})
- Global BTC Trend: {btc_trend} (EMA {config.BTC_EMA_PERIOD})
- BTC Correlation: {btc_corr:.2f}
- Market Structure: {market_struct} (Swing High/Low Analysis)
- Pivot Points: {pivot_str}
--------------------------------------------------
"""
        btc_instruction_prompt = config.PROMPT_BTC_WITH_CONTEXT.format(
            market_struct=market_struct,
            btc_trend=btc_trend,
            btc_instruction=btc_instruction,
            rsi_oversold=config.RSI_DEEP_OVERSOLD,
            rsi_overbought=config.RSI_DEEP_OVERBOUGHT
        )
    else:
        # Jika BTC Hidden (Independent Move), hanya tampilkan Market Structure & Pivot
        macro_section = f"""
--------------------------------------------------
1. MACRO VIEW (TIMEFRAME: {config.TIMEFRAME_TREND})
- Market Structure: {market_struct} (Swing High/Low Analysis)
- Pivot Points: {pivot_str}
--------------------------------------------------
"""
        btc_instruction_prompt = config.PROMPT_BTC_NO_CONTEXT.format(
            timeframe_trend=config.TIMEFRAME_TREND,
            market_struct=market_struct,
            rsi_oversold=config.RSI_DEEP_OVERSOLD,
            volume_spike=config.VOLUME_SPIKE_MULTIPLIER,
            rsi_overbought=config.RSI_DEEP_OVERBOUGHT
        )

    # [LOGIC: STRATEGY INSTRUCTION - LIQUIDITY HUNT PROTOCOL]
    # [LOGIC: STRATEGY INSTRUCTION - LIQUIDITY HUNT PROTOCOL]
    execution_mode_text = '- Market Order: Available for confirmed setups' if config.ENABLE_MARKET_ORDERS else 'pass'
    
    strategy_instruction = config.PROMPT_STRATEGY_SELECTION.format(
        volume_spike=config.VOLUME_SPIKE_MULTIPLIER,
        adx_period=config.ADX_PERIOD,
        ema_fast=config.EMA_FAST,
        ema_slow=config.EMA_SLOW,
        execution_mode_text=execution_mode_text
    )

    prompt = f"""
ROLE: {config.AI_SYSTEM_ROLE}

TASK: Analyze market data for {symbol} using the Multi-Timeframe logic below. Decide to BUY, SELL, or WAIT.

{macro_section}

--------------------------------------------------
2. SETUP VALIDATION (TIMEFRAME: {config.TIMEFRAME_SETUP})
{pattern_section_content}
--------------------------------------------------

--------------------------------------------------
3. EXECUTION TRIGGER (TIMEFRAME: {config.TIMEFRAME_EXEC})
[MOMENTUM]
- RSI ({config.RSI_PERIOD}): {rsi:.2f}
- StochRSI: K={stoch_k:.2f}, D={stoch_d:.2f}
- ADX ({config.ADX_PERIOD}): {adx:.2f} (Trend Strength)

[TREND]
- Current Price: {format_price(price)}
- Trend Signal: {trend_narrative}
- EMA Details: Fast({config.EMA_FAST})={format_price(ema_fast)} | Slow({config.EMA_SLOW})={format_price(ema_slow)} | {ema_alignment}

[PRICE ACTION]
- Last Candle ({config.TIMEFRAME_EXEC}): O={format_price(last_open)} H={format_price(last_high)} L={format_price(last_low)} C={format_price(last_close)}
- Price vs S1: {price_vs_s1}
- Price vs R1: {price_vs_r1}
- Wick Rejection (Last 5 Candles): {wick_str}
- NOTE: Strong rejection (>2x body) near S1/R1 suggests potential reversal.

[VOLATILITY & VOLUME]
- Bollinger Bands: Upper={format_price(bb_upper)}, Lower={format_price(bb_lower)}
- ATR: {atr:.5f}
- Volume: {volume} | Avg: {vol_ma} | Ratio: {vol_ratio:.2f}x {'✓ SPIKE' if vol_meets_threshold else '✗ NORMAL'}

[ORDER BOOK DEPTH]
- Depth (2%): {ob_imp}
- NOTE: Significant Imbalance (>20%) suggests potential Liquidity Hunt or Breakout.

[MARKET DATA]
- Funding Rate: {funding_rate:.6f}%
- Open Interest: {open_interest}
- Top Trader L/S Ratio: {lsr_val} (Longs: {long_pct:.1f}% / Shorts: {short_pct:.1f}%)
--------------------------------------------------

--------------------------------------------------
--------------------------------------------------
4. SENTIMENT & EXTERNAL FACTORS
{sentiment_section_str}
--------------------------------------------------
--------------------------------------------------


{strat_str}

{execution_options_str}

FINAL INSTRUCTIONS (STRATEGY SELECTION PROTOCOL):
{btc_instruction_prompt}

REMINDER: Adhere strictly to the TREND LOCK GATE defined in your system role.

2. ZONE ANALYSIS:
   - Identify if Price is testing key levels (Pivot S1 or R1).
   - If Price is strictly between S1 and R1 -> "MID_RANGE" (INSIDE_RANGE).

3. INTERPRET REACTION (Zone Reaction):
   - WICK_REJECTION: Wick penetrates level, Body closes back inside range. (Signal: Reversal)
   - BREAKOUT_CLOSE: Candle Body closes BEYOND the level with volume. (Signal: Breakout/Continuation)
   - TESTING: Price hovering at level without clear resolution. (Signal: Wait)

4. STRATEGY MAPPING:
   - REJECTION at S1 -> Validates LIQUIDITY_REVERSAL_MASTER (Long)
   - REJECTION at R1 -> Validates LIQUIDITY_REVERSAL_MASTER (Short)
   - BREAKOUT below S1 -> Validates BREAKDOWN_FOLLOW (Short)
   - BREAKOUT above R1 -> Validates BREAKDOWN_FOLLOW (Long)
   - STRONG TREND + PULLBACK in MID_RANGE -> Validates PULLBACK_CONTINUATION

5. NO-TRADE CONDITIONS:
   - MID_RANGE with no clear trend or pullback.
   - Trend Lock active and Setup contradicts major trend (and no exception met).

{strategy_instruction}

8. DECISION: Return WAIT if no setup confirmed OR trend filter disqualifies all scenarios.
"""

    execution_mode_json = '{ "MARKET" | "LIMIT" }' if config.ENABLE_MARKET_ORDERS else '"LIMIT"'
    
    output_format_prompt = config.PROMPT_MARKET_ANALYSIS_OUTPUT_FORMAT.format(
        execution_mode_json=execution_mode_json
    )

    prompt += output_format_prompt
    return prompt

def build_sentiment_prompt(sentiment_data, onchain_data):
    """
    Menyusun prompt khusus untuk Analisa Sentimen AI.
    Fokus: Berita Global, Fear & Greed, Whale Activity.
    Output: JSON dengan key 'analysis': 'sentiment'
    """
    
    # 1. Parsing Data
    fng_value = sentiment_data.get('fng_value', 50)
    fng_text = sentiment_data.get('fng_text', 'Neutral')
    news_headlines = sentiment_data.get('news', [])
    news_str = "\n".join([f"- {n}" for n in news_headlines]) if news_headlines else "No major news."
    
    whale_activity = onchain_data.get('whale_activity', [])
    whale_str = "\n".join([f"- {w}" for w in whale_activity]) if whale_activity else "No significant whale activity detected."
    inflow_status = onchain_data.get('stablecoin_inflow', 'Neutral')

    # 2. Prompt Construction
    # 2. Prompt Construction
    prompt = config.PROMPT_SENTIMENT_ANALYSIS.format(
        fng_value=fng_value,
        fng_text=fng_text,
        inflow_status=inflow_status,
        whale_str=whale_str,
        news_str=news_str
    )
    return prompt

def build_pattern_recognition_prompt(symbol, timeframe, raw_data=None):
    """
    Menyusun prompt untuk Vision AI Pattern Recognition.
    """
    raw_info = ""
    if raw_data:
        raw_info = (
            f"\n\n[SUPPLEMENTARY DATA]\n"
            f"Here are the exact numbers for the latest candle in the chart:\n"
            f"- Price: Open={raw_data.get('open')}, High={raw_data.get('high')}, Low={raw_data.get('low')}, Close={raw_data.get('close')}\n"
            f"- MACD (12,26,9): Line={raw_data.get('macd', 0):.4f}, Signal={raw_data.get('macd_signal', 0):.4f}, Histogram={raw_data.get('macd_hist', 0):.4f}\n"
            f"- Volume: {raw_data.get('volume', 0)}\n"
        )

    prompt_text = config.PROMPT_PATTERN_RECOGNITION.format(
        timeframe=timeframe,
        symbol=symbol,
        raw_info=raw_info
    )
    return prompt_text

