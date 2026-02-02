import config
import pandas as pd
import numpy as np

class AISimulator:
    """
    Simulates the AI's decision making process based on deterministic logic
    derived from the prompt engineering rules.
    """

    def __init__(self):
        self.strategies = config.AVAILABLE_STRATEGIES

    def analyze_market_simulation(self, tech_data: dict, sentiment_data: dict) -> dict:
        """
        Analyzes market data and returns a trade decision mimicking the AI.

        Args:
            tech_data: Dictionary containing technical indicators
            sentiment_data: Dictionary containing sentiment info (F&G)

        Returns:
            Dictionary with keys: decision, confidence, reason, execution_mode, strategy
        """

        # 1. Unpack Data
        symbol = tech_data.get('symbol', 'UNKNOWN')
        price = tech_data.get('price', 0)
        rsi = tech_data.get('rsi', 50)
        adx = tech_data.get('adx', 0)
        stoch_k = tech_data.get('stoch_k', 50)

        ema_fast = tech_data.get('ema_fast', 0)
        ema_slow = tech_data.get('ema_slow', 0)

        bb_upper = tech_data.get('bb_upper', 0)
        bb_lower = tech_data.get('bb_lower', 0)

        btc_trend = tech_data.get('btc_trend', 'NEUTRAL')
        btc_corr = tech_data.get('btc_correlation', 0)

        fng_value = sentiment_data.get('fng_value', 50)

        # 2. Determine Allowed Direction (Macro Filter)
        allowed_direction = "BOTH"

        # Check BTC Correlation Logic (mimic config rules)
        # Assuming high correlation for simulation simplicity if not provided
        is_correlated = btc_corr >= config.CORRELATION_THRESHOLD_BTC

        if config.USE_BTC_CORRELATION and is_correlated:
            if btc_trend == "BULLISH":
                allowed_direction = "LONG_ONLY"
            elif btc_trend == "BEARISH":
                allowed_direction = "SHORT_ONLY"

        # 3. Strategy Evaluation
        decision = "WAIT"
        confidence = 0
        reason = []
        strategy_name = "NONE"
        exec_mode = "LIQUIDITY_HUNT" if not config.ENABLE_MARKET_ORDERS else "MARKET"

        # --- STRATEGY A: TREND PULLBACK (Trend Trap) ---
        # Rule: ADX > 25 (Strong Trend)
        if adx > config.TREND_TRAP_ADX_MIN:

            # LONG SETUP
            if allowed_direction in ["LONG_ONLY", "BOTH"]:
                # Logic: Price dipped below EMA Fast but above BB Lower (Pullback)
                is_pullback = (price < ema_fast) and (price > bb_lower)
                # RSI Filter
                rsi_valid = (rsi >= config.TREND_TRAP_RSI_LONG_MIN) and (rsi <= config.TREND_TRAP_RSI_LONG_MAX)
                # Trend Valid (Fast > Slow)
                trend_valid = ema_fast > ema_slow

                if is_pullback and rsi_valid and trend_valid:
                    decision = "BUY"
                    confidence = 85
                    strategy_name = "TREND_PULLBACK"
                    reason.append("Strong Uptrend (ADX>25) with healthy pullback.")

            # SHORT SETUP
            if allowed_direction in ["SHORT_ONLY", "BOTH"] and decision == "WAIT":
                # Logic: Price rallied above EMA Fast but below BB Upper (Pullback)
                is_pullback = (price > ema_fast) and (price < bb_upper)
                # RSI Filter
                rsi_valid = (rsi >= config.TREND_TRAP_RSI_SHORT_MIN) and (rsi <= config.TREND_TRAP_RSI_SHORT_MAX)
                # Trend Valid (Fast < Slow)
                trend_valid = ema_fast < ema_slow

                if is_pullback and rsi_valid and trend_valid:
                    decision = "SELL"
                    confidence = 85
                    strategy_name = "TREND_PULLBACK"
                    reason.append("Strong Downtrend (ADX>25) with healthy pullback.")

        # --- STRATEGY B: SIDEWAYS SCALP (BB Bounce) ---
        # Rule: ADX < 20 (Weak Trend/Choppy)
        elif adx < config.SIDEWAYS_ADX_MAX:

            # LONG SETUP (Bounce from Bottom)
            if allowed_direction in ["LONG_ONLY", "BOTH"]:
                if price <= bb_lower and stoch_k < 20:
                    decision = "BUY"
                    confidence = 75
                    strategy_name = "BB_BOUNCE"
                    reason.append("Sideways Market (ADX<20), Price at Lower BB.")

            # SHORT SETUP (Reject from Top)
            if allowed_direction in ["SHORT_ONLY", "BOTH"] and decision == "WAIT":
                if price >= bb_upper and stoch_k > 80:
                    decision = "SELL"
                    confidence = 75
                    strategy_name = "BB_BOUNCE"
                    reason.append("Sideways Market (ADX<20), Price at Upper BB.")

        # 4. Sentiment Filter (Risk Adjustment)
        # If Sentiment is EXTREME, reduce confidence or flip decision
        if decision == "BUY" and fng_value < 20:
            # Extreme Fear: Buying might be catching a falling knife
            confidence -= 10
            reason.append("Caution: Extreme Fear market.")

        elif decision == "SELL" and fng_value > 80:
            # Extreme Greed: Selling might be fighting FOMO
            confidence -= 10
            reason.append("Caution: Extreme Greed market.")

        # 5. Final Threshold Check
        if confidence < config.AI_CONFIDENCE_THRESHOLD:
            decision = "WAIT"
            reason.append(f"Confidence {confidence}% too low (Min {config.AI_CONFIDENCE_THRESHOLD}%).")

        return {
            "decision": decision,
            "confidence": confidence,
            "reason": "; ".join(reason),
            "selected_strategy": strategy_name,
            "execution_mode": exec_mode
        }
