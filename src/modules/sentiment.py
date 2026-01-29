import requests
import feedparser
import random
import config
from datetime import datetime
from typing import Optional
from src.utils.helper import logger

class SentimentAnalyzer:
    def __init__(self):
        self.fng_url = config.CMC_FNG_URL
        self.last_fng = {"value": 50, "classification": "Neutral"}
        self.last_news = []       # Backward compat: mixed news
        self.raw_news = []        # Berita mentah (unfiltered)
        self.macro_news_cache = [] # Cache khusus berita makro

    def fetch_fng(self):
        """Fetch Fear & Greed Index from CoinMarketCap"""
        try:
            headers = {
                'X-CMC_PRO_API_KEY': config.CMC_API_KEY,
                'Accept': 'application/json'
            }
            params = {}
            
            if not config.CMC_API_KEY:
                logger.warning("⚠️ CMC_API_KEY not found. Using default neutral sentiment.")
                return

            resp = requests.get(self.fng_url, headers=headers, params=params, timeout=config.API_REQUEST_TIMEOUT)
            data = resp.json()
            
            if 'status' in data and int(data['status']['error_code']) == 0 and 'data' in data:
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
        """Fetch Top News from RSS Feeds dan simpan ke raw_news"""
        rss_urls = getattr(config, 'RSS_FEED_URLS', [])
        if not rss_urls:
            logger.warning("⚠️ No RSS URLs configured in config.")
            return

        all_news = []
        max_per_source = config.NEWS_MAX_PER_SOURCE
        max_age_hours = getattr(config, 'NEWS_MAX_AGE_HOURS', 24) 
        max_total = getattr(config, 'NEWS_MAX_TOTAL', 50)
        
        for url in rss_urls:
            try:
                # logger.info(f"🌐 Fetching RSS: {url}") # Reduced log spam
                response = requests.get(url, timeout=config.API_REQUEST_TIMEOUT)
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    continue

                source_name = feed.feed.get('title', 'Unknown Source')
                
                count = 0
                for entry in feed.entries:
                    if count >= max_per_source:
                        break
                    
                    is_recent = True
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_dt = datetime(*entry.published_parsed[:6])
                            age_seconds = (datetime.utcnow() - published_dt).total_seconds()
                            if age_seconds > (max_age_hours * 3600):
                                is_recent = False
                        except Exception:
                            pass
                    
                    if is_recent:
                        title = entry.title
                        # Clean title
                        title = title.replace('\n', ' ').strip()
                        all_news.append(f"{title} ({source_name})")
                        count += 1
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch RSS {url}: {e}")

        # Shuffle biar variatif sumbernya
        random.shuffle(all_news)
        
        # Simpan ke raw_news 
        self.raw_news = all_news[:max_total]
        
        # Update Macro Cache juga saat fetch
        self._update_macro_cache()
        
        logger.info(f"📰 News Fetched: {len(self.raw_news)} headlines. (Macro: {len(self.macro_news_cache)})")

    def _update_macro_cache(self):
        """Filter dan simpan berita makro terbaru ke cache."""
        macro_keywords = getattr(config, 'MACRO_KEYWORDS', [])
        found = []
        for news in self.raw_news:
            news_lower = news.lower()
            if any(kw in news_lower for kw in macro_keywords):
                found.append(f"[MACRO] {news}")
        
        # Ambil Top N Macro News
        self.macro_news_cache = found[:getattr(config, 'MACRO_NEWS_COUNT', 2)]

    def _get_coin_keywords(self, symbol: str) -> list:
        """Dapatkan keywords dari config.DAFTAR_KOIN."""
        base_coin = symbol.split('/')[0].upper()
        
        # 1. Cari di DAFTAR_KOIN
        for koin in config.DAFTAR_KOIN:
            if koin['symbol'] == symbol or (koin['symbol'].startswith(base_coin + "/")):
                return koin.get('keywords', [base_coin.lower()])
        
        # 2. Fallback default
        return [base_coin.lower()]

    def filter_news_by_relevance(self, symbol: str) -> list:
        """
        Filter berita:
        1. Berita Makro (Wajib, dari cache)
        2. Berita Koin Spesifik
        3. Berita BTC (jika koin bukan BTC, karena BTC king effect)
        """
        if not self.raw_news:
            return []
        
        relevant_news = []
        
        # 1. Masukkan Macro News (Wajib)
        # Clone list agar tidak merubah cache master
        relevant_news.extend(self.macro_news_cache)
        
        # 2. Cari Berita Koin Target & BTC
        base_coin = symbol.split('/')[0].upper()
        is_btc = base_coin == 'BTC'
        
        target_keywords = self._get_coin_keywords(symbol)
        
        # Cari keywords BTC manual jika koin bukan BTC
        btc_keywords = []
        if not is_btc:
            # Cari config BTC
            for koin in config.DAFTAR_KOIN:
                if 'BTC' in koin['symbol']:
                    btc_keywords = koin.get('keywords', ['bitcoin', 'btc'])
                    break
            if not btc_keywords: btc_keywords = ['bitcoin', 'btc']

        coin_specific_news = []
        
        for news in self.raw_news:
            # Skip jika berita sudah ada di macro (cek string exact match)
            # Karena macro news di-prepend prefix [MACRO], kita cek original textnya
            # Tapi raw_news tidak punya prefix.
            # Jadi kita cek logicnya: news ini macro atau bukan?
            
            # Agar simple: kita kumpulkan dulu candidate news, nanti di deduplikasi via set akhir
            # Atau: biarkan duplikat kalau memang overlap (jarang terjadi karena macro keywords beda context)
            
            news_lower = news.lower()
            
            # Match Target
            is_target = any(kw in news_lower for kw in target_keywords)
            
            # Match BTC (hanya jika koin bukan BTC, kalau BTC logicnya masuk is_target)
            is_btc_rel = False
            if not is_btc:
                is_btc_rel = any(kw in news_lower for kw in btc_keywords)
                
            if is_target:
                coin_specific_news.append(news)
            elif is_btc_rel:
                # Berita BTC prioritas kedua
                coin_specific_news.append(f"[BTC-CORR] {news}")
                
        # Batasi jumlah spesifik news agar prompt tidak penuh
        # Sisa slot = TOTAL_LIMIT - Len(Macro)
        limit = config.NEWS_RETENTION_LIMIT
        available_slots = max(0, limit - len(relevant_news))
        
        relevant_news.extend(coin_specific_news[:available_slots])
        
        return relevant_news

    def get_latest(self, symbol: Optional[str] = None) -> dict:
        """
        Get latest sentiment data.
        """
        news_to_display = []
        
        if symbol and self.raw_news:
             news_to_display = self.filter_news_by_relevance(symbol)
        else:
             # Jika tidak ada simbol (Global), tampilkan Macro + Random Top
             news_to_display.extend(self.macro_news_cache)
             remaining = max(0, config.NEWS_RETENTION_LIMIT - len(news_to_display))
             if remaining > 0:
                 news_to_display.extend(self.raw_news[:remaining])

        return {
            "fng_value": self.last_fng['value'],
            "fng_text": self.last_fng['classification'],
            "news": news_to_display
        }

    def update_all(self):
        self.fetch_fng()
        self.fetch_news()
