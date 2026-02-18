#!/usr/bin/env python3
"""
Test untuk validasi MONGO_URI configuration.

Test ini memastikan:
1. Config gagal di-import jika MONGO_URI tidak di-set
2. Config gagal di-import jika MONGO_URI memiliki format invalid
3. Config berhasil di-import jika MONGO_URI valid
"""

import os
import sys
import unittest
from unittest.mock import patch


class TestMongoURIValidation(unittest.TestCase):
    """Test suite untuk MONGO_URI validation."""
    
    def setUp(self):
        """Clear any existing MONGO_URI from environment."""
        # Hapus MONGO_URI dari environment jika ada
        if 'MONGO_URI' in os.environ:
            del os.environ['MONGO_URI']
        
        # Remove config from cache if it was imported before
        modules_to_remove = [key for key in sys.modules.keys() if 'config' in key]
        for mod in modules_to_remove:
            del sys.modules[mod]
    
    def tearDown(self):
        """Restore environment after tests."""
        # Cleanup
        modules_to_remove = [key for key in sys.modules.keys() if 'config' in key]
        for mod in modules_to_remove:
            del sys.modules[mod]
    
    def test_missing_mongo_uri_raises_error(self):
        """Test: Import config tanpa MONGO_URI harus raise ValueError."""
        # Pastikan MONGO_URI tidak di-set
        self.assertIsNone(os.environ.get('MONGO_URI'))
        
        # Import config harus gagal
        with self.assertRaises(ValueError) as context:
            # Tambahkan src ke path
            src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            import config
        
        # Verifikasi pesan error
        self.assertIn("MONGO_URI environment variable must be set", str(context.exception))
    
    def test_invalid_mongo_uri_scheme_raises_error(self):
        """Test: MONGO_URI dengan scheme invalid harus raise ValueError."""
        # Set MONGO_URI dengan scheme invalid
        os.environ['MONGO_URI'] = 'http://localhost:27017/'
        
        with self.assertRaises(ValueError) as context:
            src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            # Remove config from cache to force reimport
            if 'config' in sys.modules:
                del sys.modules['config']
            import config
        
        # Verifikasi pesan error
        self.assertIn("must use mongodb:// or mongodb+srv://", str(context.exception))
    
    def test_mongo_uri_without_hostname_raises_error(self):
        """Test: MONGO_URI tanpa hostname harus raise ValueError."""
        # Set MONGO_URI tanpa hostname
        os.environ['MONGO_URI'] = 'mongodb://'
        
        with self.assertRaises(ValueError) as context:
            src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            if 'config' in sys.modules:
                del sys.modules['config']
            import config
        
        # Verifikasi pesan error
        self.assertIn("must include a hostname", str(context.exception))
    
    def test_valid_mongo_uri_localhost(self):
        """Test: MONGO_URI valid dengan localhost harus berhasil."""
        # Set MONGO_URI valid
        os.environ['MONGO_URI'] = 'mongodb://localhost:27017/'
        
        # Import config harus berhasil
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        if 'config' in sys.modules:
            del sys.modules['config']
        
        # Tidak boleh raise exception
        try:
            import config
            self.assertEqual(config.MONGO_URI, 'mongodb://localhost:27017/')
        except ValueError as e:
            self.fail(f"Import config dengan MONGO_URI valid tidak boleh raise exception: {e}")
    
    def test_valid_mongo_uri_with_auth(self):
        """Test: MONGO_URI valid dengan autentikasi harus berhasil."""
        # Set MONGO_URI valid dengan username/password
        os.environ['MONGO_URI'] = 'mongodb://user:pass@mongodb.example.com:27017/dbname'
        
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        if 'config' in sys.modules:
            del sys.modules['config']
        
        # Tidak boleh raise exception
        try:
            import config
            self.assertEqual(
                config.MONGO_URI, 
                'mongodb://user:pass@mongodb.example.com:27017/dbname'
            )
        except ValueError as e:
            self.fail(f"Import config dengan MONGO_URI valid tidak boleh raise exception: {e}")
    
    def test_valid_mongo_uri_srv(self):
        """Test: MONGO_URI valid dengan mongodb+srv harus berhasil."""
        # Set MONGO_URI valid dengan SRV record
        os.environ['MONGO_URI'] = 'mongodb+srv://user:pass@cluster.mongodb.net/dbname'
        
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        if 'config' in sys.modules:
            del sys.modules['config']
        
        # Tidak boleh raise exception
        try:
            import config
            self.assertEqual(
                config.MONGO_URI,
                'mongodb+srv://user:pass@cluster.mongodb.net/dbname'
            )
        except ValueError as e:
            self.fail(f"Import config dengan MONGO_URI valid tidak boleh raise exception: {e}")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
