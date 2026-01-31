import sys
import os
import unittest

# Add project root and src to path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

from src.modules.sentiment import SentimentAnalyzer
import logging

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class TestNewsRetrieval(unittest.TestCase):
    def test_fetch_news_output(self):
        """
        Test manual untuk melihat output berita yang diambil dari RSS feed.
        """
        print("\n" + "="*50)
        print("TESTING NEWS RETRIEVAL FROM RSS SOURCES")
        print("="*50)
        
        analyzer = SentimentAnalyzer()
        
        print("Fetching news... (this might take a few seconds)")
        analyzer.fetch_news()
        
        # Versi terbaru menggunakan get_latest() untuk mengambil berita yang sudah terfilter/diformalisasi
        sentiment_data = analyzer.get_latest()
        news_list = sentiment_data.get('news', [])
        
        print(f"\n[RESULT] Retrieved {len(news_list)} headlines:\n")
        
        if not news_list:
            print("⚠️ No news fetched! Check internet connection or RSS URLs in config.")
        
        for i, news in enumerate(news_list, 1):
            print(f"{i}. {news}")
            
        print("\n" + "="*50)
        
        # Assertion sederhana
        if len(news_list) > 0:
            self.assertTrue(len(news_list) > 0)
        else:
            print("WARNING: 0 News fetched. Verification incomplete.")

if __name__ == "__main__":
    unittest.main()
