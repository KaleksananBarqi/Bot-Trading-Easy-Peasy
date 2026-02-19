
"""
Test suite for AIBrain.analyze_market method.
Tests cover success cases, error handling, malformed JSON, and edge cases.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio

# Adjust path to include src and root
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from src.modules.ai_brain import AIBrain
import config


class TestAIBrainAnalyzeMarket(unittest.TestCase):
    """Comprehensive tests for AIBrain.analyze_market method."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Patch config values
        self.patcher_key = patch.object(config, 'AI_API_KEY', 'dummy_key')
        self.patcher_url = patch.object(config, 'AI_BASE_URL', 'https://test.openrouter.ai/api/v1')
        self.patcher_model = patch.object(config, 'AI_MODEL_NAME', 'test-model')
        self.patcher_temp = patch.object(config, 'AI_TEMPERATURE', 0.0)
        self.patcher_app_url = patch.object(config, 'AI_APP_URL', 'https://test.com')
        self.patcher_app_title = patch.object(config, 'AI_APP_TITLE', 'Test Bot')
        
        self.patcher_key.start()
        self.patcher_url.start()
        self.patcher_model.start()
        self.patcher_temp.start()
        self.patcher_app_url.start()
        self.patcher_app_title.start()

    def tearDown(self):
        """Clean up test fixtures."""
        self.patcher_key.stop()
        self.patcher_url.stop()
        self.patcher_model.stop()
        self.patcher_temp.stop()
        self.patcher_app_url.stop()
        self.patcher_app_title.stop()

    def _create_mock_client(self, response_content, side_effect=None):
        """Helper to create a mocked AsyncOpenAI client."""
        mock_client = MagicMock()
        mock_create = AsyncMock()
        
        if side_effect:
            mock_create.side_effect = side_effect
        else:
            mock_message = MagicMock()
            mock_message.content = response_content
            mock_message.reasoning = None
            
            mock_choice = MagicMock()
            mock_choice.message = mock_message
            
            mock_create.return_value = MagicMock(choices=[mock_choice])
        
        mock_client.chat.completions.create = mock_create
        return mock_client

    # ==========================================================================
    # TEST: No API Key
    # ==========================================================================
    def test_analyze_market_no_api_key(self):
        """Test fallback response when AI_API_KEY is not configured."""
        with patch.object(config, 'AI_API_KEY', None):
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test prompt"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Key Missing")

    # ==========================================================================
    # TEST: Success Cases
    # ==========================================================================
    def test_analyze_market_success_valid_json(self):
        """Test successful parsing of valid JSON response."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "confidence": 85, "reason": "Bullish pattern detected"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Analyze BTC/USDT"))
            
            self.assertEqual(result["decision"], "BUY")
            self.assertEqual(result["confidence"], 85)
            self.assertEqual(result["reason"], "Bullish pattern detected")

    def test_analyze_market_success_with_code_blocks(self):
        """Test parsing of JSON wrapped in markdown code blocks."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '```json\n{"decision": "SELL", "confidence": 70}\n```'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Analyze ETH/USDT"))
            
            self.assertEqual(result["decision"], "SELL")
            self.assertEqual(result["confidence"], 70)

    def test_analyze_market_success_mixed_content(self):
        """Test parsing JSON embedded in mixed text response."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = 'Based on analysis, here is the result:\n{"decision": "WAIT", "confidence": 45, "reason": "Market uncertain"}\nEnd of analysis.'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Analyze market"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 45)

    # ==========================================================================
    # TEST: Missing Fields Handling
    # ==========================================================================
    def test_analyze_market_missing_decision_field(self):
        """Test default WAIT decision when decision field is missing."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"confidence": 60, "reason": "Unclear signal"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 60)

    def test_analyze_market_missing_confidence_field(self):
        """Test default 0 confidence when confidence field is missing."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "reason": "Strong signal"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "BUY")
            self.assertEqual(result["confidence"], 0)

    def test_analyze_market_missing_both_fields(self):
        """Test default values when both decision and confidence are missing."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"reason": "Testing only", "extra": "data"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "Testing only")

    # ==========================================================================
    # TEST: Malformed JSON Handling
    # ==========================================================================
    def test_analyze_market_malformed_json(self):
        """Test error handling when JSON parsing fails."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "confidence":}'  # Invalid JSON
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    def test_analyze_market_no_json_structure(self):
        """Test error handling when no JSON structure is found."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = 'This is just plain text without any JSON structure'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    def test_analyze_market_empty_response(self):
        """Test error handling when AI returns empty response."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = ''
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    # ==========================================================================
    # TEST: API Exception Handling
    # ==========================================================================
    def test_analyze_market_api_exception(self):
        """Test error handling when API call raises exception."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_client = MagicMock()
            mock_create = AsyncMock(side_effect=Exception("API Rate Limit Exceeded"))
            mock_client.chat.completions.create = mock_create
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    def test_analyze_market_network_timeout(self):
        """Test error handling for network timeout."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            import asyncio as asyncio_lib
            mock_client = MagicMock()
            mock_create = AsyncMock(side_effect=asyncio_lib.TimeoutError("Connection timeout"))
            mock_client.chat.completions.create = mock_create
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    def test_analyze_market_client_initialization_error(self):
        """Test error handling when AsyncOpenAI client fails to initialize."""
        # When AsyncOpenAI raises exception during __init__, it propagates up
        # The analyze_market method won't be called in this case
        with patch('src.modules.ai_brain.AsyncOpenAI', side_effect=Exception("Invalid API Key")):
            with self.assertRaises(Exception) as context:
                brain = AIBrain()
            
            self.assertIn("Invalid API Key", str(context.exception))

    # ==========================================================================
    # TEST: Complex JSON Edge Cases
    # ==========================================================================
    def test_analyze_market_nested_json(self):
        """Test parsing of nested JSON with extra data."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "confidence": 75, "reason": "Test", "nested": {"key": "value"}}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "BUY")
            self.assertEqual(result["confidence"], 75)
            self.assertIn("nested", result)

    def test_analyze_market_multiple_json_objects(self):
        """Test handling when AI returns multiple JSON objects (greedy regex matches all)."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            # The regex r"\{.*\}" is greedy and will match from first { to last }
            # This causes JSON parse error due to extra data after first object
            mock_response = '{"decision": "BUY", "confidence": 80} some text {"decision": "SELL", "confidence": 90}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            # Greedy regex causes parse error - returns error response
            self.assertEqual(result["decision"], "WAIT")
            self.assertEqual(result["confidence"], 0)
            self.assertEqual(result["reason"], "AI Error")

    def test_analyze_market_special_characters_in_response(self):
        """Test handling of special characters in JSON response."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "confidence": 85, "reason": "Bullish breakout above $50,000 resistance!"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "BUY")
            self.assertEqual(result["confidence"], 85)
            self.assertIn("$50,000", result["reason"])

    def test_analyze_market_unicode_content(self):
        """Test handling of unicode characters in response."""
        with patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            mock_response = '{"decision": "BUY", "confidence": 90, "reason": "市场看涨信号 🚀"}'
            mock_client = self._create_mock_client(mock_response)
            MockClient.return_value = mock_client
            
            brain = AIBrain()
            result = asyncio.run(brain.analyze_market("Test"))
            
            self.assertEqual(result["decision"], "BUY")
            self.assertEqual(result["confidence"], 90)
            self.assertIn("🚀", result["reason"])


if __name__ == '__main__':
    unittest.main()
