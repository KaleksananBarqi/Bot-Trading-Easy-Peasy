import requests
import feedparser
import random
import config
from src.utils.helper import logger

class SentimentAnalyzer:
    def __init__(self):
        self.fng_url = "https://api.alternative.me/fng/"
        self.last_fng = {"value": 50, "classification": "Neutral"}
        self.last_news = []

    def fetch_fng(self):
        """Fetch Fear & Greed Index"""
        try:
            resp = requests.get(self.fng_url, timeout=10)
            data = resp.json()
            if data['data']:
                item = data['data'][0]
                self.last_fng = {
                    "value": int(item['value']),
                    "classification": item['value_classification']
                }
                logger.info(f"🧠 Sentiment F&G: {self.last_fng['value']} ({self.last_fng['classification']})")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch F&G: {e}")

    def fetch_news(self):
        """Fetch Top News from RSS Feeds"""
        rss_urls = getattr(config, 'RSS_FEED_URLS', [])
        if not rss_urls:
            logger.warning("⚠️ No RSS URLs configured in config.")
            return

        all_news = []
        max_per_source = 2 # Ambil sedikit per source agar variatif
        
        # Shuffle URLs agar tidak melulu sumber yang sama di awal jika list panjang
        # Tapi karena kita iterasi semua, shuffle tidak terlalu penting untuk fetch,
        # tapi penting jika kita membatasi total request (tapi disini kita request semua).
        # Kita request semua tapi batasi items.
        
        for url in rss_urls:
            try:
                # Parse RSS
                feed = feedparser.parse(url)
                
                # Check status (bozo bit)
                if feed.bozo and hasattr(feed, 'bozo_exception'):
                     # logger.warning(f"⚠️ RSS Parse Error {url}: {feed.bozo_exception}")
                     # Lanjut saja, best effort extraction
                     pass
                     
                if not feed.entries:
                    continue

                source_name = feed.feed.get('title', 'Unknown Source')
                
                # Ambil N berita terbaru dari source ini
                for entry in feed.entries[:max_per_source]:
                    title = entry.title
                    # Format: "Judul Berita (Sumber)"
                    all_news.append(f"{title} ({source_name})")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch RSS {url}: {e}")

        # Acak hasil gabungan agar prompt mendapat variasi topik
        random.shuffle(all_news)
        
        # Batasi total berita yang disimpan (misal top 15) agar prompt tidak kepanjangan
        self.last_news = all_news[:15]
        
        logger.info(f"📰 News Fetched: {len(self.last_news)} headlines aggregated from RSS.")

    def get_latest(self):
        return {
            "fng_value": self.last_fng['value'],
            "fng_text": self.last_fng['classification'],
            "news": self.last_news
        }

    def update_all(self):
        self.fetch_fng()
        self.fetch_news()
