import unittest
from unittest.mock import MagicMock, patch
import config
from src.modules.sentiment import SentimentAnalyzer

class TestSentimentRefactor(unittest.TestCase):
    def setUp(self):
        # Setup config mock
        self.original_macro_keywords = getattr(config, 'MACRO_KEYWORDS', [])
        self.original_macro_count = getattr(config, 'MACRO_NEWS_COUNT', 2)
        self.original_daftar_koin = config.DAFTAR_KOIN
        
        # Inject test config
        config.MACRO_KEYWORDS = ["test_macro", "fed"]
        config.MACRO_NEWS_COUNT = 2
        config.DAFTAR_KOIN = [
            {"symbol": "BTC/USDT", "keywords": ["bitcoin", "btc"]},
            {"symbol": "SOL/USDT", "keywords": ["solana", "sol"]}
        ]
        
        self.analyzer = SentimentAnalyzer()

    def tearDown(self):
        # Restore config
        config.MACRO_KEYWORDS = self.original_macro_keywords
        config.MACRO_NEWS_COUNT = self.original_macro_count
        config.DAFTAR_KOIN = self.original_daftar_koin

    def test_update_macro_cache(self):
        """Test if macro news are correctly identified and cached"""
        self.analyzer.raw_news = [
            "Bitcoin hits 100k",
            "Fed raises rates (test_macro)",
            "Solana is fast",
            "Inflation is high (fed)", 
            "Random news"
        ]
        
        self.analyzer._update_macro_cache()
        
        # Expecting 2 macro news (limited by MACRO_NEWS_COUNT=2)
        # Found candidates: "Fed raises rates (test_macro)", "Inflation is high (fed)"
        self.assertEqual(len(self.analyzer.macro_news_cache), 2)
        self.assertTrue(any("test_macro" in n for n in self.analyzer.macro_news_cache))
        self.assertTrue(any("[MACRO]" in n for n in self.analyzer.macro_news_cache))

    def test_filter_news_by_relevance(self):
        """Test news filtering for a specific coin"""
        # Set raw news
        self.analyzer.raw_news = [
            "Fed decision incoming (test_macro)",  # Macro 1
            "Another Fed news (fed)",              # Macro 2
            "Bitcoin falls",                       # BTC News
            "Solana pumps",                        # SOL News
            "Ethereum update",                     # Irrelevant
        ]
        self.analyzer._update_macro_cache()
        
        # Test for SOL/USDT
        # Expect: 2 Macro + 1 SOL News + 1 BTC News (Total 4)
        relevant_news = self.analyzer.filter_news_by_relevance("SOL/USDT")
        
        print(f"\nRelevant News for SOL: {relevant_news}")
        
        self.assertTrue(any("Fed decision" in n for n in relevant_news))
        self.assertTrue(any("Solana pumps" in n for n in relevant_news))
        self.assertTrue(any("Bitcoin falls" in n for n in relevant_news)) # BTC logic check
        self.assertFalse(any("Ethereum" in n for n in relevant_news))

if __name__ == '__main__':
    unittest.main()
