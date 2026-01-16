import io
import base64
import json
import asyncio
import pandas as pd
import mplfinance as mpf
from openai import AsyncOpenAI
import httpx
import config
import matplotlib
matplotlib.use('Agg') # Force non-interactive backend
from src.utils.helper import logger

class PatternRecognizer:
    def __init__(self, market_data_manager):
        self.market_data = market_data_manager
        self.cache = {} # {symbol: {'candle_ts': 12345, 'analysis': "..."}}
        
        # Initialize AI Client for Vision
        if config.USE_PATTERN_RECOGNITION and config.AI_API_KEY:
            self.client = AsyncOpenAI(
                base_url=config.AI_BASE_URL,
                api_key=config.AI_API_KEY,
                http_client=httpx.AsyncClient(),
                default_headers={
                    "HTTP-Referer": config.AI_APP_URL,
                    "X-Title": config.AI_APP_TITLE,
                }
            )
            self.model = config.AI_VISION_MODEL
            logger.info(f"👁️ Pattern Recognizer Initialized: {self.model}")
        else:
            self.client = None
            logger.warning("⚠️ Vision AI Disabled or Key Missing.")

    def get_setup_candles(self, symbol):
        """Retrieve candles for the SETUP timeframe"""
        return self.market_data.market_store.get(symbol, {}).get(config.TIMEFRAME_SETUP, [])

    def generate_chart_image(self, symbol):
        """
        Generate candlestick chart image using mplfinance.
        Returns base64 encoded string.
        """
        candles = self.get_setup_candles(symbol)
        if not candles or len(candles) < 20:
            return None
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Create Buffer
            buf = io.BytesIO()
            
            # Style & Plot
            # rc params for dark mode
            s = mpf.make_mpf_style(base_mpf_style='nightclouds', rc={'font.size': 8})
            
            mpf.plot(
                df.tail(60), # Last 60 candles
                type='candle',
                style=s,
                volume=True,
                savefig=dict(fname=buf, dpi=100, bbox_inches='tight', format='png'),
                axisoff=True, # Hide axis to save tokens (just pure pattern) ? Or keep axis for price context? 
                # Better keep axis for context (Price values matters)
                tight_layout=True
            )
            
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode('utf-8')
            return img_str
            
        except Exception as e:
            logger.error(f"❌ Chart Generation Failed {symbol}: {e}")
            return None

    async def analyze_pattern(self, symbol):
        """
        Main function to get pattern analysis.
        Checks cache first.
        """
        if not self.client or not config.USE_PATTERN_RECOGNITION:
            return "Vision AI Disabled."

        # Check Cache based on last candle timestamp
        candles = self.get_setup_candles(symbol)
        if not candles: return "Not enough data."
        
        last_ts = candles[-1][0] # Timestamp newest candle
        
        # If latest candle is NOT closed yet, we should look at the ONE BEFORE IT for stable pattern?
        # Or usually we analyze the evolving pattern. Let's use current last timestamp as ID.
        # But optimize: only analyze if 'last_ts' is different from cached 'last_ts'. 
        # Since 'candles[-1]' updates every realtime tick (in market_data), we only want to analyze ONCE PER CANDLE or if substantial time passed?
        # Better: analyze once per candle ID. If candle hasn't closed, we might spam request.
        # Strategy: Analyze on NEW candle close? OR periodic timeout?
        # For setup (4h), one analysis per 4h candle is enough.
        
        cached = self.cache.get(symbol)
        if cached and cached['candle_ts'] == last_ts:
            # Return cached analysis
            return cached['analysis']

        logger.info(f"👁️ Recognizing Pattern for {symbol} ({config.TIMEFRAME_SETUP})...")
        
        # Generate Image
        # Run in thread executor to not block async loop (mplfinance is blocking)
        img_base64 = await asyncio.to_thread(self.generate_chart_image, symbol)
        
        if not img_base64:
            return "Failed to generate chart."

        # Call AI
        try:
            prompt_text = (
                f"Analyze this {config.TIMEFRAME_SETUP} chart for {symbol}. "
                "Identify any specific chart patterns (e.g. Head & Shoulders, Flags, Wedges, Double Top/Bottom). "
                "Determine the bias (BULLISH/BEARISH/NEUTRAL) and strength. "
                "Keep it concise (max 2-3 sentences)."
            )
            
            logger.info(f"📤 Sending chart image to Vision AI for {symbol}...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}",
                                    "detail": "low" # Low detail to save tokens, usually enough for patterns
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150,
                temperature=config.AI_VISION_TEMPERATURE
            )
            
            analysis = response.choices[0].message.content
            
            # Update Cache
            self.cache[symbol] = {
                'candle_ts': last_ts,
                'analysis': analysis
            }
            logger.info(f"✅ Pattern Analysis Done {symbol}: {analysis[:50]}...")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Vision AI Error {symbol}: {e}")
            return f"Error: {str(e)}"
