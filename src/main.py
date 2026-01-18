

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

import time
import html
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele, kirim_tele_sync, parse_timeframe_to_seconds
from src.utils.prompt_builder import build_market_prompt
from src.utils.calc import calculate_trade_scenarios

# MODULE IMPORTS
from src.modules.market_data import MarketDataManager
from src.modules.sentiment import SentimentAnalyzer
from src.modules.onchain import OnChainAnalyzer
from src.modules.ai_brain import AIBrain
from src.modules.executor import OrderExecutor
from src.modules.pattern_recognizer import PatternRecognizer

# GLOBAL INSTANCES
market_data = None
sentiment = None
onchain = None
ai_brain = None
executor = None
pattern_recognizer = None

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

            # Sync Pending Orders (Handle Manual Cancel)
            await executor.sync_pending_orders()
            
            # Check Tracker vs Real Positions
            for base_sym, pos in executor.position_cache.items():
                symbol = pos['symbol']
                # If position exists but not in tracker OR status is PENDING
                tracker = executor.safety_orders_tracker.get(symbol, {})
                status = tracker.get('status', 'NONE')
                
                if status in ['NONE', 'PENDING', 'WAITING_ENTRY']:
                    logger.info(f"🛡️ Found Unsecured Position: {symbol}. Installing Safety...")
                    success = await executor.install_safety_orders(symbol, pos)
                    if success:
                        # Update status but PRESERVE existing data (like atr_value)
                        if symbol not in executor.safety_orders_tracker:
                            executor.safety_orders_tracker[symbol] = {}
                        
                        executor.safety_orders_tracker[symbol].update({
                            "status": "SECURED",
                            "last_check": time.time()
                        })
                        executor.save_tracker()
            
            # Sleep 
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)
            
        except Exception as e:
            logger.error(f"Safety Loop Error: {e}")
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)

async def main():
    global market_data, sentiment, onchain, ai_brain, executor, pattern_recognizer
    
    # Track AI Query Timestamp (Candle ID)
    analyzed_candle_ts = {}
    # Time constants
    timeframe_exec_seconds = parse_timeframe_to_seconds(config.TIMEFRAME_EXEC)
    sentiment_interval_seconds = parse_timeframe_to_seconds(config.SENTIMENT_UPDATE_INTERVAL)
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
    pattern_recognizer = PatternRecognizer(market_data)

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
            
            # COOLDOWN LOGIC BASED ON RESULT (Profit/Loss)
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
                
                # Clean up tracker immediately
                executor.remove_from_tracker(symbol)
            
            else:
                # ENTRY FILL (RP = 0)
                # Cek jika ini adalah LIMIT ORDER yang terisi
                order_type = o.get('o', 'UNKNOWN')
                if order_type == 'LIMIT':
                     price_filled = float(o.get('ap', 0))
                     qty_filled = float(o.get('q', 0))
                     side_filled = o['S'] # BUY/SELL
                     size_usdt = qty_filled * price_filled
                     
                     # Calculate TP/SL for Notification
                     tracker = executor.safety_orders_tracker.get(sym, {})
                     atr_val = tracker.get('atr_value', 0)
                     
                     tp_str = "-"
                     sl_str = "-"
                     rr_str = "-"
                     
                     if atr_val > 0:
                         dist_sl = atr_val * config.TRAP_SAFETY_SL
                         dist_tp = atr_val * config.ATR_MULTIPLIER_TP1
                         
                         if side_filled.upper() == 'BUY':
                             sl_p = price_filled - dist_sl
                             tp_p = price_filled + dist_tp
                         else: # SELL
                             sl_p = price_filled + dist_sl
                             tp_p = price_filled - dist_tp
                             
                         tp_str = f"{tp_p:.4f}"
                         sl_str = f"{sl_p:.4f}"
                         
                         rr = dist_tp / dist_sl if dist_sl > 0 else 0
                         rr_str = f"1:{rr:.2f}"
                     
                     msg = (
                        f"✅ <b>LIMIT ENTRY FILLED</b>\n"
                        f"✨ <b>{sym}</b>\n"
                        f"🏷️ Type: {order_type}\n"
                        f"🚀 Side: {side_filled}\n"
                        f"📏 Size: ${size_usdt:.2f}\n"
                        f"💵 Price: {price_filled}\n\n"
                        f"🎯 <b>Safety Orders:</b>\n"
                        f"• TP: {tp_str}\n"
                        f"• SL: {sl_str}\n"
                        f"• R:R: {rr_str}"
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
            # Cek apakah sudah waktunya update berita & F&G (custom interval)
            if time.time() - last_sentiment_update_time >= sentiment_interval_seconds:
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
                logger.warning(f"⚠️ No tech data or insufficient history for {symbol}")
                await asyncio.sleep(2)
                continue

            sentiment_data = sentiment.get_latest()
            onchain_data = onchain.get_latest()

            # --- STEP B: CHECK EXCLUSION (Cooldown / Existing Position) ---
            # 1. Active Position Check (Active OR Pending)
            if executor.has_active_or_pending_trade(symbol):
                # logger.info(f"Skipping {symbol} (Active Position or Pending Order)")
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
            if tech_data['rsi'] < config.RSI_OVERSOLD or tech_data['rsi'] > config.RSI_OVERBOUGHT:
                is_interesting = True
            
            if not is_interesting:
                #logger.info(f"💤 {symbol} Boring (RSI: {tech_data['rsi']:.1f}, Corr: {btc_corr:.2f}). Skip AI.")
                await asyncio.sleep(2)
                continue

            # --- STEP C.5: STRATEGY SELECTION REMOVED ---
            # We now let AI decide the strategy based on the prompt.
            # ADX is still passed in tech_data's 'adx' for AI context.
            tech_data['strategy_mode'] = 'AI_DECISION' # Placeholder, overridden by AI response

            # Filter Logic Update based on Strategy
            # ... (Existing filter logic modified to respect strategy) ...
            
            # (Untuk simplifikasi, kita gabung ke existing logic tapi tambah logging)
            #logger.info(f"📊 Strategy Mode: {strategy_mode} (ADX: {adx_val:.2f})")

            # --- STEP D: AI ANALYSIS ---
            # Candle-Based Throttling (Smart Execution)
            # Logic: Hanya tanya AI jika candle Exec Timeframe (misal 1H) sudah close & berganti baru.
            # Kita bandingkan timestamp candle terakhir yang datanya kita ambil vs yang terakhir kita analisa.
            
            current_candle_ts = tech_data.get('candle_timestamp', 0)
            last_analyzed_ts = analyzed_candle_ts.get(symbol, 0)
            
            if current_candle_ts <= last_analyzed_ts:
                # Candle ID masih sama = Candle belum ganti = Skip Analisa
                # logger.info(f"⏳ {symbol} Candle {current_candle_ts} already analyzed. Waiting next candle...")
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue

            # ... (Existing Code)
            logger.info(f"🤖 Asking AI: {symbol} (Corr: {btc_corr:.2f}, Candle: {current_candle_ts}) ...")
            
            # Pattern Recognition (Vision)
            pattern_ctx = await pattern_recognizer.analyze_pattern(symbol)
            
            # Order Book Depth Analysis (Scalping Context)
            ob_depth = await market_data.get_order_book_depth(symbol)
            tech_data['order_book'] = ob_depth
            
            tech_data['btc_correlation'] = btc_corr
            
            # Calculate Trade Scenarios BEFORE AI Call
            # AI need to know what "Market" vs "Liquidity Hunt" looks like
            current_price = tech_data['price']
            # Determine potential side (Assumption for Prompt Context - AI can switch but we give baseline)
            # We can give both BUY/SELL scenarios or just implied one.
            # To be neutral, we calculate generic parameters or double scenarios.
            # However, prompt builder usually contextualizes based on trend. 
            # Simplification: We send "BUY" scenarios as standard reference, AI understands inverse for sell.
            # OR better: Calc creates generic structure. Let's stick to "BUY" reference for prompt clarity
            # unless we detect Bearish trend. Let's try to pass BOTH or Generic.
            # Current calc implementation needs a side. Let's Default to 'BUY' for visualization,
            # AI will inverse the logic if it wants to SELL (sl/tp inverted).
            # Actually, `calc` is cheap. We can check trend.
            pre_calc_side = 'BUY'
            if tech_data['trend_major'] == 'Bearish' or tech_data['btc_trend'] == 'BEARISH':
                pre_calc_side = 'SELL'
            
            trade_scenarios = calculate_trade_scenarios(
                price=current_price,
                atr=tech_data.get('atr', 0),
                side=pre_calc_side 
            )

            prompt = build_market_prompt(symbol, tech_data, sentiment_data, onchain_data, pattern_ctx, trade_scenarios)
            
            # Print Prompt for Debugging
            logger.info(f"📝 AI PROMPT INPUT for {symbol}:\n{prompt}")

            ai_decision = await ai_brain.analyze_market(prompt)
            
            # Update Timestamp (Candle ID) instead of System Time
            analyzed_candle_ts[symbol] = current_candle_ts
            
            decision = ai_decision.get('decision', 'WAIT').upper()
            confidence = ai_decision.get('confidence', 0)
            reason = html.escape(str(ai_decision.get('reason', '')))

            # --- STEP E: EXECUTION ---
            if decision in ['BUY', 'SELL', 'LONG', 'SHORT']:
                # Mapping AI Output
                side = 'buy' if decision in ['BUY', 'LONG'] else 'sell'
                
                # Get Strategy Selected by AI
                strategy_mode = ai_decision.get('selected_strategy', 'STANDARD')

                if confidence >= config.AI_CONFIDENCE_THRESHOLD:
                    # Execute!
                    lev = coin_cfg.get('leverage', config.DEFAULT_LEVERAGE)
                    
                    # Dynamic Sizing
                    dynamic_amt = await executor.calculate_dynamic_amount_usdt(symbol, lev)
                    if dynamic_amt:
                        amt = dynamic_amt
                        logger.info(f"💰 Dynamic Size: ${amt:.2f} (Risk {config.RISK_PERCENT_PER_TRADE}%)")
                    else:
                        amt = coin_cfg.get('amount', config.DEFAULT_AMOUNT_USDT)
                    
                    # EXECUTION LOGIC UPDATE
                    # 1. Determine Mode from AI
                    exec_mode = ai_decision.get('execution_mode', 'MARKET').upper()
                    
                    # 2. Re-Calculate PRECISELY for the decided side
                    # (Helper function `calculate_trade_scenarios` is lightweight)
                    params = calculate_trade_scenarios(
                        price=tech_data['price'],
                        atr=tech_data.get('atr', 0),
                        side=side
                    )
                    
                    # 3. Select Parameters
                    final_setup = {}
                    order_type = 'market'
                    
                    if exec_mode == 'LIQUIDITY_HUNT' and params.get('liquidity_hunt'):
                        # Apply Liquidity Hunt Logic
                        order_type = 'limit'
                        mode_data = params['liquidity_hunt']
                        entry_price = mode_data['entry']
                        sl_price = mode_data['sl']
                        tp_price = mode_data['tp']
                        logger.info(f"🔫 Liquidity Hunt Selected. Limit Order @ {entry_price:.4f}")
                    else:
                        # Default / Market Logic
                        order_type = 'market'
                        # Use recalculation from params['market'] to be consistent with what AI saw
                        mode_data = params['market']
                        entry_price = tech_data['price'] # Market order uses current price roughly
                        sl_price = mode_data['sl']
                        tp_price = mode_data['tp']

                    rr_ratio = abs(tp_price - entry_price) / abs(entry_price - sl_price) if abs(entry_price - sl_price) > 0 else 0
                    
                    # Formatting Message
                    margin_usdt = amt
                    position_size_usdt = amt * lev
                    direction_icon = "🟢" if side == 'buy' else "🔴"
                    
                    btc_trend_icon = "🟢" if tech_data['btc_trend'] == "BULLISH" else "🔴"
                    btc_corr_icon = "🔒" if btc_corr >= config.CORRELATION_THRESHOLD_BTC else "🔓"

                    # Execution Type Header
                    type_str = "🚀 AGRESSIVE (MARKET)" if order_type == 'market' else "🪤 PASSIVE (LIQUIDITY HUNT)"

                    msg = (f"🧠 <b>AI SIGNAL MATCHED</b>\n"
                           f"{type_str}\n\n"
                           f"Coin: {symbol}\n"
                           f"Signal: {direction_icon} {decision} ({confidence}%)\n"
                           f"Timeframe: {config.TIMEFRAME_EXEC}\n"
                           f"BTC Trend: {btc_trend_icon} {tech_data['btc_trend']}\n"
                           f"BTC Correlation: {btc_corr_icon} {btc_corr:.2f}\n"
                           f"Strategy: {strategy_mode}\n\n"
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
                    
                    logger.info(f"📤 Sending Tele Message:\n{msg}")
                    await kirim_tele(msg)
                    
                    atr_val = tech_data.get('atr', 0)
                    await executor.execute_entry(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        price=entry_price,
                        amount_usdt=amt,
                        leverage=lev,
                        strategy_tag=f"AI_{strategy_mode}_{exec_mode}",
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