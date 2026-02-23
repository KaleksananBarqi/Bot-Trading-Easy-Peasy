
import os
import time
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from src.utils.helper import logger
try:
    from src import config
except ImportError:
    import config

class MongoManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # Guard check: MONGO_URI harus sudah divalidasi oleh config.py
        # Jika None, berarti config.py belum di-import atau validasi gagal
        if not config.MONGO_URI:
            raise RuntimeError(
                "MongoDB URI is not configured. "
                "Please ensure MONGO_URI is set in your environment before importing this module."
            )
        
        self.uri = config.MONGO_URI
        self.db_name = config.MONGO_DB_NAME
        self.collection_name = config.MONGO_COLLECTION_NAME
        self.client = None
        self.db = None
        self.settings_collection = None
        
        self.connect()
        self._initialized = True
        
        # Initialize default settings if empty
        self._init_default_settings()

    def _init_default_settings(self):
        """Seed initial settings from config.py if not exists in DB"""
        if self.settings_collection is not None:
            doc = self.settings_collection.find_one({"_id": "global"})
            if not doc:
                try:
                    default_settings = {
                        "_id": "global",
                        "DAFTAR_KOIN": config.DAFTAR_KOIN,
                        "PAKAI_DEMO": getattr(config, 'PAKAI_DEMO', True)
                    }
                    self.settings_collection.insert_one(default_settings)
                    logger.info("✅ Default bot settings seeded to MongoDB")
                except Exception as e:
                    logger.error(f"❌ Failed to seed default settings: {e}")

    def connect(self):
        """Establishes connection to MongoDB."""
        try:
            # Set shorter timeout for initial connection check
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            
            # Trigger connection check
            self.client.admin.command('ping')
            
            self.db = self.client[self.db_name]
            self.trades_collection = self.db[self.collection_name]
            self.settings_collection = self.db['bot_settings']
            
            # Ensure indexes
            self._setup_indexes()
            
            logger.info(f"✅ MongoDB Connected: {self.db_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ MongoDB Connection Failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ MongoDB Error: {e}")
            return False

    def _setup_indexes(self):
        """Setup standard indexes for performance."""
        try:
            # Index on symbol (for filtering by coin)
            self.trades_collection.create_index([("symbol", ASCENDING)])
            
            # Index on timestamp (for date range filtering and sorting)
            self.trades_collection.create_index([("timestamp", DESCENDING)])
            
            # Index on strategy_tag (for strategy performance analysis)
            self.trades_collection.create_index([("strategy_tag", ASCENDING)])
            
            # Index on exit_type (for exit type analysis)
            self.trades_collection.create_index([("exit_type", ASCENDING)])
            
            logger.info("✅ MongoDB Indexes Verified")
        except Exception as e:
            logger.warning(f"⚠️ Failed to create indexes: {e}")

    def insert_trade(self, trade_data: dict) -> bool:
        """
        Inserts a single trade document.
        """
        try:
            if self.db is None:
                if not self.connect():
                    return False
            
            result = self.trades_collection.insert_one(trade_data)
            return result.acknowledged
        except Exception as e:
            logger.error(f"❌ Failed to insert trade to MongoDB: {e}")
            return False

    ALLOWED_FILTER_FIELDS = frozenset({
        'timestamp', 'symbol', 'side', 'type',
        'entry_price', 'exit_price', 'size_usdt',
        'pnl_usdt', 'pnl_percent', 'roi_percent',
        'fee', 'strategy_tag', 'result',
        'prompt', 'reason', 'setup_at', 'filled_at',
        'exit_type', 'trailing_was_active',
        'trailing_sl_final', 'trailing_high', 'trailing_low',
        'activation_price', 'sl_price_initial'
    })

    ALLOWED_SORT_FIELDS = frozenset({
        'timestamp', 'symbol', 'side', 'type',
        'entry_price', 'exit_price', 'size_usdt',
        'pnl_usdt', 'pnl_percent', 'roi_percent',
        'fee', 'strategy_tag', 'result',
        'exit_type'
    })

    MONGO_OPERATORS = frozenset({
        '$where', '$function', '$expr', '$text', '$search', '$meta',
        '$near', '$nearSphere', '$geometry', '$maxDistance', '$minDistance',
        '$all', '$elemMatch', '$exists', '$in', '$nin', '$not', '$or',
        '$and', '$nor', '$regex', '$options', '$slice', '$size',
        '$gt', '$gte', '$lt', '$lte', '$ne', '$eq'
    })

    @staticmethod
    def _sanitize_filter_query(filter_query: dict) -> dict:
        if not filter_query:
            return {}
        sanitized = {}
        for key, value in filter_query.items():
            if key.startswith('$'):
                logger.warning(f"⚠️ Rejected MongoDB operator in filter: {key}")
                continue
            if key not in MongoManager.ALLOWED_FILTER_FIELDS:
                logger.warning(f"⚠️ Rejected unknown field in filter: {key}")
                continue
            if isinstance(value, dict):
                for op in value.keys():
                    if op in MongoManager.MONGO_OPERATORS:
                        logger.warning(f"⚠️ Rejected MongoDB operator in filter value: {op}")
                        break
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value
        return sanitized

    @staticmethod
    def _sanitize_sort_field(sort_by: str) -> str:
        if sort_by not in MongoManager.ALLOWED_SORT_FIELDS:
            logger.warning(f"⚠️ Rejected unknown sort field: {sort_by}, using 'timestamp'")
            return 'timestamp'
        return sort_by

    def get_trades(self, filter_query: dict = {}, sort_by: str = "timestamp", ascending: bool = False, limit: int = 0):
        """
        Retrieves trades based on filter.
        """
        try:
            if self.db is None:
                if not self.connect():
                    return []
            
            sanitized_filter = self._sanitize_filter_query(filter_query)
            sanitized_sort = self._sanitize_sort_field(sort_by)
            
            direction = ASCENDING if ascending else DESCENDING
            cursor = self.trades_collection.find(sanitized_filter).sort(sanitized_sort, direction)
            
            if limit > 0:
                cursor = cursor.limit(limit)
                
            return list(cursor)
        except Exception as e:
            logger.error(f"❌ Failed to fetch trades from MongoDB: {e}")
            return []

    def get_trade_count(self, filter_query: dict = {}) -> int:
        """Count trades matching filter."""
        try:
            if self.db is None:
                return 0
            sanitized_filter = self._sanitize_filter_query(filter_query)
            return self.trades_collection.count_documents(sanitized_filter)
        except Exception as e:
            logger.error(f"❌ Error counting trades: {e}")
            return 0

    # ==========================================
    # BOT SETTINGS MANAGEMENT (REMOTE CONTROL)
    # ==========================================
    
    def get_bot_settings(self) -> dict:
        """Get the global bot settings document."""
        if self.db is None and not self.connect():
            # Fallback to config if DB is down
            return {"DAFTAR_KOIN": config.DAFTAR_KOIN, "PAKAI_DEMO": getattr(config, 'PAKAI_DEMO', True)}
        
        try:
            doc = self.settings_collection.find_one({"_id": "global"})
            if doc:
                return doc
        except Exception as e:
            logger.error(f"❌ Error fetching bot settings: {e}")
            
        return {"DAFTAR_KOIN": config.DAFTAR_KOIN, "PAKAI_DEMO": getattr(config, 'PAKAI_DEMO', True)}

    def update_bot_settings(self, updates: dict) -> bool:
        """Update specific fields in the global bot settings."""
        if self.db is None and not self.connect():
            return False
            
        try:
            # Use $set to only update the provided fields
            result = self.settings_collection.update_one(
                {"_id": "global"},
                {"$set": updates},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error updating bot settings: {e}")
            return False

    def get_daftar_koin(self) -> list:
        """Helper to get the current list of coins from settings."""
        settings = self.get_bot_settings()
        return settings.get("DAFTAR_KOIN", [])

    def add_koin(self, koin_data: dict) -> bool:
        """Add or update a coin in DAFTAR_KOIN."""
        current_koin = self.get_daftar_koin()
        symbol = koin_data.get("symbol")
        
        if not symbol:
            return False
            
        # Check if already exists; if yes, replace it
        updated = False
        for i, coin in enumerate(current_koin):
            if coin.get("symbol") == symbol:
                current_koin[i] = koin_data
                updated = True
                break
                
        if not updated:
            current_koin.append(koin_data)
            
        return self.update_bot_settings({"DAFTAR_KOIN": current_koin})

    def remove_koin(self, symbol: str) -> bool:
        """Remove a coin from DAFTAR_KOIN."""
        current_koin = self.get_daftar_koin()
        new_koin = [c for c in current_koin if c.get("symbol") != symbol]
        
        if len(new_koin) == len(current_koin):
            return False # Coin not found
            
        return self.update_bot_settings({"DAFTAR_KOIN": new_koin})

    def get_is_demo(self) -> bool:
        """Helper to get current PAKAI_DEMO mode."""
        settings = self.get_bot_settings()
        return settings.get("PAKAI_DEMO", getattr(config, 'PAKAI_DEMO', True))

    def set_is_demo(self, is_demo: bool) -> bool:
        """Helper to set PAKAI_DEMO mode."""
        return self.update_bot_settings({"PAKAI_DEMO": is_demo})
