
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio

# Adjust path to include src to allow 'import config' inside helper to work
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.append(src_path)
if root_path not in sys.path:
    sys.path.append(root_path)


from src.modules.ai_brain import AIBrain
# PENTING: Import 'config' langsung, bukan 'src.config', karena ai_brain.py mengimport 'import config'
# Kita harus mempatch module object yang SAMA.
import config 

class TestReasoningConfig(unittest.TestCase):
    
    def setUp(self):
        # Patch config values directly on the 'config' module
        self.patcher_key = patch.object(config, 'AI_API_KEY', 'dummy_key')
        self.patcher_key.start()

        
    def tearDown(self):
        self.patcher_key.stop()

    def test_reasoning_enabled(self):
        """Test jika reasoning enabled, parameter dikirim"""
        with patch.object(config, 'AI_REASONING_ENABLED', True), \
             patch.object(config, 'AI_REASONING_EFFORT', 'high'), \
             patch.object(config, 'AI_REASONING_EXCLUDE', False), \
             patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            
            mock_instance = MockClient.return_value
            # Make create async
            mock_create = AsyncMock()
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"decision": "BUY", "confidence": 90}'))]
            )
            mock_instance.chat.completions.create = mock_create
            
            brain = AIBrain()
            
            # Run async method implementation
            asyncio.run(brain.analyze_market("Test prompt"))
            
            # Check call args
            _, kwargs = mock_instance.chat.completions.create.call_args
            
            self.assertIn('extra_body', kwargs)
            self.assertEqual(kwargs['extra_body']['reasoning']['enabled'], True)
            self.assertEqual(kwargs['extra_body']['reasoning']['effort'], 'high')
            self.assertEqual(kwargs['extra_body']['reasoning']['exclude'], False)

    def test_reasoning_disabled(self):
        """Test jika reasoning disabled, parameter TIDAK dikirim"""
        with patch.object(config, 'AI_REASONING_ENABLED', False), \
             patch('src.modules.ai_brain.AsyncOpenAI') as MockClient:
            
            mock_instance = MockClient.return_value
            # Make create async
            mock_create = AsyncMock()
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"decision": "BUY", "confidence": 90}'))]
            )
            mock_instance.chat.completions.create = mock_create
            
            brain = AIBrain()
            
            # Run async method
            asyncio.run(brain.analyze_market("Test prompt"))
            
            # Check call args
            _, kwargs = mock_instance.chat.completions.create.call_args
            
            self.assertIsNone(kwargs.get('extra_body'))

if __name__ == '__main__':
    unittest.main()
