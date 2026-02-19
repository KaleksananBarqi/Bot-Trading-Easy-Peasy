import json
import os
import asyncio
import config
from src.utils.helper import logger

class TradeTracker:
    """
    Manages the state of active and pending trades via a JSON file.
    Responsibilities:
    - Load/Save tracker data.
    - CRUD operations for trade metadata.
    """
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        """Load tracker from disk."""
        if os.path.exists(config.TRACKER_FILENAME):
            try:
                with open(config.TRACKER_FILENAME, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tracker: {e}")
                self.data = {}
        else:
            self.data = {}

    async def save(self):
        """Async save tracker to disk (non-blocking)."""
        try:
            await asyncio.to_thread(self._save_sync)
        except Exception as e:
            logger.error(f"⚠️ Gagal save tracker: {e}")

    def _save_sync(self):
        """Sync actual write to file."""
        with open(config.TRACKER_FILENAME, 'w') as f:
            json.dump(self.data, f, indent=2, sort_keys=True)

    def get(self, symbol):
        return self.data.get(symbol)

    def set(self, symbol, data):
        self.data[symbol] = data

    def update(self, symbol, updates):
        if symbol in self.data:
            self.data[symbol].update(updates)

    def delete(self, symbol):
        if symbol in self.data:
            del self.data[symbol]

    def exists(self, symbol):
        return symbol in self.data
