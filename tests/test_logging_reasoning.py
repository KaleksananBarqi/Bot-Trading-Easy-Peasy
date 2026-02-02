
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio

# Adjust path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
if src_path not in sys.path:
    sys.path.append(src_path)

from src.modules.ai_brain import AIBrain
import config 

class TestReasoningLogging(unittest.TestCase):
    
    def setUp(self):
        self.patcher_key = patch.object(config, 'AI_API_KEY', 'dummy_key')
        self.patcher_key.start()

    def tearDown(self):
        self.patcher_key.stop()

    def test_logging_reasoning_success(self):
        """Test reasoning content logged when AI_LOG_REASONING is True"""
        with patch.object(config, 'AI_REASONING_ENABLED', True), \
             patch.object(config, 'AI_LOG_REASONING', True), \
             patch('src.modules.ai_brain.AsyncOpenAI') as MockClient, \
             patch('src.modules.ai_brain.logger') as MockLogger:
            
            # Setup mock response with reasoning
            mock_message = MagicMock()
            mock_message.content = '{"decision": "BUY"}'
            mock_message.reasoning = "Because line goes up" # OpenRouter style
            
            mock_choice = MagicMock()
            mock_choice.message = mock_message
            
            mock_instance = MockClient.return_value
            # Make create async
            mock_create = AsyncMock()
            mock_create.return_value = MagicMock(choices=[mock_choice])
            mock_instance.chat.completions.create = mock_create
            
            brain = AIBrain()
            asyncio.run(brain.analyze_market("prompt"))
            
            # Verify logger called with reasoning content
            # Check if any call made to logger.info contains the reasoning text
            found = False
            for call in MockLogger.info.call_args_list:
                args, _ = call
                if "Because line goes up" in args[0] and "AI REASONING START" in args[0]:
                    found = True
                    break
            
            self.assertTrue(found, "Reasoning content was not logged!")

    def test_logging_reasoning_fallback(self):
        """Test reasoning content logged via fallback attribute (deepseek style)"""
        with patch.object(config, 'AI_REASONING_ENABLED', True), \
             patch.object(config, 'AI_LOG_REASONING', True), \
             patch('src.modules.ai_brain.AsyncOpenAI') as MockClient, \
             patch('src.modules.ai_brain.logger') as MockLogger:
            
            # Setup mock response with reasoning_content (native)
            mock_message = MagicMock()
            mock_message.content = '{"decision": "BUY"}'
            # Simulate attribute missing 'reasoning' but having 'reasoning_content'
            del mock_message.reasoning 
            mock_message.reasoning_content = "Thinking deeply..."
            # Ensure getattr(msg, 'reasoning') returns None (default mock returns MagicMock)
            # We strictly need to simulate the attribute access behavior.
            # MagicMock default behavior is to create child mocks on access.
            # So getattr(mock, 'reasoning') -> Mock object (which is truthy).
            # We must configure it to be None explicitly if we want to fail the first check.
            mock_message.reasoning = None

            mock_choice = MagicMock()
            mock_choice.message = mock_message
            
            mock_instance = MockClient.return_value
            # Make create async
            mock_create = AsyncMock()
            mock_create.return_value = MagicMock(choices=[mock_choice])
            mock_instance.chat.completions.create = mock_create
            
            brain = AIBrain()
            asyncio.run(brain.analyze_market("prompt"))
            
            found = False
            for call in MockLogger.info.call_args_list:
                args, _ = call
                if "Thinking deeply..." in args[0]:
                    found = True
                    break
            self.assertTrue(found, "Fallback reasoning content was not logged!")

if __name__ == '__main__':
    unittest.main()
