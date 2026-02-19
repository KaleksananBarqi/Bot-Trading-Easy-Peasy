import time
import ccxt.async_support as ccxt
import config
from src.utils.helper import logger, kirim_tele

class OrderManager:
    """
    Manages Order Execution (Entry).
    Responsibilities:
    - Execute Market/Limit Orders.
    - Interact with RiskManager for Cooldowns.
    - Save initial state to TradeTracker.
    """
    def __init__(self, exchange, tracker, risk_manager):
        self.exchange = exchange
        self.tracker = tracker
        self.risk = risk_manager

    async def execute_entry(self, symbol, side, order_type, price, amount_usdt, leverage, strategy_tag, atr_value=0, ai_prompt=None, ai_reason=None, technical_data=None, config_snapshot=None):
        """
        Eksekusi open posisi (Market/Limit).
        """
        # 1. Cek Cooldown
        if self.risk.is_under_cooldown(symbol):
            remaining = self.risk.get_remaining_cooldown(symbol)
            logger.info(f"🛑 {symbol} is in Cooldown ({remaining}s remaining). Skip Entry.")
            return

        try:
            # 2. Set Leverage & Margin
            try:
                await self.exchange.set_leverage(leverage, symbol)
                await self.exchange.set_margin_mode(config.DEFAULT_MARGIN_TYPE, symbol)
            except ccxt.BaseError as e:
                err_msg = str(e).lower()
                if "already set" not in err_msg and "no need to change" not in err_msg:
                    logger.warning(f"⚠️ Leverage/Margin setup skipped for {symbol}: {e}")

            # 3. Hitung Qty
            if price is None or price == 0:
                ticker = await self.exchange.fetch_ticker(symbol)
                price_exec = ticker['last']
            else:
                price_exec = price

            qty = (amount_usdt * leverage) / price_exec
            qty = self.exchange.amount_to_precision(symbol, qty)

            logger.info(f"🚀 EXECUTING: {symbol} | {side} | ${amount_usdt} | x{leverage} | ATR: {atr_value}")

            # 4. Create Order
            if order_type.lower() == 'limit':
                order = await self.exchange.create_order(symbol, 'limit', side, qty, price_exec)
                
                # Save to tracker as WAITING_ENTRY
                self.tracker.set(symbol, {
                    "status": "WAITING_ENTRY",
                    "entry_id": str(order['id']),
                    "created_at": time.time(),
                    "expires_at": time.time() + config.LIMIT_ORDER_EXPIRY_SECONDS,
                    "strategy": strategy_tag,
                    "order_type": order_type.upper(),
                    "atr_value": atr_value,
                    "ai_prompt": ai_prompt,
                    "ai_reason": ai_reason,
                    "technical_data": technical_data or {},
                    "config_snapshot": config_snapshot or {}
                })
                await self.tracker.save()
                await kirim_tele(f"⏳ <b>LIMIT PLACED ({strategy_tag})</b>\n{symbol} {side} @ {price_exec:.4f}\n(Trap SL set by ATR: {atr_value:.4f})")

            else: # MARKET
                # [FIX RACE CONDITION]
                # Simpan metadata SEBELUM order dilempar
                self.tracker.set(symbol, {
                    "status": "PENDING", 
                    "strategy": strategy_tag,
                    "order_type": order_type.upper(),
                    "atr_value": atr_value,
                    "created_at": time.time(),
                    "filled_at": time.time(),
                    "ai_prompt": ai_prompt,
                    "ai_reason": ai_reason,
                    "technical_data": technical_data or {},
                    "config_snapshot": config_snapshot or {}
                })
                await self.tracker.save()

                try:
                    order = await self.exchange.create_order(symbol, 'market', side, qty)
                    await kirim_tele(f"✅ <b>MARKET FILLED</b>\n{symbol} {side} (Size: ${amount_usdt*leverage:.2f})")
                except Exception as e:
                    # [ROLLBACK] Jika order gagal, hapus dari tracker
                    logger.error(f"❌ Market Order Failed {symbol}, rolling back tracker...")
                    self.tracker.delete(symbol)
                    await self.tracker.save()
                    raise e

        except Exception as e:
            logger.error(f"❌ Entry Failed {symbol}: {e}")
            await kirim_tele(f"❌ <b>ENTRY ERROR</b>\n{symbol}: {e}", alert=True)
