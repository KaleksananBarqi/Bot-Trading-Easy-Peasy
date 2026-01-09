
import config
from src.utils.helper import logger

class OnChainAnalyzer:
    def __init__(self):
        self.whale_transactions = [] # List of strings: "$500k Buy BTC"
        self.stablecoin_inflow = "Neutral" # Neutral, Positive, Negative

    def detect_whale(self, symbol, size_usdt, side):
        """
        Called by WebSocket AggTrade or OrderUpdate to record big trades
        """
        if size_usdt >= config.WHALE_THRESHOLD_USDT:
            emoji = "🐋"
            msg = f"{emoji} {side} {symbol} worth ${size_usdt:,.0f}"
            self.whale_transactions.append(msg)
            # Keep only last 10
            if len(self.whale_transactions) > 10:
               self.whale_transactions.pop(0)
            
            logger.info(f"Detect Whale: {msg}")

    def fetch_stablecoin_inflows(self):
        """
        Placeholder: Fetch data from DefiLlama (requires separate implementation/key).
        For now, we simulate or keep it Neutral to avoid dependencies blocking execution.
        """
        # TODO: Implement DefiLlama API request
        # Endpoint: https://api.llama.fi/charts/stablecoin
        self.stablecoin_inflow = "Neutral"

    def get_latest(self):
        return {
            "whale_activity": self.whale_transactions,
            "stablecoin_inflow": self.stablecoin_inflow
        }
