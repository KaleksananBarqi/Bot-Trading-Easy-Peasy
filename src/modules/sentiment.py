import requests
import feedparser
import random
import asyncio
import aiohttp
import json
import config
from datetime import datetime, timezone
from typing import Optional
from src.utils.helper import logger

class SentimentAnalyzer:
    def __init__(self):
        self.fng_url = config.CMC_FNG_URL
        self.last_fng = {"value": 50, "classification": "Neutral"}
        self.last_news = []       # Backward compat: mixed news
        self.raw_news = []        # Berita mentah (unfiltered)
        self.macro_news_cache = [] # Cache khusus berita makro

        # Optimization: Pre-compute keyword lookups for O(1) access
        self._exact_keywords = {}
        self._base_keywords = {}

        for i, koin in enumerate(config.DAFTAR_KOIN):
            sym = koin['symbol']
            kw = koin.get('keywords', [sym.split('/')[0].lower()])

            # Exact map
            if sym not in self._exact_keywords:
                self._exact_keywords[sym] = (i, kw)

            # Base map (startswith logic)
            parts = sym.split('/')
            if len(parts) > 1 and parts[0]:
                base = parts[0].upper()
                # Store if not already present (first match wins)
                if base not in self._base_keywords:
                    self._base_keywords[base] = (i, kw)
        
        # [NEW] Storage untuk hasil analisa AI (Cache)
        self.analyzed_result = None

    def save_analysis(self, result: dict):
        """Simpan hasil analisa AI yang sudah matang."""
        self.analyzed_result = result
        # Tambahkan timestamp agar tahu kapan terakhir update
        self.analyzed_result['last_updated'] = datetime.now(timezone.utc).timestamp()
        
    def get_analysis(self) -> Optional[dict]:
        """Ambil hasil analisa AI yang tersimpan."""
        return self.analyzed_result

    async def fetch_fng(self, session: aiohttp.ClientSession = None):
        """Fetch Fear & Greed Index from CoinMarketCap (Async)"""
        if not config.CMC_API_KEY:
            logger.warning("⚠️ CMC_API_KEY not found. Using default neutral sentiment.")
            return

        headers = {
            'X-CMC_PRO_API_KEY': config.CMC_API_KEY,
            'Accept': 'application/json'
        }
        params = {}
        
        own_session = session is None
        
        try:
            if own_session:
                session = aiohttp.ClientSession()
            
            timeout = aiohttp.ClientTimeout(total=config.API_REQUEST_TIMEOUT)
            
            async with session.get(
                self.fng_url, 
                headers=headers, 
                params=params, 
                timeout=timeout
            ) as resp:
                data = await resp.json()
                
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

        except aiohttp.ClientError as e:
            logger.warning(f"⚠️ Network error fetching F&G: {type(e).__name__}: {e}")
        except aiohttp.ContentTypeError as e:
            logger.warning(f"⚠️ Invalid JSON response from CMC F&G API: {e}")
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"⚠️ Data parsing error in F&G response: {type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Unexpected error fetching F&G: {type(e).__name__}: {e}")
        finally:
            if own_session and session:
                await session.close()

    async def _fetch_single_rss(self, session: aiohttp.ClientSession, url: str, max_per_source: int, max_age_hours: int) -> list:
        """Fetch single RSS feed secara async."""
        news_items = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=config.API_REQUEST_TIMEOUT)) as response:
                content = await response.read()
                feed = await asyncio.to_thread(feedparser.parse, content)
                
                if not feed.entries:
                    return []

                source_name = feed.feed.get('title', 'Unknown Source')
                
                count = 0
                for entry in feed.entries:
                    if count >= max_per_source:
                        break
                    
                    is_recent = True
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_dt = datetime(*entry.published_parsed[:6])
                            age_seconds = (datetime.now(timezone.utc) - published_dt.replace(tzinfo=timezone.utc)).total_seconds()
                            if age_seconds > (max_age_hours * 3600):
                                is_recent = False
                        except Exception:
                            pass
                    
                    if is_recent:
                        title = entry.title
                        # Clean title
                        title = title.replace('\n', ' ').strip()
                        news_items.append(f"{title} ({source_name})")
                        count += 1
                        
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch RSS {url}: {e}")
        
        return news_items

    async def fetch_news(self):
        """Fetch Top News dari RSS Feeds secara concurrent dan simpan ke raw_news."""
        rss_urls = getattr(config, 'RSS_FEED_URLS', [])
        if not rss_urls:
            logger.warning("⚠️ No RSS URLs configured in config.")
            return

        max_per_source = config.NEWS_MAX_PER_SOURCE
        max_age_hours = getattr(config, 'NEWS_MAX_AGE_HOURS', 24) 
        max_total = getattr(config, 'NEWS_MAX_TOTAL', 50)
        
        # Concurrent fetch dengan aiohttp
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_single_rss(session, url, max_per_source, max_age_hours) 
                for url in rss_urls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Gabungkan hasil dari semua feeds
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
            # Skip exceptions (sudah di-log di _fetch_single_rss)
        
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
        
        # Ambil Top N Macro News (max limit)
        self.macro_news_cache = found[:getattr(config, 'NEWS_MACRO_MAX', 3)]

    def _get_coin_keywords(self, symbol: str) -> list:
        """Dapatkan keywords dari config.DAFTAR_KOIN (Optimized O(1))."""
        base_coin = symbol.split('/')[0].upper()
        
        candidate_exact = self._exact_keywords.get(symbol)
        candidate_base = self._base_keywords.get(base_coin)
        
        # Compare indices to find the first match in the original list
        if candidate_exact and candidate_base:
            # If both match, the one with smaller index appeared earlier
            if candidate_exact[0] <= candidate_base[0]:
                return candidate_exact[1]
            else:
                return candidate_base[1]
        elif candidate_exact:
            return candidate_exact[1]
        elif candidate_base:
            return candidate_base[1]
        else:
            return [base_coin.lower()]

    def filter_news_by_relevance(self, symbol: str) -> list:
        """
        Filter berita dengan enforcement per kategori:
        1. Berita Makro (max NEWS_MACRO_MAX) → Priority 1
        2. Berita Koin Spesifik (min NEWS_COIN_SPECIFIC_MIN) → Priority 2  
        3. Berita BTC (max NEWS_BTC_MAX, hanya jika koin bukan BTC) → Priority 3
        
        Returns:
            list: Berita terfilter dengan label kategori
        """
        if not self.raw_news:
            return []
        
        base_coin = symbol.split('/')[0].upper()
        is_btc = base_coin == 'BTC'
        
        # Get config limits
        macro_max = getattr(config, 'NEWS_MACRO_MAX', 3)
        coin_min = getattr(config, 'NEWS_COIN_SPECIFIC_MIN', 4)
        btc_max = getattr(config, 'NEWS_BTC_MAX', 3)
        total_limit = getattr(config, 'NEWS_RETENTION_LIMIT', 10)
        
        # Get keywords
        target_keywords = self._get_coin_keywords(symbol)
        macro_keywords = getattr(config, 'MACRO_KEYWORDS', [])
        
        btc_keywords = []
        if not is_btc:
            for koin in config.DAFTAR_KOIN:
                if 'BTC' in koin['symbol']:
                    btc_keywords = koin.get('keywords', ['bitcoin', 'btc'])
                    break
            if not btc_keywords:
                btc_keywords = ['bitcoin', 'btc']
        
        # Kategorisasi berita
        macro_news = []
        coin_news = []
        btc_news = []
        
        for news in self.raw_news:
            news_lower = news.lower()
            
            # Check macro first (priority)
            is_macro = any(kw in news_lower for kw in macro_keywords)
            is_coin = any(kw in news_lower for kw in target_keywords)
            is_btc_rel = any(kw in news_lower for kw in btc_keywords) if not is_btc else False
            
            # Categorize (allow overlap for coin-specific)
            if is_macro and len(macro_news) < macro_max:
                macro_news.append(f"[MACRO] {news}")
            
            if is_coin:
                coin_news.append(news)
            elif is_btc_rel and len(btc_news) < btc_max:
                btc_news.append(f"[BTC-CORR] {news}")
        
        # Warning jika berita koin spesifik kurang dari minimum
        # if len(coin_news) < coin_min:
        #     from src.utils.helper import logger
        #     logger.warning(
        #         f"⚠️ Insufficient coin-specific news for {symbol} "
        #         f"(found: {len(coin_news)}, required: {coin_min})"
        #     )
        
        # Gabungkan dengan urutan prioritas: Macro → Coin → BTC
        result = []
        result.extend(macro_news[:macro_max])
        
        # Sisa slot untuk coin + BTC
        remaining_slots = total_limit - len(result)
        
        # Prioritaskan coin news
        coin_to_add = coin_news[:remaining_slots]
        result.extend(coin_to_add)
        
        # Sisa slot untuk BTC (jika ada)
        remaining_slots = total_limit - len(result)
        if remaining_slots > 0 and not is_btc:
            btc_to_add = btc_news[:min(remaining_slots, btc_max)]
            result.extend(btc_to_add)
        
        return result

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

    async def update_all(self):
        """Update semua data sentiment secara concurrent."""
        await asyncio.gather(
            self.fetch_fng(),  # FnG now async with aiohttp
            self.fetch_news()  # RSS sudah async
        )
