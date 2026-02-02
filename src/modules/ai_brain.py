
from openai import OpenAI
import json
import config
from src.utils.helper import logger
import re

class AIBrain:
    def __init__(self):
        if config.AI_API_KEY:
            import httpx
            self.client = OpenAI(
                base_url=config.AI_BASE_URL,
                api_key=config.AI_API_KEY,
                http_client=httpx.Client()
            )
            self.model_name = config.AI_MODEL_NAME
            logger.info(f"🧠 AI Brain Initialized: {self.model_name} via OpenRouter")
            if getattr(config, 'AI_REASONING_ENABLED', False):
                logger.info(f"🧠 Reasoning Feature ENABLED (Effort: {config.AI_REASONING_EFFORT})")
        else:
            self.client = None
            logger.warning("⚠️ AI_API_KEY not found. AI Brain is disabled.")

    def _build_reasoning_config(self):
        """
        Build reasoning configuration berdasarkan config.
        Return None jika reasoning dinonaktifkan.
        """
        if not getattr(config, 'AI_REASONING_ENABLED', False):
            return None
        
        reasoning_config = {
            "reasoning": {
                "enabled": True, # Explicitly enable
                "effort": getattr(config, 'AI_REASONING_EFFORT', 'medium'),
                "exclude": getattr(config, 'AI_REASONING_EXCLUDE', False)
            }
        }
        return reasoning_config

    async def analyze_market(self, prompt_text):
        """
        Send prompt to AI and parse JSON response.
        """
        if not self.client:
            return {"decision": "WAIT", "confidence": 0, "reason": "AI Key Missing"}

        try:
            # Generate Content
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": config.AI_APP_URL, 
                    "X-Title": config.AI_APP_TITLE, 
                },
                extra_body=self._build_reasoning_config(),
                model=self.model_name,
                messages=[ 
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ],
                temperature=config.AI_TEMPERATURE
            )

            # [LOGGING REASONING]
            if getattr(config, 'AI_LOG_REASONING', False):
                try:
                    msg_obj = completion.choices[0].message
                    # Coba berbagai kemungkinan field reasoning (tergantung SDK & Provider)
                    r_content = getattr(msg_obj, 'reasoning', None)
                    if not r_content: r_content = getattr(msg_obj, 'reasoning_content', None) 
                    if not r_content: # Cek di model_dump/extra jika pakai pydantic model underlying
                        model_extra = getattr(msg_obj, 'model_extra', {}) or {}
                        r_content = model_extra.get('reasoning') or model_extra.get('reasoning_content')
                    
                    if r_content:
                        logger.info(f"🧠💭 [AI REASONING START]\n{r_content}\n🧠💭 [AI REASONING END]")
                except Exception as e_reason:
                    logger.warning(f"⚠️ Failed to extract/log reasoning: {e_reason}")
            
            # Text Cleaning (Robust Regex)
            raw_text = completion.choices[0].message.content
            
            # Cari substring yang diawali '{' dan diakhiri '}'
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            
            if match:
                cleaned_text = match.group(0)
                # Parse JSON
                decision_json = json.loads(cleaned_text)
            else:
                # Fallback simple clean if regex fails (though unlikely if JSON exists)
                cleaned_text = raw_text.replace('```json', '').replace('```', '').strip()
                decision_json = json.loads(cleaned_text)
            
            # Standardize Output
            if "decision" not in decision_json: decision_json["decision"] = "WAIT"
            if "confidence" not in decision_json: decision_json["confidence"] = 0
            
            logger.info(f"🧠 AI Response: {decision_json['decision']} ({decision_json['confidence']}%) - {decision_json.get('reason','')}")
            return decision_json

        except Exception as e:
            # Safe raw_text access for logging
            raw_text_snippet = raw_text[:200] if 'raw_text' in locals() and raw_text else "None"
            logger.error(f"❌ AI Analysis Failed: {e}. Raw Text snippet: {raw_text_snippet}...")
            return {"decision": "WAIT", "confidence": 0, "reason": "AI Error"}

    async def analyze_sentiment(self, prompt_text):
        """
        Khusus untuk Sentiment Analysis (Output: analysis='sentiment')
        Menggunakan Model yang lebih murah (config.AI_SENTIMENT_MODEL)
        """
        if not self.client:
            return None

        # Tentukan Model: Gunakan config khusus jika ada, jika tidak fallback ke default model
        target_model = getattr(config, 'AI_SENTIMENT_MODEL', self.model_name)
        
        try:
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": config.AI_APP_URL, 
                    "X-Title": config.AI_APP_TITLE, 
                },
                model=target_model,
                messages=[{"role": "user", "content": prompt_text}],
                # Sentiment boleh lebih kreatif sedikit
                temperature=0.3 
            )
            
            raw_text = completion.choices[0].message.content
            
            # Cleaning JSON
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                cleaned_text = match.group(0)
                decision_json = json.loads(cleaned_text)
            else:
                cleaned_text = raw_text.replace('```json', '').replace('```', '').strip()
                decision_json = json.loads(cleaned_text)
                
            logger.info(f"🧠 Sentiment Analysis Done via {target_model}")
            return decision_json

        except Exception as e:
            logger.error(f"❌ Sentiment Analysis Failed: {e}")
            return None
