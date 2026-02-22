"""
OrderUpdateHandler — Menghandle semua callback WebSocket terkait order update.

Diextrak dari main.py untuk menghilangkan dependensi pada variabel global
`executor` dan `journal`. Semua dependensi di-inject via constructor.
"""

import asyncio
import time
from datetime import datetime

import config
from src.utils.helper import logger, kirim_tele, get_coin_leverage


class OrderUpdateHandler:
    """
    Menghandle order updates dari WebSocket (FILLED, CANCELED, EXPIRED).
    
    Mendelegasikan ke handler spesifik berdasarkan status order.
    Dependensi (executor, journal) di-inject via constructor.
    """

    def __init__(self, executor, journal):
        """
        Args:
            executor: Instance OrderExecutor untuk operasi trading
            journal: Instance TradeJournal untuk logging trade
        """
        self.executor = executor
        self.journal = journal

    # ------------------------------------------------------------------
    # PUBLIC CALLBACK (entry point untuk WebSocket)
    # ------------------------------------------------------------------

    async def order_update_cb(self, payload):
        """
        Handle order updates dari WebSocket (FILLED, CANCELED, EXPIRED).
        Dispatcher utama yang mendelegasikan ke handler spesifik.
        """
        o = payload['o']
        sym = o['s'].replace('USDT', '/USDT')
        status = o['X']

        if status == 'CANCELED':
            await self._handle_order_cancelled(sym, o)
        elif status == 'EXPIRED':
            await self._handle_order_expired(sym, o)
        elif status == 'FILLED':
            rp = float(o.get('rp', 0))
            logger.info(f"⚡ Order Filled: {sym} {o['S']} @ {o['ap']} | RP: {rp}")

            if rp != 0:
                # Position Close (Realized Profit != 0)
                await self._handle_position_close(sym, o)
            else:
                # Entry Fill (RP = 0)
                await self._handle_entry_fill(sym, o)

            # Trigger safety check immediately
            await self.executor.sync_positions()

    # ------------------------------------------------------------------
    # PRIVATE HANDLERS
    # ------------------------------------------------------------------

    async def _handle_order_cancelled(self, sym, o):
        """Handle CANCELED order dari WebSocket event."""
        order_id = str(o.get('i', ''))

        # Check if this is our tracked order
        tracker = self.executor.safety_orders_tracker.get(sym, {})
        tracked_id = str(tracker.get('entry_id', ''))

        if tracked_id == order_id:
            # This is our limit entry order - was cancelled manually
            logger.info(f"🗑️ Order CANCELED manually: {sym} (ID: {order_id})")

            # Log to journal as CANCELLED
            trade_data = self._build_non_filled_trade_data(sym, tracker, 'CANCELLED')
            if self.journal:
                self.journal.log_trade(trade_data)

            await self.executor.remove_from_tracker(sym)
            await kirim_tele(
                f"🗑️ <b>ORDER CANCELED</b>\n"
                f"Order {sym} dibatalkan secara manual.\n"
                f"Tracker cleaned & Logged to Journal."
            )
        else:
            # Not our tracked order (could be SL/TP or other) - just log
            logger.debug(f"🔔 Order canceled (non-entry): {sym} ID {order_id}")

    async def _handle_order_expired(self, sym, o):
        """Handle EXPIRED order dari WebSocket event."""
        order_id = str(o.get('i', ''))

        # Check if this is our tracked order
        tracker = self.executor.safety_orders_tracker.get(sym, {})
        tracked_id = str(tracker.get('entry_id', ''))

        if tracked_id == order_id:
            logger.info(f"⏰ Order EXPIRED/TIMEOUT: {sym} (ID: {order_id})")

            # Log to journal as TIMEOUT
            trade_data = self._build_non_filled_trade_data(sym, tracker, 'TIMEOUT')
            if self.journal:
                self.journal.log_trade(trade_data)

            await self.executor.remove_from_tracker(sym)
            await kirim_tele(
                f"⏰ <b>ORDER EXPIRED</b>\n"
                f"Limit Order {sym} kadaluarsa (timeout).\n"
                f"Tracker cleaned & Logged to Journal."
            )
        else:
            logger.debug(f"🔔 Order expired (non-entry): {sym} ID {order_id}")

    async def _handle_position_close(self, sym, o):
        """
        Handle FILLED order yang menutup posisi (Realized Profit != 0).
        Mengatur cooldown, kirim notifikasi PnL, dan log ke journal.
        """
        rp = float(o.get('rp', 0))
        price = float(o.get('ap', 0))
        order_type = o.get('o', 'UNKNOWN')
        order_info = o
        symbol = sym
        pnl = rp

        # COOLDOWN LOGIC BASED ON RESULT (Profit/Loss)
        if pnl > 0:
            self.executor.set_cooldown(sym, config.COOLDOWN_IF_PROFIT)
        else:
            self.executor.set_cooldown(sym, config.COOLDOWN_IF_LOSS)

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
        tracker = self.executor.safety_orders_tracker.get(symbol, {})
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

        # --- EXIT TYPE DETECTION ---
        exit_type_map = {
            'STOP_MARKET': 'STOP_LOSS',
            'TAKE_PROFIT_MARKET': 'TAKE_PROFIT',
            'TRAILING_STOP_MARKET': 'TRAILING_STOP',
            'MARKET': 'MANUAL',
            'LIMIT': 'LIMIT',
        }
        exit_type = exit_type_map.get(order_type, order_type)

        # --- TRAILING METADATA (captured before tracker cleanup) ---
        trailing_was_active = tracker.get('trailing_active', False)
        trailing_sl_final = tracker.get('trailing_sl', 0)
        trailing_high = tracker.get('trailing_high', 0)
        trailing_low = tracker.get('trailing_low', 0)
        activation_price = tracker.get('activation_price', 0)
        sl_price_initial = tracker.get('sl_price_initial', 0)

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
            'config_snapshot': cfg_snapshot,
            'exit_type': exit_type,
            'trailing_was_active': trailing_was_active,
            'trailing_sl_final': trailing_sl_final,
            'trailing_high': trailing_high,
            'trailing_low': trailing_low,
            'activation_price': activation_price,
            'sl_price_initial': sl_price_initial,
        }

        if self.journal:
            self.journal.log_trade(trade_data)

        # Clean up tracker immediately
        await self.executor.remove_from_tracker(symbol)

    async def _handle_entry_fill(self, sym, o):
        """
        Handle FILLED limit entry order (RP = 0).
        Update tracker, kirim notifikasi, dan aktifkan native trailing jika dikonfigurasi.
        """
        order_type = o.get('o', 'UNKNOWN')
        if order_type != 'LIMIT':
            return

        price_filled = float(o.get('ap', 0))
        qty_filled = float(o.get('q', 0))
        side_filled = o['S']  # BUY/SELL
        size_usdt = qty_filled * price_filled

        # Update Tracker with FILLED time
        if sym in self.executor.safety_orders_tracker:
            self.executor.safety_orders_tracker[sym]['filled_at'] = time.time()
            await self.executor.save_tracker()

        # Calculate TP/SL for Notification
        tracker = self.executor.safety_orders_tracker.get(sym, {})
        atr_val = tracker.get('atr_value', 0)

        tp_str = "-"
        sl_str = "-"
        rr_str = "-"
        tp_price_float = 0  # Untuk dikirim ke trailing delayed

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
            tp_price_float = tp_p

            rr = dist_tp / dist_sl if dist_sl > 0 else 0
            rr_str = f"1:{rr:.2f}"

        # NATIVE TRAILING LOGIC
        trailing_note = ""
        if config.USE_NATIVE_TRAILING:
            trailing_note = f"\n⏳ <b>Native Trailing:</b> Activating in {config.TRAILING_ACTIVATION_DELAY}s..."
            # Import here to avoid circular dependency
            from src.main import activate_native_trailing_delayed
            asyncio.create_task(activate_native_trailing_delayed(sym, side_filled, qty_filled, price_filled, tp_price_float))

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

    # ------------------------------------------------------------------
    # STATIC HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _build_non_filled_trade_data(sym, tracker, result_status):
        """
        Build trade data dict untuk order yang CANCELLED atau TIMEOUT (tidak pernah filled).
        
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
