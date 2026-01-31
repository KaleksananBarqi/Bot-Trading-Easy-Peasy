"""
Unit Test untuk News Filtering Logic di SentimentAnalyzer
Test ini memvalidasi bahwa berita difilter dengan benar berdasarkan koin.
"""
import sys
import os
import unittest

# Add project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.modules.sentiment import SentimentAnalyzer
import config


class TestNewsFiltering(unittest.TestCase):
    """Test filtering berita berdasarkan relevansi koin"""
    
    def setUp(self):
        """Setup mock data untuk testing"""
        self.analyzer = SentimentAnalyzer()
        # Mock raw news - simulasi output dari RSS feeds
        self.analyzer.raw_news = [
            "Bitcoin surges to new ATH amid ETF inflows (CoinDesk)",
            "PENGU Price Surges Despite 95% Sentiment Drop (TheBlock)",
            "XRP Could Enter New Growth Phase After SEC Ruling (CryptoSlate)",
            "Solana TVL hits $5B milestone as DeFi activity increases (Blockworks)",
            "Ethereum 2.0 staking rewards increase by 10% (BeInCrypto)",
            "Federal Reserve hints at rate cuts in Q2 (Google News)",
            "BTC whale moves $200M to exchange, sparking sell-off fears (U.Today)",
            "Dogecoin sees renewed interest from retail investors (DailyHodl)",
            "Cardano's Hydra upgrade promises 1M TPS (NewsBTC)",
            "Bitcoin miners report record hash rate after halving (Bitcoin.com)",
            "Arbitrum TVL surpasses $3B as layer 2 adoption grows (TheBlock)",
            "Chainlink CCIP expands to 10 new blockchains (CryptoSlate)",
        ]
    
    def test_filter_btc_only_gets_btc_news(self):
        """BTC harus dapat berita BTC saja, tidak termasuk altcoin"""
        result = self.analyzer.filter_news_by_relevance("BTC/USDT")
        
        # Harus ada berita Bitcoin
        btc_news_count = sum(1 for n in result if 'bitcoin' in n.lower() or 'btc' in n.lower())
        self.assertGreater(btc_news_count, 0, "Harusnya ada berita BTC")
        
        # Tidak boleh ada berita altcoin spesifik (tanpa tag [MACRO])
        non_macro_news = [n for n in result if not n.startswith('[MACRO]')]
        self.assertFalse(any("pengu" in n.lower() for n in non_macro_news), "PENGU tidak boleh ada di berita BTC")
        self.assertFalse(any("solana" in n.lower() for n in non_macro_news), "Solana tidak boleh ada di berita BTC")
    
    def test_filter_sol_gets_sol_and_btc(self):
        """SOL harus dapat berita SOL + BTC (karena BTC selalu disertakan)"""
        result = self.analyzer.filter_news_by_relevance("SOL/USDT")
        
        # Harus ada berita Solana
        sol_news = [n for n in result if 'solana' in n.lower() or 'sol' in n.lower()]
        self.assertTrue(len(sol_news) > 0, "Harusnya ada berita Solana")
        
        # Harus ada berita BTC juga (BTC king effect) - ditandai dengan [BTC-CORR]
        btc_news = [n for n in result if 'bitcoin' in n.lower() or 'btc' in n.lower()]
        self.assertTrue(len(btc_news) > 0, "Harusnya ada berita BTC untuk SOL")
        
        # Tidak boleh ada berita XRP dalam berita non-macro
        non_macro_news = [n for n in result if not n.startswith('[MACRO]')]
        # Filter hanya yang bukan BTC-CORR
        coin_only_news = [n for n in non_macro_news if not n.startswith('[BTC-CORR]')]
        self.assertFalse(any("xrp" in n.lower() for n in coin_only_news), "XRP tidak boleh ada di berita SOL")
    
    def test_btc_news_max_limit(self):
        """BTC news harus dibatasi max NEWS_BTC_MAX"""
        btc_max = getattr(config, 'NEWS_BTC_MAX', 3)
        result = self.analyzer.filter_news_by_relevance("SOL/USDT")
        
        # Hitung berita BTC (yang ada tag [BTC-CORR])
        btc_corr_news = [n for n in result if '[BTC-CORR]' in n]
        self.assertLessEqual(len(btc_corr_news), btc_max, 
                            f"BTC news harus max {btc_max}")
    
    def test_macro_news_max_limit(self):
        """Macro news harus dibatasi max NEWS_MACRO_MAX"""
        macro_max = getattr(config, 'NEWS_MACRO_MAX', 3)
        result = self.analyzer.filter_news_by_relevance("BTC/USDT")
        
        # Hitung berita macro (yang ada tag [MACRO])
        macro_news = [n for n in result if '[MACRO]' in n]
        self.assertLessEqual(len(macro_news), macro_max, 
                            f"Macro news harus max {macro_max}")
    
    def test_get_latest_with_symbol_filters(self):
        """get_latest(symbol) harus mengembalikan berita terfilter"""
        result = self.analyzer.get_latest(symbol="SOL/USDT")
        
        self.assertIn('news', result)
        news = result['news']
        
        # Pastikan ada berita
        self.assertTrue(len(news) > 0, "Harusnya ada berita yang dikembalikan")
        
        # Pastikan tidak ada berita XRP dalam berita non-macro/non-BTC
        coin_only_news = [n for n in news if not n.startswith('[MACRO]') and not n.startswith('[BTC-CORR]')]
        self.assertFalse(any("xrp" in n.lower() for n in coin_only_news), "XRP tidak boleh ada")
    
    def test_get_latest_without_symbol_returns_macro_plus_random(self):
        """get_latest() tanpa symbol harus mengembalikan macro + random news"""
        # Setup macro cache
        self.analyzer._update_macro_cache()
        
        result = self.analyzer.get_latest()
        
        self.assertIn('news', result)
        # Harus ada sesuatu dikembalikan
        self.assertIsInstance(result['news'], list)
    
    def test_empty_raw_news_returns_empty(self):
        """Jika raw_news kosong, filter harus return list kosong"""
        self.analyzer.raw_news = []
        result = self.analyzer.filter_news_by_relevance("BTC/USDT")
        
        self.assertEqual(result, [])


class TestNewsFilteringConfig(unittest.TestCase):
    """Test untuk memastikan config filtering tersetup dengan benar"""
    
    def test_config_constants_exist(self):
        """Pastikan konstanta filtering ada di config"""
        self.assertTrue(hasattr(config, 'NEWS_COIN_SPECIFIC_MIN'), 
                       "NEWS_COIN_SPECIFIC_MIN harus ada di config")
        self.assertTrue(hasattr(config, 'NEWS_BTC_MAX'), 
                       "NEWS_BTC_MAX harus ada di config")
        self.assertTrue(hasattr(config, 'NEWS_MACRO_MAX'), 
                       "NEWS_MACRO_MAX harus ada di config")
    
    def test_config_values_are_sensible(self):
        """Pastikan nilai config masuk akal"""
        self.assertGreaterEqual(config.NEWS_COIN_SPECIFIC_MIN, 1)
        self.assertGreaterEqual(config.NEWS_BTC_MAX, 1)
        self.assertGreaterEqual(config.NEWS_MACRO_MAX, 1)
        self.assertLessEqual(config.NEWS_COIN_SPECIFIC_MIN, 10)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTING NEWS FILTERING LOGIC")
    print("="*60 + "\n")
    
    unittest.main(verbosity=2)

