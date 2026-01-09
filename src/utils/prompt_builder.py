
import config

def build_market_prompt(symbol, tech_data, sentiment_data, onchain_data):
    """
    Menyusun prompt untuk AI berdasarkan data teknikal, sentimen, dan on-chain.
    """
    
    # 1. Parsing Data Teknikal
    price = tech_data.get('price', 0)
    rsi = tech_data.get('rsi', 50)
    adx = tech_data.get('adx', 0)
    ema_pos = tech_data.get('price_vs_ema', 'UNKNOWN')
    btc_trend = tech_data.get('btc_trend', 'NEUTRAL')
    
    # [NEW] Additional Indicators
    ema_slow = tech_data.get('ema_slow', 0)
    trend_major = tech_data.get('trend_major', 'UNKNOWN')
    vol_ma = tech_data.get('vol_ma', 0)
    volume = tech_data.get('volume', 0)
    stoch_k = tech_data.get('stoch_k', 50)
    stoch_d = tech_data.get('stoch_d', 50)
    bb_upper = tech_data.get('bb_upper', 0)
    bb_lower = tech_data.get('bb_lower', 0)
    atr = tech_data.get('atr', 0)
    
    # Strategy Mode from Main
    strategy_mode = tech_data.get('strategy_mode', 'STANDARD')

    # 2. Parsing Sentiment
    fng_value = sentiment_data.get('fng_value', 50)
    fng_text = sentiment_data.get('fng_text', 'Neutral')
    news_headlines = sentiment_data.get('news', [])
    news_str = "\n".join([f"- {n}" for n in news_headlines]) if news_headlines else "No major news."

    # 3. Parsing On-Chain
    funding_rate = tech_data.get('funding_rate', 0) 
    open_interest = tech_data.get('open_interest', 0)
    whale_activity = onchain_data.get('whale_activity', [])
    whale_str = "\n".join([f"- {w}" for w in whale_activity]) if whale_activity else "No significant whale activity detected."
    inflow_status = onchain_data.get('stablecoin_inflow', 'Neutral')

    # 3.5 Strategy Context
    strategies = []
    
    # Priority Strategy based on Mode
    if strategy_mode == 'TREND_PULLBACK':
        strategies.append(f"🔥 PRIMARY STRATEGY: TREND TRAP / PULLBACK. Trend is STRONG (ADX {adx:.1f}). Look for retests of EMA or Support levels.")
        strategies.append(f"   Condition: StochRSI Oversold in Bull Trend, or Overbought in Bear Trend.")
    elif strategy_mode == 'BB_BOUNCE':
        strategies.append(f"🔥 PRIMARY STRATEGY: BB BOUNCE / SCALP. Market is SIDEWAYS (ADX {adx:.1f}).")
        strategies.append(f"   Condition: Buy at BB Lower, Sell at BB Upper. Avoid breakout setups.")
    else:
        strategies.append("STANDARD MODE: Follow Trend if aligned with BTC, or Reversal if Extremes.")

    if config.USE_LIQUIDITY_HUNT:
        strategies.append(f"🔫 LIQUIDITY HUNT ACTIVE: Entry will be via LIMIT ORDER at Price +/- {config.ATR_MULTIPLIER_SL} ATR.")
        strategies.append("   Ensure the setup allows for a wick/scam wick entry.")
    
    strat_str = "\n".join([f"- {s}" for s in strategies])

    # 4. Construct Prompt
    prompt = f"""
ROLE: You are an expert Crypto Trading AI with a focus on Risk Management and Trend Following.

TASK: Analyze the current market data for {symbol} and decide whether to OPEN a position or WAIT.

DATA CONTEXT:
----------------------------------------
A. TECHNICAL INDICATORS (H1 / 5m)
- Price: {price}
- Trend vs BTC: {btc_trend} (King Filter)
- EMA Trend: {ema_pos} (Fast), {trend_major} (Slow/Major)
- RSI (14): {rsi:.2f}
- ADX (14): {adx:.2f}
- StochRSI (3,3): K={stoch_k:.2f}, D={stoch_d:.2f}
- Bollinger Bands: Up={bb_upper:.2f}, Low={bb_lower:.2f}
- Volume: {volume} (Avg: {vol_ma})
- ATR: {atr:.4f}
- Funding Rate: {funding_rate:.6f}% 

B. MARKET SENTIMENT
- Fear & Greed Index: {fng_value} ({fng_text})
- Latest Headlines:
{news_str}

C. ON-CHAIN / WHALE DATA
- Stablecoin Inflow: {inflow_status}
- Recent Large Transactions (Whales):
{whale_str}

D. ACTIVE STRATEGIES (PRIORITIZE THESE SETUPS)
{strat_str}
----------------------------------------

INSTRUCTIONS:
1. Analyze the correlation between Technicals and Sentiment.
2. CHECK if any "ACTIVE STRATEGY" criteria are met. If yes, confidence should be higher.
3. Look for "Confluence" (e.g., RSI Oversold + Fear Market + Whale Buying).
4. If signals are mixed, prioritize Capital Preservation (WAIT).
5. Provide a Confidence Score (0-100%).

OUTPUT FORMAT (JSON ONLY):
{{
  "decision": "BUY" | "SELL" | "WAIT",
  "reason": "Short explanation (Mention if Strategy Condition is met)...",
  "confidence": 75,
  "risk_level": "LOW" | "MEDIUM" | "HIGH"
}}
"""
    return prompt
