
import unittest
import sys
import os
import importlib
from unittest.mock import patch

# Ensure src is in path
sys.path.insert(0, os.path.abspath("src"))

import config
from src.utils import helper

class TestHelperOptimization(unittest.TestCase):
    def test_get_coin_config_exists(self):
        """Test that get_coin_config returns the correct config for an existing coin."""
        # Pick a symbol from config.DAFTAR_KOIN
        if not config.DAFTAR_KOIN:
            self.skipTest("DAFTAR_KOIN is empty")

        target_coin = config.DAFTAR_KOIN[0]
        symbol = target_coin['symbol']

        result = helper.get_coin_config(symbol)
        self.assertEqual(result, target_coin)

    def test_get_coin_config_not_found(self):
        """Test that get_coin_config returns None for a non-existent coin."""
        symbol = "NON_EXISTENT_COIN/USDT"
        result = helper.get_coin_config(symbol)
        self.assertIsNone(result)

    def test_coin_config_map_populated(self):
        """Verify that _COIN_CONFIG_MAP is populated correctly."""
        self.assertTrue(hasattr(helper, '_COIN_CONFIG_MAP'))

        unique_symbols = set(c['symbol'] for c in config.DAFTAR_KOIN)
        self.assertEqual(len(helper._COIN_CONFIG_MAP), len(unique_symbols))

        for coin in config.DAFTAR_KOIN:
            symbol = coin['symbol']
            self.assertIn(symbol, helper._COIN_CONFIG_MAP)

    def test_duplicate_handling_preserves_first(self):
        """Test that if duplicates exist in config, the first one is preserved."""
        # Create a mock config with duplicates
        mock_coins = [
            {"symbol": "DUP/USDT", "id": 1},
            {"symbol": "DUP/USDT", "id": 2}, # Should be ignored
            {"symbol": "UNIQUE/USDT", "id": 3}
        ]

        # Ensure we restore the module state after this test, even if it fails
        self.addCleanup(importlib.reload, helper)

        # Patch config.DAFTAR_KOIN
        with patch('config.DAFTAR_KOIN', mock_coins):
            # Reload helper to re-run the module-level code
            importlib.reload(helper)

            # Verify behavior
            dup_config = helper.get_coin_config("DUP/USDT")
            self.assertIsNotNone(dup_config)
            self.assertEqual(dup_config['id'], 1, "Should preserve the first occurrence")

            unique_config = helper.get_coin_config("UNIQUE/USDT")
            self.assertIsNotNone(unique_config)
            self.assertEqual(unique_config['id'], 3)

            self.assertEqual(len(helper._COIN_CONFIG_MAP), 2)

if __name__ == '__main__':
    unittest.main()
