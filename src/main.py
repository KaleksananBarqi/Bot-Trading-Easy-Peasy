


import asyncio

import time
import html
from datetime import datetime
import ccxt.async_support as ccxt
import config
from src.utils.helper import (
    logger, kirim_tele, kirim_tele_sync, parse_timeframe_to_seconds, 
    get_next_rounded_time, get_coin_leverage, convert_timestamp_to_wib_str
)
from src.utils.prompt_builder import build_market_prompt, build_sentiment_prompt
from src.utils.calc import calculate_trade_scenarios, calculate_dual_scenarios, calculate_profit_loss_estimation

# MODULE IMPORTS
from src.modules.market_data import MarketDataManager
from src.modules.sentiment import SentimentAnalyzer
from src.modules.onchain import OnChainAnalyzer
from src.modules.ai_brain import AIBrain
from src.modules.executor import OrderExecutor
from src.modules.pattern_recognizer import PatternRecognizer
from src.modules.journal import TradeJournal

# GLOBAL INSTANCES
market_data = None
sentiment = None
onchain = None
ai_brain = None
executor = None

async def activate_native_trailing_delayed(symbol, side, qty):
    """
    Activate native trailing stop after a delay.
    Extracted from main() as a module-level helper function.
    """
    logger.info(f"⏳ Waiting {config.TRAILING_ACTIVATION_DELAY}s to activate Native Trailing for {symbol}...")
    await asyncio.sleep(config.TRAILING_ACTIVATION_DELAY)
    
    if not executor.has_active_or_pending_trade(symbol):
        logger.warning(f"⚠️ Position {symbol} closed before Native Trailing activation.")
        return

    success = await executor.install_native_trailing_stop(
        symbol, side, qty, config.TRAILING_CALLBACK_RATE
    )
    if success:
       await kirim_tele(f"🔄 <b>NATIVE TRAILING ACTIVE</b>\n{symbol}\nCallback: {config.TRAILING_CALLBACK_RATE*100}%")

pattern_recognizer = None
journal = None


async def run_sentiment_analysis():
    """
    Run sentiment analysis using AI.
    Extracted from main() as a module-level helper function.
    """
    global sentiment, onchain, ai_brain
    
    if not config.ENABLE_SENTIMENT_ANALYSIS:
        return

    try:
        # Prepare Prompt
        s_data = sentiment.get_latest()
        o_data = onchain.get_latest()
        prompt = build_sentiment_prompt(s_data, o_data)
        
        # Ask AI
        logger.info(f"📝 SENTIMENT AI PROMPT:\n{prompt}")
        result = await ai_brain.analyze_sentiment(prompt)
        
        if result:
            # Save Analysis to Cache
            sentiment.save_analysis(result)

            # Kirim ke Telegram Channel Sentiment
            mood = result.get('overall_sentiment', 'UNKNOWN')
            score = result.get('sentiment_score', 0)
            phase = result.get('market_phase', '-')
            smart_money = result.get('smart_money_activity', '-')
            retail_mood = result.get('retail_sentiment', '-')
            
            summary = result.get('summary', '-')
            drivers = result.get('key_drivers', [])
            risk = result.get('risk_assessment', 'N/A')
            drivers_str = "\n".join([f"• {d}" for d in drivers])
            
            icon = "😐"
            if score > 60: icon = "🚀"
            elif score < 40: icon = "🐻"
            
            msg = (
                f"📢 <b>PASAR SAAT INI {mood} {icon}</b>\n"
                f"Score: {score}/100\n\n"
                f"🌀 <b>Phase:</b> {phase}\n"
                f"🐋 <b>Whales:</b> {smart_money}\n"
                f"👥 <b>Retail:</b> {retail_mood}\n\n"
                f"📝 <b>Ringkasan:</b>\n{summary}\n\n"
                f"🔑 <b>Faktor Utama:</b>\n{drivers_str}\n\n"
                f"⚠️ <b>Risk Assessment:</b>\n{risk}\n\n"
                f"<i>Analisa ini digenerate otomatis oleh AI ({config.AI_SENTIMENT_MODEL})</i>"
            )
            
            logger.info(f"📤 SENTIMENT TELEGRAM MESSAGE:\n{msg}")
            await kirim_tele(msg, channel='sentiment')
            logger.info("✅ Sentiment Report Sent.")
    except Exception as e:
        logger.error(f"❌ Sentiment Loop Error: {e}")


async def safety_monitor_loop(executor: OrderExecutor) -> None:
    """
    Background Task untuk memantau posisi terbuka.
    - Cek Pending Orders (cleanup)
    - Re-verify Tracker consistency
    - (Trailing Stop sekarang via WebSocket push, bukan polling di sini)

    Args:
        executor: Instance OrderExecutor untuk operasi trading
    """
    logger.info("🛡️ Safety Monitor Started")
    while True:
        try:
            # 1. Sync & Cleanup Pending Orders
            await executor.sync_pending_orders()

            # 2. Sync Posisi vs Tracker (Housekeeping)
            # Pastikan jika ada posisi manual/baru yang belum masuk tracker, kita amankan.
            count = await executor.sync_positions()

            for base_sym, pos in executor.position_cache.items():
                symbol = pos['symbol']
                tracker = executor.safety_orders_tracker.get(symbol, {})
                status = tracker.get('status', 'NONE')

                if status in ['NONE', 'PENDING', 'WAITING_ENTRY']:
                    logger.info(f"🛡️ Found Unsecured Position: {symbol}. Installing Safety...")
                    success = await executor.install_safety_orders(symbol, pos)
                    if success:
                        if symbol not in executor.safety_orders_tracker:
                            executor.safety_orders_tracker[symbol] = {}
                        executor.safety_orders_tracker[symbol].update({
                            "status": "SECURED",
                            "last_check": time.time()
                        })
                        await executor.save_tracker()

            # Sleep agak lama karena load utama sudah di WebSocket
            await asyncio.sleep(config.SAFETY_MONITOR_INTERVAL)

        except Exception as e:
            logger.error(f"Safety Loop Error: {e}")
            await asyncio.sleep(config.ERROR_SLEEP_DELAY)

async def trailing_price_handler(symbol, price):
    """Callback untuk menangani update harga realtime dari WebSocket"""
    if config.ENABLE_TRAILING_STOP and executor:
        await executor.check_trailing_on_price(symbol, price)

async def whale_handler(symbol, amount, side):
    """Callback dari Market Data (AggTrade) untuk whale detection"""
    if onchain:
        onchain.detect_whale(symbol, amount, side)


# ============================================================================
# EXTRACTED HELPER FUNCTIONS (dari main() untuk mengurangi kompleksitas)
# ============================================================================

def _initialize_exchange():
    """
    Setup CCXT Binance exchange instance.
    Extracted from main() initialization block.
    """
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
    return exchange


def _initialize_modules(exchange):
    """
    Setup semua module instances.
    Extracted from main() setup block.
    
    Returns:
        tuple: (market_data, sentiment, onchain, ai_brain, executor, pattern_recognizer, journal)
    """
    md = MarketDataManager(exchange)
    sent = SentimentAnalyzer()
    oc = OnChainAnalyzer()
    ai = AIBrain()
    exe = OrderExecutor(exchange)
    pr = PatternRecognizer(md)
    jr = TradeJournal()
    return md, sent, oc, ai, exe, pr, jr


def _build_non_filled_trade_data(sym, tracker, result_status):
    """
    Build trade data dict untuk order yang CANCELLED atau TIMEOUT (tidak pernah filled).
    Deduplikasi dari handler cancelled dan expired yang >90% identik.
    
    Args:
        sym: Symbol (e.g. 'BTC/USDT')
        tracker: Safety orders tracker dict untuk symbol ini
        result_status: 'CANCELLED' atau 'TIMEOUT'
    
    Returns:
        dict: Trade data siap untuk journal.log_trade()
    """
    strategy_tag = tracker.get('strategy', 'UNKNOWN')
    prompt_text = tracker.get('ai_prompt', '-')
    reason_text = tracker.get('ai_reason', '-')
    setup_at_ts = tracker.get('created_at', 0)
    tech_snapshot = tracker.get('technical_data', {})
    cfg_snapshot = tracker.get('config_snapshot', {})
    entry_price_setup = tracker.get('entry_price', 0)
    side_setup = tracker.get('side', 'UNKNOWN')

    setup_at_str = datetime.fromtimestamp(setup_at_ts).isoformat() if setup_at_ts > 0 else ''
    
    return {
        'symbol': sym,
        'side': side_setup,
        'type': 'LIMIT',
        'entry_price': entry_price_setup,
        'exit_price': 0,
        'size_usdt': 0,
        'pnl_usdt': 0,
        'result': result_status,
        'strategy_tag': strategy_tag,
        'prompt': prompt_text,
        'reason': reason_text,
        'setup_at': setup_at_str,
        'filled_at': '',  # Never filled
        'technical_data': tech_snapshot,
        'config_snapshot': cfg_snapshot
    }


async def _handle_order_cancelled(sym, o):
    """
    Handle CANCELED order dari WebSocket event.
    Extracted from order_update_cb().
    """
    order_id = str(o.get('i', ''))
    
    # Check if this is our tracked order
    tracker = executor.safety_orders_tracker.get(sym, {})
    tracked_id = str(tracker.get('entry_id', ''))
    
    if tracked_id == order_id:
        # This is our limit entry order - was cancelled manually
        logger.info(f"🗑️ Order CANCELED manually: {sym} (ID: {order_id})")
        
        # Log to journal as CANCELLED
        trade_data = _build_non_filled_trade_data(sym, tracker, 'CANCELLED')
        if journal:
            journal.log_trade(trade_data)

        await executor.remove_from_tracker(sym)
        await kirim_tele(
            f"🗑️ <b>ORDER CANCELED</b>\n"
            f"Order {sym} dibatalkan secara manual.\n"
            f"Tracker cleaned & Logged to Journal."
        )
    else:
        # Not our tracked order (could be SL/TP or other) - just log
        logger.debug(f"🔔 Order canceled (non-entry): {sym} ID {order_id}")


async def _handle_order_expired(sym, o):
    """
    Handle EXPIRED order dari WebSocket event.
    Extracted from order_update_cb().
    """
    order_id = str(o.get('i', ''))
    
    # Check if this is our tracked order
    tracker = executor.safety_orders_tracker.get(sym, {})
    tracked_id = str(tracker.get('entry_id', ''))
    
    if tracked_id == order_id:
        logger.info(f"⏰ Order EXPIRED/TIMEOUT: {sym} (ID: {order_id})")
        
        # Log to journal as TIMEOUT
        trade_data = _build_non_filled_trade_data(sym, tracker, 'TIMEOUT')
        if journal:
            journal.log_trade(trade_data)

        await executor.remove_from_tracker(sym)
        await kirim_tele(
            f"⏰ <b>ORDER EXPIRED</b>\n"
            f"Limit Order {sym} kadaluarsa (timeout).\n"
            f"Tracker cleaned & Logged to Journal."
        )
    else:
        logger.debug(f"🔔 Order expired (non-entry): {sym} ID {order_id}")


async def _handle_position_close(sym, o):
    """
    Handle FILLED order yang menutup posisi (Realized Profit != 0).
    Mengatur cooldown, kirim notifikasi PnL, dan log ke journal.
    Extracted from order_update_cb().
    """
    rp = float(o.get('rp', 0))
    price = float(o.get('ap', 0))
    order_type = o.get('o', 'UNKNOWN')
    order_info = o
    symbol = sym
    pnl = rp
    
    # COOLDOWN LOGIC BASED ON RESULT (Profit/Loss)
    if pnl > 0:
        executor.set_cooldown(sym, config.COOLDOWN_IF_PROFIT)
    else:
        executor.set_cooldown(sym, config.COOLDOWN_IF_LOSS)
    
    # Format Pesan
    emoji = "💰" if pnl > 0 else "🛑"
    title = "TAKE PROFIT HIT" if pnl > 0 else "STOP LOSS HIT"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
    
    # Hitung size yang diclose
    qty_closed = float(order_info.get('q', 0))
    size_closed_usdt = qty_closed * price
    
    # --- ROI CALCULATION ---
    leverage = get_coin_leverage(symbol)
    margin_used = size_closed_usdt / leverage if leverage > 0 else size_closed_usdt
    
    roi_percent = 0
    if margin_used > 0:
        roi_percent = (pnl / margin_used) * 100
        
    roi_icon = "🔥" if roi_percent > 0 else "🩸"
    
    msg = (
            f"{emoji} <b>{title}</b>\n"
            f"✨ <b>{symbol}</b>\n"
            f"🏷️ Type: {order_type}\n"
            f"📏 Size: ${size_closed_usdt:.2f}\n" 
            f"💵 Price: {price}\n"
            f"💸 PnL: <b>{pnl_str}</b>\n"
            f"{roi_icon} ROI: <b>{roi_percent:+.2f}%</b>"
        )
    await kirim_tele(msg)

    # --- RECORD TRADE TO JOURNAL ---
    tracker = executor.safety_orders_tracker.get(symbol, {})
    strategy_tag = tracker.get('strategy', 'UNKNOWN')
    prompt_text = tracker.get('ai_prompt', '-')
    reason_text = tracker.get('ai_reason', '-')
    setup_at_ts = tracker.get('created_at', 0)
    filled_at_ts = tracker.get('filled_at', 0)
    tech_snapshot = tracker.get('technical_data', {})
    cfg_snapshot = tracker.get('config_snapshot', {})
    
    setup_at_str = datetime.fromtimestamp(setup_at_ts).isoformat() if setup_at_ts > 0 else ''
    filled_at_str = datetime.fromtimestamp(filled_at_ts).isoformat() if filled_at_ts > 0 else ''

    # Get Order Type from Tracker (Entry Type), not Closing Order Type
    entry_order_type = tracker.get('order_type', 'MARKET')

    trade_data = {
        'symbol': symbol,
        'side': tracker.get('side', 'LONG' if order_info['S'] == 'SELL' else 'SHORT'), 
        'type': entry_order_type,
        'entry_price': tracker.get('entry_price', 0),
        'exit_price': price,
        'size_usdt': size_closed_usdt,
        'pnl_usdt': pnl,
        'roi_percent': roi_percent,
        'fee': float(order_info.get('n', 0)),
        'strategy_tag': strategy_tag,
        'prompt': prompt_text,
        'reason': reason_text,
        'setup_at': setup_at_str,
        'filled_at': filled_at_str,
        'technical_data': tech_snapshot,
        'config_snapshot': cfg_snapshot
    }
    
    if journal:
        journal.log_trade(trade_data)
    
    # Clean up tracker immediately
    await executor.remove_from_tracker(symbol)


async def _handle_entry_fill(sym, o):
    """
    Handle FILLED limit entry order (RP = 0).
    Update tracker, kirim notifikasi, dan aktifkan native trailing jika dikonfigurasi.
    Extracted from order_update_cb().
    """
    order_type = o.get('o', 'UNKNOWN')
    if order_type != 'LIMIT':
        return
    
    price_filled = float(o.get('ap', 0))
    qty_filled = float(o.get('q', 0))
    side_filled = o['S']  # BUY/SELL
    size_usdt = qty_filled * price_filled
    
    # Update Tracker with FILLED time
    if sym in executor.safety_orders_tracker:
        executor.safety_orders_tracker[sym]['filled_at'] = time.time()
        await executor.save_tracker()

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
        else:  # SELL
            sl_p = price_filled + dist_sl
            tp_p = price_filled - dist_tp
            
        tp_str = f"{tp_p:.4f}"
        sl_str = f"{sl_p:.4f}"
        
        rr = dist_tp / dist_sl if dist_sl > 0 else 0
        rr_str = f"1:{rr:.2f}"
    
    # NATIVE TRAILING LOGIC
    trailing_note = ""
    if config.USE_NATIVE_TRAILING:
        trailing_note = f"\n⏳ <b>Native Trailing:</b> Activating in {config.TRAILING_ACTIVATION_DELAY}s..."
        asyncio.create_task(activate_native_trailing_delayed(sym, side_filled, qty_filled))
    
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
        f"{trailing_note}"
    )
    await kirim_tele(msg)


async def order_update_cb(payload):
    """
    Handle order updates dari WebSocket (FILLED, CANCELED, EXPIRED).
    Module-level dispatcher yang mendelegasikan ke handler spesifik.
    Extracted from main() as a module-level callback.
    """
    o = payload['o']
    sym = o['s'].replace('USDT', '/USDT')
    status = o['X']
    
    if status == 'CANCELED':
        await _handle_order_cancelled(sym, o)
    elif status == 'EXPIRED':
        await _handle_order_expired(sym, o)
    elif status == 'FILLED':
        rp = float(o.get('rp', 0))
        logger.info(f"⚡ Order Filled: {sym} {o['S']} @ {o['ap']} | RP: {rp}")
        
        if rp != 0:
            # Position Close (Realized Profit != 0)
            await _handle_position_close(sym, o)
        else:
            # Entry Fill (RP = 0)
            await _handle_entry_fill(sym, o)
        
        # Trigger safety check immediately
        await executor.sync_positions()


async def account_update_cb(payload):
    """
    Callback WebSocket untuk perubahan akun (balance/position).
    Extracted from main() as a module-level callback.
    """
    await executor.sync_positions()


def _run_periodic_updates(scheduler_state):
    """
    Jalankan scheduled updates untuk sentiment data dan AI analysis.
    Extracted from main loop scheduler block.
    
    Args:
        scheduler_state: dict dengan keys 'next_sentiment_update' dan 'next_sentiment_analysis'
    """
    current_time = time.time()

    # A. DATA REFRESH (RSS & FnG & OnChain)
    if current_time >= scheduler_state['next_sentiment_update']:
        logger.info("🔄 Refreshing Sentiment & On-Chain Data (Fetch Only)...")
        try:
            asyncio.create_task(sentiment.update_all())
            asyncio.create_task(onchain.fetch_stablecoin_inflows())
            
            scheduler_state['next_sentiment_update'] = get_next_rounded_time(config.SENTIMENT_UPDATE_INTERVAL)
            logger.info(f"✅ Data Refreshed. Next: {convert_timestamp_to_wib_str(scheduler_state['next_sentiment_update'])}")
        except Exception as e:
             logger.error(f"❌ Failed to refresh data: {e}")

    # B. AI SENTIMENT ANALYSIS (Report Generation)
    if config.ENABLE_SENTIMENT_ANALYSIS and current_time >= scheduler_state['next_sentiment_analysis']:
         logger.info("🧠 Running Scheduled Sentiment Analysis (AI)...")
         
         asyncio.create_task(run_sentiment_analysis())
         
         scheduler_state['next_sentiment_analysis'] = get_next_rounded_time(config.SENTIMENT_ANALYSIS_INTERVAL)
         logger.info(f"✅ Analysis Triggered. Next: {convert_timestamp_to_wib_str(scheduler_state['next_sentiment_analysis'])}")


def _check_trade_exclusions(symbol, coin_cfg):
    """
    Cek apakah symbol harus di-skip (active position, cooldown, category limit).
    Extracted from main loop exclusion check block.
    
    Returns:
        bool: True jika harus di-skip, False jika boleh lanjut
    """
    # 1. Active Position Check (Active OR Pending)
    if executor.has_active_or_pending_trade(symbol):
        return True
    
    # 2. Cooldown Check
    if executor.is_under_cooldown(symbol):
        return True

    # 3. Check Category Limit
    category = coin_cfg.get('category', 'UNKNOWN')
    if config.MAX_POSITIONS_PER_CATEGORY > 0:
        current_cat_count = executor.get_open_positions_count_by_category(category)
        if current_cat_count >= config.MAX_POSITIONS_PER_CATEGORY:
            return True
    
    return False


async def _apply_traditional_filters(symbol, tech_data, coin_cfg):
    """
    Terapkan filter teknikal tradisional sebelum AI analysis.
    Menghemat token AI dengan memfilter setup yang jelas buruk.
    Extracted from main loop filter block.
    
    Returns:
        tuple: (is_interesting: bool, btc_corr: float, show_btc_context: bool)
    """
    is_interesting = False
    
    # Filter 1: Trend Alignment (King Filter) & Correlation Check
    # [KING EXCEPTION] BTC tidak perlu cek korelasi (pasti 1.0, tidak bermakna)
    if symbol == config.BTC_SYMBOL:
        btc_corr = 1.0
        show_btc_context = False
        
        if tech_data['price_vs_ema'] in ["Above", "Below"]:
            is_interesting = True
    else:
        btc_corr = await market_data.get_btc_correlation(symbol)
        
        use_btc_corr_config = coin_cfg.get('btc_corr', True)
        show_btc_context = False

        if use_btc_corr_config:
            if btc_corr >= config.CORRELATION_THRESHOLD_BTC:
                show_btc_context = True
                
                if tech_data['btc_trend'] == "BULLISH" and tech_data['price_vs_ema'] == "Above":
                    is_interesting = True
                elif tech_data['btc_trend'] == "BEARISH" and tech_data['price_vs_ema'] == "Below":
                    is_interesting = True
                else:
                    pass  # Conflicting signal -> Skip
            else:
                show_btc_context = False
                is_interesting = True
        else:
            show_btc_context = False
            
            if tech_data['price_vs_ema'] in ["Above", "Below"]:
                is_interesting = True
            else:
                pass

    
    # Filter 2: RSI Extremes (Reversal)
    if tech_data['rsi'] < config.RSI_OVERSOLD or tech_data['rsi'] > config.RSI_OVERBOUGHT:
        is_interesting = True
    
    return is_interesting, btc_corr, show_btc_context


async def _prepare_and_execute_trade(symbol, side, tech_data, coin_cfg, ai_decision, 
                                      dual_scenarios, btc_corr, show_btc_context, prompt, reason):
    """
    Build order parameters, kirim notifikasi Telegram, dan eksekusi entry.
    Extracted from main loop execution block.
    
    Args:
        symbol: Trading pair symbol
        side: 'buy' atau 'sell'
        tech_data: Data teknikal dari MarketDataManager
        coin_cfg: Konfigurasi koin dari config.DAFTAR_KOIN
        ai_decision: Dict hasil analisa AI
        dual_scenarios: Dict skenario long/short dari calculate_dual_scenarios
        btc_corr: Korelasi BTC
        show_btc_context: Apakah menampilkan konteks BTC
        prompt: Prompt AI yang dikirim
        reason: Alasan keputusan AI (sudah di-escape)
    """
    strategy_mode = ai_decision.get('selected_strategy', 'STANDARD')
    confidence = ai_decision.get('confidence', 0)
    lev = coin_cfg.get('leverage', config.DEFAULT_LEVERAGE)
    
    # Dynamic Sizing
    dynamic_amt = await executor.calculate_dynamic_amount_usdt(symbol, lev)
    if dynamic_amt:
        amt = dynamic_amt
        logger.info(f"💰 Dynamic Size: ${amt:.2f} (Risk {config.RISK_PERCENT_PER_TRADE}%)")
    else:
        amt = coin_cfg.get('amount', config.DEFAULT_AMOUNT_USDT)
    
    # EXECUTION LOGIC
    # 1. Determine Mode from AI
    exec_mode = ai_decision.get('execution_mode', 'MARKET').upper()
    
    # 2. Use CACHED Dual Scenarios
    params = dual_scenarios['long'] if side == 'buy' else dual_scenarios['short']
    
    # 3. Select Parameters
    order_type = 'market'
    
    if exec_mode == 'LIMIT' and params.get('liquidity_hunt'):
        order_type = 'limit'
        mode_data = params['liquidity_hunt']
        entry_price = mode_data['entry']
        sl_price = mode_data['sl']
        tp_price = mode_data['tp']
        logger.info(f"🔫 Limit Setup Selected. Entry @ {entry_price:.4f}")
    else:
        # Default / Market Logic
        if not config.ENABLE_MARKET_ORDERS:
             # FORCE FALLBACK TO LIMIT
             order_type = 'limit'
             mode_data = params.get('liquidity_hunt', params['market'])
             entry_price = mode_data.get('entry', tech_data['price'])
             sl_price = mode_data['sl']
             tp_price = mode_data['tp']
             logger.info(f"🛡️ Market Order Disabled. Forcing Limit Order @ {entry_price:.4f}")
             exec_mode = 'LIMIT (FORCED)'
        else:
             order_type = 'market'
             mode_data = params['market']
             entry_price = tech_data['price']
             sl_price = mode_data['sl']
             tp_price = mode_data['tp']

    rr_ratio = abs(tp_price - entry_price) / abs(entry_price - sl_price) if abs(entry_price - sl_price) > 0 else 0
    
    # Formatting Message
    margin_usdt = amt
    position_size_usdt = amt * lev
    direction_icon = "🟢" if side == 'buy' else "🔴"
    
    # Calculate Profit/Loss Estimation
    pnl_est = calculate_profit_loss_estimation(
        entry_price=entry_price,
        tp_price=tp_price,
        sl_price=sl_price,
        side=side,
        amount_usdt=amt,
        leverage=lev
    )
    
    # Conditional BTC Lines
    btc_trend_icon = "🟢" if tech_data['btc_trend'] == "BULLISH" else "🔴"
    btc_corr_icon = "🔒" if btc_corr >= config.CORRELATION_THRESHOLD_BTC else "🔓"
    
    btc_lines = ""
    if config.USE_BTC_CORRELATION:
        btc_lines = (f"BTC Trend: {btc_trend_icon} {tech_data['btc_trend']}\n"
                     f"BTC Correlation: {btc_corr_icon} {btc_corr:.2f}\n")

    # Prepare Sentiment Context
    sentiment_analysis_cached = sentiment.get_analysis() or {}
    s_score = sentiment_analysis_cached.get('sentiment_score', 50)
    s_mood = sentiment_analysis_cached.get('overall_sentiment', 'NEUTRAL')
    
    s_icon = "😐"
    if s_score > 60: s_icon = "🚀"
    elif s_score < 40: s_icon = "🐻"
    
    sentiment_line = f"Mood: {s_icon} {s_mood} (Score: {s_score}) by {config.AI_SENTIMENT_MODEL}"

    # Execution Type Header
    type_str = "🚀 AGRESSIVE (MARKET)" if order_type == 'market' else "🪤 PASSIVE (LIQUIDITY HUNT)"

    msg = (f"🧠 <b>AI SIGNAL MATCHED</b>\n"
           f"{type_str}\n"
           f"{sentiment_line}\n\n"
           f"Coin: {symbol}\n"
           f"Signal: {direction_icon} {ai_decision.get('decision', 'WAIT').upper()} ({confidence}%)\n"
           f"Timeframe: {config.TIMEFRAME_EXEC}\n"
           f"{btc_lines}"
           f"Strategy: {strategy_mode}\n\n"
           f"🛒 <b>Order Details:</b>\n"
           f"• Type: {order_type.upper()}\n"
           f"• Entry: {entry_price:.4f}\n"
           f"• TP: {tp_price:.4f}\n"
           f"• SL: {sl_price:.4f}\n"
           f"• R:R: 1:{rr_ratio:.2f}\n\n"
           f"📈 <b>Estimasi Hasil:</b>\n"
           f"• Jika TP: <b>+${pnl_est['profit_usdt']:.2f}</b> (+{pnl_est['profit_percent']:.2f}%)\n"
           f"• Jika SL: <b>-${pnl_est['loss_usdt']:.2f}</b> (-{pnl_est['loss_percent']:.2f}%)\n\n"
           f"💰 <b>Size & Risk:</b>\n"
           f"• Margin: ${margin_usdt:.2f}\n"
           f"• Size: ${position_size_usdt:.2f} (x{lev})\n\n"
           f"📝 <b>Reason:</b>\n"
           f"{reason}\n\n"
           f"⚠️ <b>Disclaimer:</b>\n"
           f"• Sinyal dibuat oleh AI dari berbagai sumber, tetap DYOR & SUYBI (Sayangi Uangmu Yang Berharga Itu).\n"
           f"• Pattern recognition by {config.AI_VISION_MODEL}\n"
           f"• Final analyze & execution by {config.AI_MODEL_NAME}")
    
    logger.info(f"📤 Sending Tele Message:\n{msg}")
    await kirim_tele(msg)
    
    atr_val = tech_data.get('atr', 0)
    
    # Build Technical & Config Snapshots
    technical_snapshot = {
        'rsi': tech_data.get('rsi', 0),
        'atr': atr_val,
        'price': tech_data.get('price', 0),
        'price_vs_ema': tech_data.get('price_vs_ema', ''),
        'btc_trend': tech_data.get('btc_trend', ''),
        'btc_correlation': btc_corr,
        'stoch_rsi_k': tech_data.get('stoch_k', 0),
        'stoch_rsi_d': tech_data.get('stoch_d', 0),
        'adx': tech_data.get('adx', 0),
        'macd_histogram': tech_data.get('macd_histogram', 0),
        'bb_upper': tech_data.get('bb_upper', 0),
        'bb_lower': tech_data.get('bb_lower', 0),
        'order_book_imbalance': tech_data.get('order_book', {}).get('imbalance_pct', 0),
    }
    config_snapshot = {
        'atr_multiplier_tp': config.ATR_MULTIPLIER_TP1,
        'trap_safety_sl': config.TRAP_SAFETY_SL,
        'risk_percent': config.RISK_PERCENT_PER_TRADE,
        'leverage': lev,
        'ai_confidence': confidence,
        'ai_model': config.AI_MODEL_NAME,
        'vision_model': config.AI_VISION_MODEL,
        'sentiment_model': config.AI_SENTIMENT_MODEL,
        'timeframe_exec': config.TIMEFRAME_EXEC,
        'strategy_mode': strategy_mode,
        'exec_mode': exec_mode,
        'dynamic_size': config.USE_DYNAMIC_SIZE,
        'ENTRY_AT_RETAIL_SL': config.ATR_MULTIPLIER_SL,
    }

    await executor.execute_entry(
        symbol=symbol,
        side=side,
        order_type=order_type,
        price=entry_price,
        amount_usdt=amt,
        leverage=lev,
        strategy_tag=f"AI_{strategy_mode}_{exec_mode}",
        atr_value=atr_val,
        ai_prompt=prompt,
        ai_reason=reason,
        technical_data=technical_snapshot,
        config_snapshot=config_snapshot
    )


# ============================================================================
# MAIN FUNCTION (Orchestrator - Reduced Complexity)
# ============================================================================

async def main():
    global market_data, sentiment, onchain, ai_brain, executor, pattern_recognizer, journal
    
    # Track AI Query Timestamp (Candle ID)
    analyzed_candle_ts = {}
    # Time constants
    timeframe_exec_seconds = parse_timeframe_to_seconds(config.TIMEFRAME_EXEC)
    
    # Scheduler State
    scheduler_state = {
        'next_sentiment_update': get_next_rounded_time(config.SENTIMENT_UPDATE_INTERVAL),
        'next_sentiment_analysis': get_next_rounded_time(config.SENTIMENT_ANALYSIS_INTERVAL),
    }
    
    logger.info(f"⏳ Next Sentiment Data Refresh: {convert_timestamp_to_wib_str(scheduler_state['next_sentiment_update'])}")
    logger.info(f"⏳ Next Sentiment AI Analysis: {convert_timestamp_to_wib_str(scheduler_state['next_sentiment_analysis'])}")

    # 1. INITIALIZATION
    exchange = _initialize_exchange()
    await kirim_tele("🤖 <b>BOT TRADING STARTED</b>\nAI-Hybrid System Online.", alert=True)

    # 2. SETUP MODULES
    market_data, sentiment, onchain, ai_brain, executor, pattern_recognizer, journal = _initialize_modules(exchange)

    # 3. PRELOAD DATA
    await market_data.initialize_data()
    await sentiment.update_all()  # Initial Fetch Headline & F&G

    # Initial AI Analysis (Blocking)
    logger.info("🧠 Performing Initial AI Sentiment Analysis...")
    await run_sentiment_analysis()
    
    # 4. START BACKGROUND TASKS
    asyncio.create_task(market_data.start_stream(account_update_cb, order_update_cb, whale_handler))
    asyncio.create_task(safety_monitor_loop(executor))

    logger.info("🚀 MAIN LOOP RUNNING...")

    # 5. MAIN TRADING LOOP
    ticker_idx = 0
    while True:
        try:
            # --- STEP 0: PERIODIC UPDATE SCHEDULER ---
            _run_periodic_updates(scheduler_state)

            # Round Robin Scan (One coin per loop)
            coin_cfg = config.DAFTAR_KOIN[ticker_idx]
            symbol = coin_cfg['symbol']
            ticker_idx = (ticker_idx + 1) % len(config.DAFTAR_KOIN)
            
            # --- STEP A: COLLECT DATA ---
            tech_data = await market_data.get_technical_data(symbol)
            if not tech_data:
                logger.warning(f"⚠️ No tech data or insufficient history for {symbol}")
                await asyncio.sleep(config.LOOP_SKIP_DELAY)
                continue

            sentiment_data = sentiment.get_latest(symbol=symbol)
            onchain_data = onchain.get_latest(symbol=symbol)

            # --- STEP B: CHECK EXCLUSION ---
            if _check_trade_exclusions(symbol, coin_cfg):
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue
            
            # --- STEP C: TRADITIONAL FILTER ---
            is_interesting, btc_corr, show_btc_context = await _apply_traditional_filters(symbol, tech_data, coin_cfg)
            
            if not is_interesting:
                await asyncio.sleep(config.LOOP_SKIP_DELAY)
                continue

            # Strategy Selection is now handled by AI
            tech_data['strategy_mode'] = 'AI_DECISION'

            # --- STEP D: AI ANALYSIS ---
            # Candle-Based Throttling
            current_candle_ts = tech_data.get('candle_timestamp', 0)
            last_analyzed_ts = analyzed_candle_ts.get(symbol, 0)
            
            if current_candle_ts <= last_analyzed_ts:
                await asyncio.sleep(config.LOOP_SLEEP_DELAY)
                continue

            logger.info(f"🤖 Asking AI: {symbol} (Corr: {btc_corr:.2f}, Candle: {current_candle_ts}) ...")
            
            # Pattern Recognition (Vision)
            pattern_ctx = await pattern_recognizer.analyze_pattern(symbol)
            
            if not pattern_ctx.get('is_valid', True):
                logger.warning(f"⚠️ Skipping {symbol} - Pattern analysis invalid/truncated")
                await asyncio.sleep(config.LOOP_SKIP_DELAY)
                continue
            
            # Order Book Depth Analysis
            ob_depth = await market_data.get_order_book_depth(symbol)
            tech_data['order_book'] = ob_depth
            tech_data['btc_correlation'] = btc_corr
            
            # Calculate Trade Scenarios BEFORE AI Call
            current_price = tech_data['price']
            dual_scenarios = calculate_dual_scenarios(
                price=current_price,
                atr=tech_data.get('atr', 0)
            )

            # Get Cached Sentiment Analysis
            sentiment_analysis = sentiment.get_analysis()

            prompt = build_market_prompt(
                symbol, 
                tech_data, 
                sentiment_data, 
                onchain_data, 
                pattern_ctx, 
                dual_scenarios, 
                show_btc_context=show_btc_context,
                sentiment_analysis=sentiment_analysis
            )
            
            logger.info(f"📝 AI PROMPT INPUT for {symbol}:\n{prompt}")

            ai_decision = await ai_brain.analyze_market(prompt)
            
            # Update Candle ID Tracker
            analyzed_candle_ts[symbol] = current_candle_ts
            
            decision = ai_decision.get('decision', 'WAIT').upper()
            confidence = ai_decision.get('confidence', 0)
            reason = html.escape(str(ai_decision.get('reason', '')))

            # --- STEP E: EXECUTION ---
            if decision in ['BUY', 'SELL', 'LONG', 'SHORT']:
                side = 'buy' if decision in ['BUY', 'LONG'] else 'sell'
                
                if confidence >= config.AI_CONFIDENCE_THRESHOLD:
                    await _prepare_and_execute_trade(
                        symbol=symbol,
                        side=side,
                        tech_data=tech_data,
                        coin_cfg=coin_cfg,
                        ai_decision=ai_decision,
                        dual_scenarios=dual_scenarios,
                        btc_corr=btc_corr,
                        show_btc_context=show_btc_context,
                        prompt=prompt,
                        reason=reason
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