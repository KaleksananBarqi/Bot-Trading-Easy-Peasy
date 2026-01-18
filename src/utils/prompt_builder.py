
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

def build_market_prompt(symbol, tech_data, sentiment_data, onchain_data, pattern_analysis=None, trade_scenarios=None):
    """
    Menyusun prompt untuk AI berdasarkan data teknikal, sentimen, dan on-chain.
    Struktur Baru: Multi-Timeframe (Macro -> Setup -> Execution).
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
    pivots = tech_data.get('pivots')
    pivot_str = "N/A"
    if pivots:
        pivot_str = f"P={format_price(pivots['P'])}, S1={format_price(pivots['S1'])}, R1={format_price(pivots['R1'])}"

    # --- B. EXECUTION DATA (Execution Timeframe / 15m) ---
    price = tech_data.get('price', 0)
    rsi = tech_data.get('rsi', 50)
    adx = tech_data.get('adx', 0)
    
    # EMA Analysis
    ema_fast = tech_data.get('ema_fast', 0)
    ema_slow = tech_data.get('ema_slow', 0)
    ema_pos = tech_data.get('price_vs_ema', 'UNKNOWN')
    trend_major = tech_data.get('trend_major', 'UNKNOWN')
    
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
    funding_rate = tech_data.get('funding_rate', 0)
    open_interest = tech_data.get('open_interest', 'N/A')
    
    # LSD (Long/Short Ratio)
    lsr_data = tech_data.get('lsr', {}) or {}
    lsr_val = lsr_data.get('longShortRatio', 'N/A')
    long_pct = float(lsr_data.get('longAccount', 0)) * 100 if lsr_data.get('longAccount') else 0
    short_pct = float(lsr_data.get('shortAccount', 0)) * 100 if lsr_data.get('shortAccount') else 0

    # --- C. SENTIMENT & ON-CHAIN ---
    fng_value = sentiment_data.get('fng_value', 50)
    fng_text = sentiment_data.get('fng_text', 'Neutral')
    news_headlines = sentiment_data.get('news', [])
    news_str = "\n".join([f"- {n}" for n in news_headlines]) if news_headlines else "No major news."
    
    whale_activity = onchain_data.get('whale_activity', [])
    whale_str = "\n".join([f"- {w}" for w in whale_activity]) if whale_activity else "No significant whale activity detected."
    inflow_status = onchain_data.get('stablecoin_inflow', 'Neutral')

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
    # (Obsolete Rule Removed)
    
    strat_str = "\n".join(strategies)

    # Dynamic BTC Warning
    btc_instruction = ""
    if btc_corr >= config.CORRELATION_THRESHOLD_BTC:
        btc_instruction = f"IMPORTANT: High BTC Correlation ({btc_corr:.2f}). Do NOT open positions against BTC Trend ({btc_trend})."

    # ==========================================
    # 2.5 TRADE SCENARIOS (Market vs Liquidity Hunt)
    # ==========================================
    execution_options_str = "N/A"
    if trade_scenarios:
        m = trade_scenarios.get('market', {})
        h = trade_scenarios.get('liquidity_hunt', {})
        
        execution_options_str = f"""
[EXECUTION OPTIONS]
OPTION A: AGGRESSIVE (MARKET)
- Entry: Market Price ({format_price(m.get('entry', 0))})
- Stop Loss: {format_price(m.get('sl', 0))}
- Take Profit: {format_price(m.get('tp', 0))}
- Risk:Reward: 1:{m.get('rr', 0)}

OPTION B: PASSIVE (LIQUIDITY HUNT)
- Entry: Limit Order at {format_price(h.get('entry', 0))} (Sweeping Standard SLs)
- Stop Loss: {format_price(h.get('sl', 0))}
- Take Profit: {format_price(h.get('tp', 0))}
- Risk:Reward: 1:{h.get('rr', 0)}
"""

    # ==========================================
    # 3. PROMPT CONSTRUCTION
    # ==========================================
    prompt = f"""
ROLE: {config.AI_SYSTEM_ROLE}

TASK: Analyze market data for {symbol} using the Multi-Timeframe logic below. Decide to BUY, SELL, or WAIT.

--------------------------------------------------
1. MACRO VIEW (TIMEFRAME: {config.TIMEFRAME_TREND})
> OBJECTIVE: Determine the Major Trend Bias.
- Global BTC Trend: {btc_trend} (EMA {config.BTC_EMA_PERIOD})
- BTC Correlation: {btc_corr:.2f}
- Market Structure: {market_struct} (Swing High/Low Analysis)
- Pivot Points: {pivot_str}
--------------------------------------------------

--------------------------------------------------
2. SETUP VALIDATION (TIMEFRAME: {config.TIMEFRAME_SETUP})
- Chart Pattern Analysis: {pattern_analysis if pattern_analysis else "Not Available"}
*INSTRUCTION: Use this pattern to confirm the Macro Bias.*
--------------------------------------------------

--------------------------------------------------
3. EXECUTION TRIGGER (TIMEFRAME: {config.TIMEFRAME_EXEC})
> OBJECTIVE: Pinpoint Entry Timing.
[MOMENTUM]
- RSI ({config.RSI_PERIOD}): {rsi:.2f}
- StochRSI: K={stoch_k:.2f}, D={stoch_d:.2f}
- ADX ({config.ADX_PERIOD}): {adx:.2f} (Trend Strength)

[TREND]
- Price: {format_price(price)}
- EMA Status: {ema_pos} (Fast: {format_price(ema_fast)} vs Slow: {format_price(ema_slow)})
- Major Trend (EMA {config.EMA_SLOW}): {trend_major}

[VOLATILITY & VOLUME]
- Bollinger Bands: Upper={format_price(bb_upper)}, Lower={format_price(bb_lower)}
- ATR: {atr:.5f}
- Volume: {volume} (Avg: {vol_ma})

[ORDER BOOK DEPTH]
- Depth (2%): {ob_imp}
- NOTE: Significant Imbalance (>20%) suggests potential Liquidity Hunt or Breakout.

[MARKET DATA]
- Funding Rate: {funding_rate:.6f}%
- Open Interest: {open_interest}
- Top Trader L/S Ratio: {lsr_val} (Longs: {long_pct:.1f}% / Shorts: {short_pct:.1f}%)
--------------------------------------------------

--------------------------------------------------
4. SENTIMENT & EXTERNAL FACTORS
- Fear & Greed Index: {fng_value} ({fng_text})
- Stablecoin Inflow: {inflow_status}
- Whale Activity:
{whale_str}
- Latest News:
{news_str}
--------------------------------------------------


{strat_str}

{execution_options_str}

FINAL INSTRUCTIONS:
1. CHECK MACRO BIAS: Is the {config.TIMEFRAME_TREND} Structure & BTC Trend supportive?
   {btc_instruction}
2. VERIFY SETUP: Does the {config.TIMEFRAME_SETUP} Pattern align with the Bias?
3. CHECK TRIGGER: Are {config.TIMEFRAME_EXEC} Momentum indicators (RSI/Stoch/ADX) giving a clear signal?
4. SELECT STRATEGY & EXECUTION: 
   - Choose the Strategy that aligns with the Bias.
   - Select OPTION A (Aggressive) for clear momentum, or OPTION B (Passive) if a Stop Run/Liquidity Sweep is detected.
5. DECISION: Return WAIT if signals are conflicting.

OUTPUT FORMAT (JSON ONLY):
{{
  "analysis": {{
    "macro_bias": "BULLISH/BEARISH/NEUTRAL",
    "pattern_signal": "Description of pattern implication",
    "execution_trigger": "Valid/Invalid based on indicators"
  }},
  "selected_strategy": "NAME OF STRATEGY",
  "execution_mode": "MARKET" | "LIQUIDITY_HUNT",
  "decision": "BUY" | "SELL" | "WAIT",
  "reason": "Explain your logic in INDONESIAN language, referencing specific macro and micro factors.",
  "confidence": 0-100,
  "risk_level": "LOW" | "MEDIUM" | "HIGH"
}}
"""
    return prompt
