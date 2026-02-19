import sys
import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
sys.path.append(src_path)


class TestCryptoPnLGeneratorHexToRgb(unittest.TestCase):
    """Test suite for _hex_to_rgb method"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_hex_to_rgb_six_digits(self):
        """Test 6-digit hex color conversion"""
        result = self.generator._hex_to_rgb('#FFFFFF')
        self.assertEqual(result, (255, 255, 255))

    def test_hex_to_rgb_six_digits_black(self):
        """Test 6-digit hex color black"""
        result = self.generator._hex_to_rgb('#000000')
        self.assertEqual(result, (0, 0, 0))

    def test_hex_to_rgb_six_digits_red(self):
        """Test 6-digit hex color red"""
        result = self.generator._hex_to_rgb('#FF0000')
        self.assertEqual(result, (255, 0, 0))

    def test_hex_to_rgb_six_digits_green(self):
        """Test 6-digit hex color green"""
        result = self.generator._hex_to_rgb('#00FF00')
        self.assertEqual(result, (0, 255, 0))

    def test_hex_to_rgb_six_digits_blue(self):
        """Test 6-digit hex color blue"""
        result = self.generator._hex_to_rgb('#0000FF')
        self.assertEqual(result, (0, 0, 255))

    def test_hex_to_rgb_eight_digits_with_alpha(self):
        """Test 8-digit hex color with alpha channel"""
        result = self.generator._hex_to_rgb('#FF000080')
        self.assertEqual(result, (255, 0, 0, 128))

    def test_hex_to_rgb_shorthand_three_digits(self):
        """Test 3-digit shorthand hex color"""
        result = self.generator._hex_to_rgb('#FFF')
        self.assertEqual(result, (255, 255, 255))

    def test_hex_to_rgb_shorthand_four_digits(self):
        """Test 4-digit shorthand hex color with alpha"""
        result = self.generator._hex_to_rgb('#F00F')
        self.assertEqual(result, (255, 0, 0, 255))

    def test_hex_to_rgb_without_hash(self):
        """Test hex color without hash prefix"""
        result = self.generator._hex_to_rgb('FFFFFF')
        self.assertEqual(result, (255, 255, 255))

    def test_hex_to_rgb_mixed_case(self):
        """Test hex color with mixed case"""
        result = self.generator._hex_to_rgb('#AaBbCc')
        self.assertEqual(result, (170, 187, 204))


class TestCryptoPnLGeneratorConfig(unittest.TestCase):
    """Test suite for configuration loading"""

    def test_load_config_file_exists(self):
        """Test loading config from existing file"""
        from src.utils.pnl_generator import CryptoPnLGenerator
        generator = CryptoPnLGenerator()
        self.assertIsInstance(generator.config, dict)

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist"""
        from src.utils.pnl_generator import CryptoPnLGenerator
        with patch('os.path.exists', return_value=False):
            with patch('builtins.open', side_effect=FileNotFoundError):
                generator = CryptoPnLGenerator()
                self.assertEqual(generator.config, {})

    def test_ensure_asset_dirs(self):
        """Test asset directory creation"""
        from src.utils.pnl_generator import CryptoPnLGenerator
        generator = CryptoPnLGenerator()
        self.assertIsNotNone(generator.base_dir)


class TestCryptoPnLGeneratorAssetPath(unittest.TestCase):
    """Test suite for asset path handling"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_get_asset_path_with_valid_path(self):
        """Test getting asset path with valid relative path"""
        result = self.generator._get_asset_path('assets/test.png')
        self.assertIsNotNone(result)
        self.assertIn('assets', result)

    def test_get_asset_path_with_empty_string(self):
        """Test getting asset path with empty string returns None"""
        result = self.generator._get_asset_path('')
        self.assertIsNone(result)

    def test_get_asset_path_with_none(self):
        """Test getting asset path with None returns None"""
        result = self.generator._get_asset_path(None)
        self.assertIsNone(result)


class TestCryptoPnLGeneratorGradient(unittest.TestCase):
    """Test suite for gradient background generation"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_create_gradient_bg_single_color(self):
        """Test gradient with single color"""
        result = self.generator._create_gradient_bg(100, 100, ['#FFFFFF'])
        self.assertEqual(result.size, (100, 100))

    def test_create_gradient_bg_two_colors(self):
        """Test gradient with two colors"""
        result = self.generator._create_gradient_bg(100, 100, ['#000000', '#FFFFFF'])
        self.assertEqual(result.size, (100, 100))

    def test_create_gradient_bg_three_colors(self):
        """Test gradient with three colors"""
        result = self.generator._create_gradient_bg(200, 200, ['#000000', '#808080', '#FFFFFF'])
        self.assertEqual(result.size, (200, 200))

    def test_create_gradient_bg_zero_height(self):
        """Test gradient with zero height returns base image"""
        result = self.generator._create_gradient_bg(100, 0, ['#FFFFFF'])
        self.assertEqual(result.size, (100, 0))


class TestCryptoPnLGeneratorCardGeneration(unittest.TestCase):
    """Test suite for card generation"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def get_sample_trade_data(self):
        """Return sample trade data for testing"""
        return {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.00,
            'exit_price': 55000.00,
            'pnl_usdt': 500.00,
            'roi_percent': 10.0,
            'leverage': 10,
            'strategy': 'Test Strategy'
        }

    def test_generate_card_basic(self):
        """Test basic card generation"""
        trade_data = self.get_sample_trade_data()
        result = self.generator.generate_card(trade_data)
        
        self.assertIsInstance(result, BytesIO)
        self.assertGreater(result.getbuffer().nbytes, 0)

    def test_generate_card_win_scenario(self):
        """Test card generation with winning trade"""
        trade_data = self.get_sample_trade_data()
        trade_data['roi_percent'] = 25.5
        trade_data['pnl_usdt'] = 1275.00
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_loss_scenario(self):
        """Test card generation with losing trade"""
        trade_data = self.get_sample_trade_data()
        trade_data['roi_percent'] = -15.0
        trade_data['pnl_usdt'] = -750.00
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_short_side(self):
        """Test card generation with SHORT side"""
        trade_data = self.get_sample_trade_data()
        trade_data['side'] = 'SHORT'
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_zero_pnl(self):
        """Test card generation with zero PnL"""
        trade_data = self.get_sample_trade_data()
        trade_data['roi_percent'] = 0
        trade_data['pnl_usdt'] = 0
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_large_leverage(self):
        """Test card generation with high leverage"""
        trade_data = self.get_sample_trade_data()
        trade_data['leverage'] = 125
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_missing_optional_fields(self):
        """Test card generation with missing optional fields"""
        trade_data = {
            'symbol': 'ETH/USDT',
            'side': 'LONG',
        }
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_custom_strategy(self):
        """Test card generation with custom strategy name"""
        trade_data = self.get_sample_trade_data()
        trade_data['strategy'] = 'My_Custom_Strategy_2024'
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_strategy_with_underscores(self):
        """Test card generation with underscores in strategy name"""
        trade_data = self.get_sample_trade_data()
        trade_data['strategy'] = 'MACD_RSI_Combined'
        
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_portrait_raises_error(self):
        """Test that portrait mode raises ValueError"""
        from src.utils.pnl_generator import CryptoPnLGenerator
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                'card_settings': {'width': 1080, 'height': 1920},
                'style': {}
            }, f)
            config_path = f.name
        
        try:
            with patch('src.utils.pnl_generator.CryptoPnLGenerator._load_config', return_value={
                'card_settings': {'width': 1080, 'height': 1920},
                'style': {}
            }):
                generator = CryptoPnLGenerator()
                trade_data = self.get_sample_trade_data()
                with self.assertRaises(ValueError) as context:
                    generator.generate_card(trade_data)
                self.assertIn('not supported', str(context.exception))
        finally:
            os.unlink(config_path)


class TestCryptoPnLCropToFill(unittest.TestCase):
    """Test suite for image cropping functionality"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_crop_to_fill_wider_image(self):
        """Test cropping a wider-than-target image"""
        from PIL import Image
        src = Image.new('RGB', (200, 100), (255, 0, 0))
        result = self.generator._crop_to_fill(src, 100, 100)
        self.assertEqual(result.size, (100, 100))

    def test_crop_to_fill_taller_image(self):
        """Test cropping a taller-than-target image"""
        from PIL import Image
        src = Image.new('RGB', (100, 200), (255, 0, 0))
        result = self.generator._crop_to_fill(src, 100, 100)
        self.assertEqual(result.size, (100, 100))


class TestCryptoPnLCalcPanelWidth(unittest.TestCase):
    """Test suite for panel width calculation"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_calc_panel_width_default(self):
        """Test default panel width calculation"""
        result = self.generator._calc_panel_width(1920, 1080)
        min_expected = int(1920 * 0.30)
        max_expected = int(1920 * 0.65)
        self.assertGreaterEqual(result, min_expected)
        self.assertLessEqual(result, max_expected)

    def test_calc_panel_width_minimum_ratio(self):
        """Test panel width respects minimum ratio"""
        result = self.generator._calc_panel_width(1000, 1000)
        min_expected = int(1000 * 0.30)
        self.assertGreaterEqual(result, min_expected)

    def test_calc_panel_width_maximum_ratio(self):
        """Test panel width respects maximum ratio"""
        result = self.generator._calc_panel_width(100, 100)
        max_expected = int(100 * 0.65)
        self.assertLessEqual(result, max_expected)


class TestCryptoPnLGeneratorIntegration(unittest.TestCase):
    """Integration tests for full card generation workflow"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_full_generation_workflow(self):
        """Test complete workflow from data to image"""
        trade_data_list = [
            {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'entry_price': 42000.00,
                'exit_price': 45000.00,
                'pnl_usdt': 300.00,
                'roi_percent': 7.14,
                'leverage': 20,
                'strategy': 'Breakout Strategy'
            },
            {
                'symbol': 'ETH/USDT',
                'side': 'SHORT',
                'entry_price': 2500.00,
                'exit_price': 2400.00,
                'pnl_usdt': 200.00,
                'roi_percent': 8.0,
                'leverage': 15,
                'strategy': 'Mean Reversion'
            },
            {
                'symbol': 'SOL/USDT',
                'side': 'LONG',
                'entry_price': 100.00,
                'exit_price': 95.00,
                'pnl_usdt': -50.00,
                'roi_percent': -5.0,
                'leverage': 5,
                'strategy': 'Scalping'
            }
        ]
        
        for trade_data in trade_data_list:
            result = self.generator.generate_card(trade_data)
            self.assertIsInstance(result, BytesIO)
            self.assertGreater(result.getbuffer().nbytes, 1000)


class TestCryptoPnLGeneratorEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        from src.utils.pnl_generator import CryptoPnLGenerator
        self.generator = CryptoPnLGenerator()

    def test_generate_card_with_extremely_large_pnl(self):
        """Test card generation with very large PnL values"""
        trade_data = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.00,
            'exit_price': 50001.00,
            'pnl_usdt': 999999999.99,
            'roi_percent': 999999.99,
            'leverage': 1,
            'strategy': 'Big Winner'
        }
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_with_small_prices(self):
        """Test card generation with small token prices"""
        trade_data = {
            'symbol': 'DOGE/USDT',
            'side': 'LONG',
            'entry_price': 0.001,
            'exit_price': 0.002,
            'pnl_usdt': 100.00,
            'roi_percent': 100.0,
            'leverage': 10,
            'strategy': 'Micro Cap'
        }
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)

    def test_generate_card_with_max_leverage(self):
        """Test card generation with maximum leverage"""
        trade_data = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.00,
            'exit_price': 55000.00,
            'pnl_usdt': 50000.00,
            'roi_percent': 1000.0,
            'leverage': 125,
            'strategy': 'High Leverage'
        }
        result = self.generator.generate_card(trade_data)
        self.assertIsInstance(result, BytesIO)


if __name__ == '__main__':
    unittest.main()
