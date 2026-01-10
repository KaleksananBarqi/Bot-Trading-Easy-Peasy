import requests
import feedparser
import random
import config
from src.utils.helper import logger

class SentimentAnalyzer:
    def __init__(self):
        self.fng_url = config.CMC_FNG_URL
        self.last_fng = {"value": 50, "classification": "Neutral"}
        self.last_news = []

    def fetch_fng(self):
        """Fetch Fear & Greed Index from CoinMarketCap"""
        try:
            headers = {
                'X-CMC_PRO_API_KEY': config.CMC_API_KEY,
                'Accept': 'application/json'
            }
            # Endpoint /latest tidak butuh limit
            params = {}
            
            if not config.CMC_API_KEY:
                logger.warning("⚠️ CMC_API_KEY not found. Using default neutral sentiment.")
                return

            resp = requests.get(self.fng_url, headers=headers, params=params, timeout=config.API_REQUEST_TIMEOUT)
            data = resp.json()
            
            # Error code bisa integer 0 atau string "0"
            if 'status' in data and int(data['status']['error_code']) == 0 and 'data' in data:
                # Handle response format (bisa dict atau list tergantung endpoint)
                if isinstance(data['data'], list) and len(data['data']) > 0:
                    item = data['data'][0]
                elif isinstance(data['data'], dict):
                    item = data['data']
                else:
                    logger.warning(f"⚠️ CMC API Unexpected Data Format: {data['data']}")
                    return

                self.last_fng = {
                    "value": int(item['value']),
                    "classification": item['value_classification']
                }
                logger.info(f"🧠 Sentiment F&G (CMC): {self.last_fng['value']} ({self.last_fng['classification']})")
            else:
                error_msg = data.get('status', {}).get('error_message')
                logger.warning(f"⚠️ CMC API Error: {error_msg if error_msg else data}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch F&G: {e}")

    def fetch_news(self):
        """Fetch Top News from RSS Feeds"""
        rss_urls = getattr(config, 'RSS_FEED_URLS', [])
        if not rss_urls:
            logger.warning("⚠️ No RSS URLs configured in config.")
            return

        all_news = []
        max_per_source = config.NEWS_MAX_PER_SOURCE # Ambil sedikit per source agar variatif
        
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
        self.last_news = all_news[:config.NEWS_RETENTION_LIMIT]
        
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
