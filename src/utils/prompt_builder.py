
import config

def build_market_prompt(symbol, tech_data, sentiment_data, onchain_data):
    """
    Menyusun prompt untuk AI berdasarkan data teknikal, sentimen, dan on-chain.
    """
    
    # 0. VALIDATION: Critical Data Check
    if not tech_data or tech_data.get('price', 0) == 0:
        return None # Abort signal generation if data is invalid
    
    # 1. Parsing Data Teknikal
    price = tech_data.get('price', 0)
    rsi = tech_data.get('rsi', 50)
    adx = tech_data.get('adx', 0)
    ema_pos = tech_data.get('price_vs_ema', 'UNKNOWN')
    btc_trend = tech_data.get('btc_trend', 'NEUTRAL')
    btc_corr = tech_data.get('btc_correlation', 0)
    
    # Additional Indicators
    ema_fast = tech_data.get('ema_fast', 0)
    ema_slow = tech_data.get('ema_slow', 0)
    trend_major = tech_data.get('trend_major', 'UNKNOWN')
    vol_ma = tech_data.get('vol_ma', 0)
    volume = tech_data.get('volume', 0)
    stoch_k = tech_data.get('stoch_k', 50)
    stoch_d = tech_data.get('stoch_d', 50)
    bb_upper = tech_data.get('bb_upper', 0)
    bb_lower = tech_data.get('bb_lower', 0)
    atr = tech_data.get('atr', 0)
    
    # Pivot Points Support/Resistance
    pivots = tech_data.get('pivots')
    pivot_str = "N/A"
    if pivots:
        pivot_str = f"P={pivots['P']:.2f}, S1={pivots['S1']:.2f}, S2={pivots['S2']:.2f}, R1={pivots['R1']:.2f}, R2={pivots['R2']:.2f}"
    
    # Strategy Mode from Main
    strategy_mode = tech_data.get('strategy_mode', 'STANDARD')

    # 2. Parsing Sentiment
    fng_value = sentiment_data.get('fng_value', 50)
    fng_text = sentiment_data.get('fng_text', 'Neutral')
    news_headlines = sentiment_data.get('news', [])
    news_str = "\n".join([f"- {n}" for n in news_headlines]) if news_headlines else "No major news."

    # 3. Parsing On-Chain
    funding_rate = tech_data.get('funding_rate', 0) 
    whale_activity = onchain_data.get('whale_activity', [])
    whale_str = "\n".join([f"- {w}" for w in whale_activity]) if whale_activity else "No significant whale activity detected."
    inflow_status = onchain_data.get('stablecoin_inflow', 'Neutral')

    # 3.5 Strategy Context
    strategies = []
    strategies.append("AVAILABLE STRATEGIES TO CHOOSE FROM:")
    
    # Iterate all strategies from config
    for name, desc in config.AVAILABLE_STRATEGIES.items():
        strategies.append(f"[{name}]: {desc}")
    
    strategies.append("")
    strategies.append("ADDITIONAL CONTEXT:")
    if config.USE_LIQUIDITY_HUNT:
        strategies.append(f"- 🔫 LIQUIDITY HUNT ACTIVE: Entry will be via LIMIT ORDER at Price +/- {config.ATR_MULTIPLIER_SL} ATR.")
        strategies.append("  (Ensure the setup allows for a wick/scam wick entry).")
    
    strat_str = "\n".join([f"{s}" for s in strategies])

    # [NEW] Dynamic BTC Instruction
    btc_instruction = ""
    if btc_corr >= config.CORRELATION_THRESHOLD_BTC:
        btc_instruction = f"WARNING: HIGH BTC CORRELATION ({btc_corr:.2f}). DO NOT TRADE AGAINST BTC TREND ({btc_trend})."

    # 4. Construct Prompt
    prompt = f"""
ROLE: {config.AI_SYSTEM_ROLE}

TASK: Analyze market data for {symbol}. SELECT THE BEST STRATEGY from the available list that matches current conditions (Trend vs Sideways) and decide if we should OPEN a position or WAIT.

DATA CONTEXT:
----------------------------------------
A. TECHNICAL INDICATORS ({config.TIMEFRAME_TREND} / {config.TIMEFRAME_EXEC})
- Price: {price}
- Trend vs BTC: {btc_trend} (King Filter)
- BTC Correlation: {btc_corr:.2f}
- EMA Trend: {ema_pos} (Fast), {trend_major} (Slow/Major)
- RSI ({config.RSI_PERIOD}): {rsi:.2f}
- ADX ({config.ADX_PERIOD}): {adx:.2f} [Note: ADX > 25 = Strong Trend, ADX < 20 = Weak Trend/Sideways]
- StochRSI ({config.STOCHRSI_K},{config.STOCHRSI_D}): K={stoch_k:.2f}, D={stoch_d:.2f}
- Bollinger Bands: Up={bb_upper:.2f}, Low={bb_lower:.2f}
- Pivot Points ({config.TIMEFRAME_TREND}): {pivot_str}
- Volume: {volume} (Avg: {vol_ma})
- ATR: {atr:.4f}
- Funding Rate: {funding_rate:.6f}% 
- Open Interest: {tech_data.get('open_interest', 'N/A')}

B. MARKET SENTIMENT
- Fear & Greed Index: {fng_value} ({fng_text})
- Latest Headlines:
{news_str}

C. ON-CHAIN / WHALE DATA
- Stablecoin Inflow: {inflow_status}
- Recent Large Transactions (Whales):
{whale_str}

D. STRATEGY SELECTION
{strat_str}
----------------------------------------

INSTRUCTIONS:
1. MARKET STRUCTURE: Check ADX for Trend Strength. High ADX -> Trend Strategies. Low ADX -> Sideways Strategies.
   {btc_instruction}
2. SELECT STRATEGY: Choose ONE strategy from the list that perfectly fits the current market structure.
3. CONFLUENCE: Ensure Technicals + Sentiment align with the chosen strategy.
4. DECISION: If no strategy is valid or signals are mixed, return WAIT.

OUTPUT FORMAT (JSON ONLY):
{{
  "analysis": {{
    "bullish_factors": ["factor 1", "factor 2"],
    "bearish_factors": ["factor 1", "factor 2"]
  }},
  "selected_strategy": "NAME OF STRATEGY (e.g. STRATEGY A)",
  "decision": "BUY" | "SELL" | "WAIT",
  "reason": "Synthesis of analysis in INDONESIAN LANGUAGE...",
  "confidence": 0-100,
  "risk_level": "LOW" | "MEDIUM" | "HIGH"
}}
"""
    return prompt
