

import sys
import os
# Fix Module Search Path (Add Project Root)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

import time
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele, kirim_tele_sync, parse_timeframe_to_seconds
from src.utils.prompt_builder import build_market_prompt

# MODULE IMPORTS
from src.modules.market_data import MarketDataManager
from src.modules.sentiment import SentimentAnalyzer
from src.modules.onchain import OnChainAnalyzer
from src.modules.ai_brain import AIBrain
from src.modules.executor import OrderExecutor

# GLOBAL INSTANCES
market_data = None
sentiment = None
onchain = None
ai_brain = None
executor = None

async def safety_monitor_loop():
    """
    Background loop to check for:
    1. Pending orders (Securing positions)
    2. Tracker cleanup
    """
    logger.info("🛡️ Safety Monitor Started")
    while True:
        try:
            # Sync positions from Binance
            count = await executor.sync_positions()
            
            # Check Tracker vs Real Positions
            for base_sym, pos in executor.position_cache.items():
                symbol = pos['symbol']
                # If position exists but not in tracker OR status is PENDING
                tracker = executor.safety_orders_tracker.get(symbol, {})
                status = tracker.get('status', 'NONE')
                
                if status in ['NONE', 'PENDING']:
                    logger.info(f"🛡️ Found Unsecured Position: {symbol}. Installing Safety...")
                    success = await executor.install_safety_orders(symbol, pos)
                    if success:
                        executor.safety_orders_tracker[symbol] = {
                            "status": "SECURED",
                            "last_check": time.time()
                        }
                        executor.save_tracker()
            
            # Sleep 
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Safety Loop Error: {e}")
            await asyncio.sleep(5)

async def main():
    global market_data, sentiment, onchain, ai_brain, executor
    
    # Track AI Query Timestamp
    last_ai_query = {}
    timeframe_exec_seconds = parse_timeframe_to_seconds(config.TIMEFRAME_EXEC)

    # 1. INITIALIZATION
    exchange = ccxt.binance({
        'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
        'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True, 
            'recvWindow': 10000
        }
    })
    if config.PAKAI_DEMO: exchange.enable_demo_trading(True)

    await kirim_tele("🤖 <b>BOT UPGRADED & STARTED</b>\nAI-Hybrid System Online.", alert=True)

    # 2. SETUP MODULES
    market_data = MarketDataManager(exchange)
    sentiment = SentimentAnalyzer()
    onchain = OnChainAnalyzer()
    ai_brain = AIBrain()
    executor = OrderExecutor(exchange)

    # 3. PRELOAD DATA
    await market_data.initialize_data()
    sentiment.update_all() # Initial Fetch Headline & F&G
    
    # 4. START BACKGROUND TASKS
    # WebSocket Callback Wrappers
    async def account_update_cb(payload):
        # Trigger sync when account balance/position changes
        await executor.sync_positions()

    async def order_update_cb(payload):
        # Handle filled orders (e.g., detect Whale execution if needed, or simply log)
        o = payload['o']
        sym = o['s'].replace('USDT', '/USDT')
        status = o['X']
        if status == 'FILLED':
            rp = float(o.get('rp', 0))
            logger.info(f"⚡ Order Filled: {sym} {o['S']} @ {o['ap']} | RP: {rp}")
            
            # [NEW] COOLDOWN LOGIC BASED ON RESULT (Profit/Loss)
            # Only trigger cooldown if this fill actually closes a position (Realized Profit != 0)
            if rp != 0:
                if rp > 0:
                    executor.set_cooldown(sym, config.COOLDOWN_IF_PROFIT)
                    msg_res = "✅ PROFIT"
                else:
                    executor.set_cooldown(sym, config.COOLDOWN_IF_LOSS)
                    msg_res = "❌ LOSS"
                
                await kirim_tele(f"{msg_res} Trade Closed: {sym}\nRP: ${rp:.2f}\nCooldown activated.")

            # Trigger safety check immediately
            await executor.sync_positions()

    asyncio.create_task(market_data.start_stream(account_update_cb, order_update_cb))
    asyncio.create_task(safety_monitor_loop())

    logger.info("🚀 MAIN LOOP RUNNING...")

    # 5. MAIN TRADING LOOP
    ticker_idx = 0
    while True:
        try:
            # Round Robin Scan (One coin per loop to save API/AI limit)
            coin_cfg = config.DAFTAR_KOIN[ticker_idx]
            symbol = coin_cfg['symbol']
            
            ticker_idx = (ticker_idx + 1) % len(config.DAFTAR_KOIN)
            
            # --- STEP A: COLLECT DATA ---
            tech_data = market_data.get_technical_data(symbol)
            if not tech_data:
                await asyncio.sleep(2)
                continue

            sentiment_data = sentiment.get_latest()
            onchain_data = onchain.get_latest()

            # --- STEP B: CHECK EXCLUSION (Cooldown / Existing Position) ---
            # 1. Active Position Check
            base_sym = symbol.split('/')[0]
            if base_sym in executor.position_cache:
                # logger.info(f"Skipping {symbol} (Active Position)")
                await asyncio.sleep(1)
                continue
            
            # 2. Cooldown Check
            if executor.is_under_cooldown(symbol):
                # Logger handled inside is_under_cooldown but we can skip silently here to reduce spam
                await asyncio.sleep(1)
                continue

            # [NEW] Check Category Limit
            category = coin_cfg.get('category', 'UNKNOWN')
            if config.MAX_POSITIONS_PER_CATEGORY > 0:
                current_cat_count = executor.get_open_positions_count_by_category(category)
                if current_cat_count >= config.MAX_POSITIONS_PER_CATEGORY:
                   # logger.info(f"Skip {symbol}: Category {category} Full ({current_cat_count}/{config.MAX_POSITIONS_PER_CATEGORY})")
                   await asyncio.sleep(1)
                   continue
            
            # --- STEP C: TRADITIONAL FILTER FIRST ---
            # Don't waste AI tokens on garbage setups
            # Rule: Harusnya ada sinyal teknikal dasar dulu (e.g. RSI extreme atau Trend following)
            is_interesting = False
            
            # Filter 1: Trend Alignment (King Filter) & Correlation Check
            btc_corr = await market_data.get_btc_correlation(symbol)
            
            if btc_corr >= config.CORRELATION_THRESHOLD_BTC:
                # High Correlation: Must follow BTC
                if tech_data['btc_trend'] == "BULLISH" and tech_data['price_vs_ema'] == "Above":
                     is_interesting = True
                elif tech_data['btc_trend'] == "BEARISH" and tech_data['price_vs_ema'] == "Below":
                     is_interesting = True
                else:
                    # logger.info(f"msg: {symbol} Skipping. High Corr ({btc_corr:.2f}) but Trend Mismatch (BTC {tech_data['btc_trend']} vs {tech_data['price_vs_ema']})")
                    pass
            else:
                # Low Correlation: Independent Movement Allowed
                # We assume if Independent, we allow AI to see it regardless of BTC
                # logger.info(f"✨ {symbol} Low Corr ({btc_corr:.2f}). Independent Trend Allowed.")
                is_interesting = True
            
            # Filter 2: RSI Extremes (Reversal)
            if tech_data['rsi'] < 30 or tech_data['rsi'] > 70:
                is_interesting = True
            
            if not is_interesting:
                # print(f"💤 {symbol} Boring. Skip AI.")
                await asyncio.sleep(2)
                continue

            # --- STEP C.5: STRATEGY SELECTION & FILTER UPDATES ---
            adx_val = tech_data.get('adx', 0)
            strategy_mode = 'STANDARD'
            
            if config.USE_TREND_TRAP_STRATEGY and adx_val >= config.TREND_TRAP_ADX_MIN:
                strategy_mode = 'TREND_PULLBACK'
            elif config.USE_SIDEWAYS_SCALP and adx_val <= config.SIDEWAYS_ADX_MAX:
                strategy_mode = 'BB_BOUNCE'
            
            # Update Context for AI
            tech_data['strategy_mode'] = strategy_mode

            # Filter Logic Update based on Strategy
            # ... (Existing filter logic modified to respect strategy) ...
            
            # (Untuk simplifikasi, kita gabung ke existing logic tapi tambah logging)
            logger.info(f"📊 Strategy Mode: {strategy_mode} (ADX: {adx_val:.2f})")

            # --- STEP D: AI ANALYSIS ---
            # [NEW] Frequency Check
            last_query_time = last_ai_query.get(symbol, 0)
            time_elapsed = time.time() - last_query_time
            
            if time_elapsed < timeframe_exec_seconds:
                # Skip AI to save cost/spam
                # logger.info(f"⏳ {symbol} AI Skip (Wait {int(timeframe_exec_seconds - time_elapsed)}s)")
                await asyncio.sleep(1)
                continue

            # ... (Existing Code)
            logger.info(f"🤖 Asking AI: {symbol} (Corr: {btc_corr:.2f}) ...")
            prompt = build_market_prompt(symbol, tech_data, sentiment_data, onchain_data)
            
            ai_decision = await ai_brain.analyze_market(prompt)
            
            # Update Timestamp only if analyzed
            last_ai_query[symbol] = time.time()
            
            decision = ai_decision.get('decision', 'WAIT').upper()
            confidence = ai_decision.get('confidence', 0)
            reason = ai_decision.get('reason', '')

            # --- STEP E: EXECUTION ---
            if decision in ['BUY', 'SELL', 'LONG', 'SHORT']:
                # Mapping AI Output
                side = 'buy' if decision in ['BUY', 'LONG'] else 'sell'
                
                if confidence >= config.AI_CONFIDENCE_THRESHOLD:
                    # Execute!
                    lev = coin_cfg.get('leverage', config.DEFAULT_LEVERAGE)
                    
                    # [NEW] Dynamic Sizing
                    dynamic_amt = await executor.calculate_dynamic_amount_usdt(symbol, lev)
                    if dynamic_amt:
                        amt = dynamic_amt
                        logger.info(f"💰 Dynamic Size: ${amt:.2f} (Risk {config.RISK_PERCENT_PER_TRADE}%)")
                    else:
                        amt = coin_cfg.get('amount', config.DEFAULT_AMOUNT_USDT)
                    
                    msg = (f"🧠 <b>AI SIGNAL MATCHED</b>\n"
                           f"Coin: {symbol}\nDec: {decision} ({confidence}%)\n"
                           f"Mode: {strategy_mode}\n"
                           f"Reason: {reason}")
                    await kirim_tele(msg)
                    
                    # [NEW] LIQUIDITY HUNT CALCULATION
                    order_type = 'market'
                    entry_price = tech_data['price']
                    
                    if config.USE_LIQUIDITY_HUNT:
                        atr_val = tech_data.get('atr', 0)
                        if atr_val > 0:
                            order_type = 'limit'
                            # Jarak entry = 1.0 * ATRMultiplierSL (Default 1.0 di config)
                            offset = atr_val * config.ATR_MULTIPLIER_SL
                            
                            if side == 'buy':
                                entry_price = tech_data['price'] - offset
                            else:
                                entry_price = tech_data['price'] + offset
                                
                            logger.info(f"🔫 Liquidity Hunt Activated. Limit Order @ {entry_price:.4f} (Last: {tech_data['price']}, ATR: {atr_val})")
                    
                    await executor.execute_entry(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        price=entry_price,
                        amount_usdt=amt,
                        leverage=lev,
                        strategy_tag=f"AI_{strategy_mode}",
                        atr_value=tech_data.get('atr', 0) # Pass ATR for Safety Orders
                    )
                else:
                    logger.info(f"🛑 AI Vote Low Confidence: {confidence}% (Need {config.AI_CONFIDENCE_THRESHOLD}%)")

            # Rate Limit Protection
            await asyncio.sleep(config.ERROR_SLEEP_DELAY) 

        except Exception as e:
            logger.error(f"Main Loop Error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot Stopped Manually.")
        kirim_tele_sync("🛑 Bot Stopped Manually")
    except Exception as e:
        print(f"💀 Fatal Crash: {e}")
        kirim_tele_sync(f"💀 Bot Crash: {e}")