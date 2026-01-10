
from openai import OpenAI
import json
import config
from src.utils.helper import logger
import re

class AIBrain:
    def __init__(self):
        if config.AI_API_KEY:
            self.client = OpenAI(
                base_url=config.AI_BASE_URL,
                api_key=config.AI_API_KEY,
            )
            self.model_name = config.AI_MODEL_NAME
            logger.info(f"🧠 AI Brain Initialized: {self.model_name} via OpenRouter")
        else:
            self.client = None
            logger.warning("⚠️ AI_API_KEY not found. AI Brain is disabled.")

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
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ]
            )
            
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
