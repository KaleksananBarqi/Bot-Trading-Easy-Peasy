

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
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)
            
        except Exception as e:
            logger.error(f"Safety Loop Error: {e}")
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)

async def main():
    global market_data, sentiment, onchain, ai_brain, executor
    
    # Track AI Query Timestamp
    last_ai_query = {}
    timeframe_exec_seconds = parse_timeframe_to_seconds(config.TIMEFRAME_EXEC)
    timeframe_trend_seconds = parse_timeframe_to_seconds(config.TIMEFRAME_TREND)
    last_sentiment_update_time = time.time()

    # 1. INITIALIZATION
    exchange = ccxt.binance({
        'apiKey': config.API_KEY_DEMO if config.PAKAI_DEMO else config.API_KEY_LIVE,
        'secret': config.SECRET_KEY_DEMO if config.PAKAI_DEMO else config.SECRET_KEY_LIVE,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True, 
            'recvWindow': config.API_RECV_WINDOW
        }
    })
    if config.PAKAI_DEMO: exchange.enable_demo_trading(True)

    await kirim_tele("🤖 <b>BOT TRADING STARTED</b>\nAI-Hybrid System Online.", alert=True)

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
                else:
                    executor.set_cooldown(sym, config.COOLDOWN_IF_LOSS)
                
                # Format Pesan
                pnl = rp
                order_info = o
                symbol = sym
                price = float(o.get('ap', 0))
                order_type = o.get('o', 'UNKNOWN')
                
                emoji = "💰" if pnl > 0 else "🛑"
                title = "TAKE PROFIT HIT" if pnl > 0 else "STOP LOSS HIT"
                pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
                
                # Hitung size yang diclose
                qty_closed = float(order_info.get('q', 0))
                size_closed_usdt = qty_closed * price
                
                msg = (
                        f"{emoji} <b>{title}</b>\n"
                        f"✨ <b>{symbol}</b>\n"
                        f"🏷️ Type: {order_type}\n"
                        f"📏 <b>Size:</b> ${size_closed_usdt:.2f}\n" 
                        f"💵 Price: {price}\n"
                        f"💸 PnL: <b>{pnl_str}</b>"
                    )
                await kirim_tele(msg)

            # Trigger safety check immediately
            await executor.sync_positions()

    def whale_handler(symbol, amount, side):
        # Callback from Market Data (AggTrade)
        onchain.detect_whale(symbol, amount, side)

    asyncio.create_task(market_data.start_stream(account_update_cb, order_update_cb, whale_handler))
    asyncio.create_task(safety_monitor_loop())

    logger.info("🚀 MAIN LOOP RUNNING...")

    # 5. MAIN TRADING LOOP
    ticker_idx = 0
    while True:
        try:
            # Round Robin Scan (One coin per loop to save API/AI limit)
            
            # --- STEP 0: PERIODIC SENTIMENT REFRESH ---
             # Cek apakah sudah waktunya update berita & F&G (misal setiap 1 jam)
            if time.time() - last_sentiment_update_time >= timeframe_trend_seconds:
                logger.info("🔄 Refreshing Sentiment & On-Chain Data...")
                try:
                    # Jalankan di background task agar tidak memblokir main loop (Fire & Forget)
                    asyncio.create_task(asyncio.to_thread(sentiment.update_all))
                    asyncio.create_task(asyncio.to_thread(onchain.fetch_stablecoin_inflows))
                    
                    last_sentiment_update_time = time.time()
                    logger.info("✅ Sentiment & On-Chain Data Refreshed.")
                except Exception as e:
                    logger.error(f"❌ Failed to refresh data: {e}")

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
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue
            
            # 2. Cooldown Check
            if executor.is_under_cooldown(symbol):
                # Logger handled inside is_under_cooldown but we can skip silently here to reduce spam
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue

            # [NEW] Check Category Limit
            category = coin_cfg.get('category', 'UNKNOWN')
            if config.MAX_POSITIONS_PER_CATEGORY > 0:
                current_cat_count = executor.get_open_positions_count_by_category(category)
                if current_cat_count >= config.MAX_POSITIONS_PER_CATEGORY:
                   # logger.info(f"Skip {symbol}: Category {category} Full ({current_cat_count}/{config.MAX_POSITIONS_PER_CATEGORY})")
                   await asyncio.sleep(config.LOOP_SLEEP_DELAY)
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
            #logger.info(f"📊 Strategy Mode: {strategy_mode} (ADX: {adx_val:.2f})")

            # --- STEP D: AI ANALYSIS ---
            # [NEW] Frequency Check
            last_query_time = last_ai_query.get(symbol, 0)
            time_elapsed = time.time() - last_query_time
            
            if time_elapsed < timeframe_exec_seconds:
                # Skip AI to save cost/spam
                logger.info(f"⏳ {symbol} AI Skip (Wait {int(timeframe_exec_seconds - time_elapsed)}s)")
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue

            # ... (Existing Code)
            logger.info(f"🤖 Asking AI: {symbol} (Corr: {btc_corr:.2f}) ...")
            tech_data['btc_correlation'] = btc_corr
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
                    
                    # --- CALCULATION & PREPARATION ---
                    order_type = 'market'
                    entry_price = tech_data['price']
                    atr_val = tech_data.get('atr', 0)
                    
                    # Liquidity Hunt Logic
                    if config.USE_LIQUIDITY_HUNT and atr_val > 0:
                        order_type = 'limit'
                        offset = atr_val * config.ATR_MULTIPLIER_SL
                        if side == 'buy':
                            entry_price = tech_data['price'] - offset
                        else:
                            entry_price = tech_data['price'] + offset
                        logger.info(f"🔫 Liquidity Hunt Activated. Limit Order @ {entry_price:.4f} (Last: {tech_data['price']}, ATR: {atr_val})")

                    # Calculate TP/SL for Display
                    sl_price = 0
                    tp_price = 0
                    rr_ratio = 0.0

                    if atr_val > 0:
                         dist_sl = atr_val * config.TRAP_SAFETY_SL
                         dist_tp = atr_val * config.ATR_MULTIPLIER_TP1
                         rr_ratio = dist_tp / dist_sl if dist_sl > 0 else 0
                         
                         if side == 'buy':
                             sl_price = entry_price - dist_sl
                             tp_price = entry_price + dist_tp
                         else:
                             sl_price = entry_price + dist_sl
                             tp_price = entry_price - dist_tp
                    else:
                         sl_percent = 0.01; tp_percent = 0.02
                         rr_ratio = tp_percent / sl_percent
                         if side == 'buy':
                            sl_price = entry_price * (1 - sl_percent)
                            tp_price = entry_price * (1 + tp_percent)
                         else:
                            sl_price = entry_price * (1 + sl_percent)
                            tp_price = entry_price * (1 - tp_percent)

                    margin_usdt = amt
                    position_size_usdt = amt * lev
                    direction_icon = "🟢" if side == 'buy' else "🔴"
                    
                    btc_trend_icon = "🟢" if tech_data['btc_trend'] == "BULLISH" else "🔴"
                    btc_corr_icon = "🔒" if btc_corr >= config.CORRELATION_THRESHOLD_BTC else "🔓"

                    msg = (f"🧠 <b>AI SIGNAL MATCHED</b>\n"
                           f"Coin: {symbol}\n"
                           f"Signal: {direction_icon} {decision} ({confidence}%)\n"
                           f"Timeframe: {config.TIMEFRAME_EXEC}\n"
                           f"BTC Trend: {btc_trend_icon} {tech_data['btc_trend']}\n"
                           f"BTC Correlation: {btc_corr_icon} {btc_corr:.2f}\n"
                           f"Mode: {strategy_mode}\n\n"
                           f"🛒 <b>Order Details:</b>\n"
                           f"• Type: {order_type.upper()}\n"
                           f"• Entry: {entry_price:.4f}\n"
                           f"• TP: {tp_price:.4f}\n"
                           f"• SL: {sl_price:.4f}\n"
                           f"• R:R: 1:{rr_ratio:.2f}\n\n"
                           f"💰 <b>Size & Risk:</b>\n"
                           f"• Margin: ${margin_usdt:.2f}\n"
                           f"• Size: ${position_size_usdt:.2f} (x{lev})\n\n"
                           f"📝 <b>Reason:</b>\n"
                           f"{reason}")
                    
                    await kirim_tele(msg)
                    
                    await executor.execute_entry(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        price=entry_price,
                        amount_usdt=amt,
                        leverage=lev,
                        strategy_tag=f"AI_{strategy_mode}",
                        atr_value=atr_val 
                    )
                else:
                    logger.info(f"🛑 AI Vote Low Confidence: {confidence}% (Need {config.AI_CONFIDENCE_THRESHOLD}%)")

            # Rate Limit Protection
            await asyncio.sleep(config.ERROR_SLEEP_DELAY) 

        except Exception as e:
            logger.error(f"Main Loop Error: {e}")
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot Stopped Manually.")
        kirim_tele_sync("🛑 Bot Stopped Manually")
    except Exception as e:
        print(f"💀 Fatal Crash: {e}")
        kirim_tele_sync(f"💀 Bot Crash: {e}")