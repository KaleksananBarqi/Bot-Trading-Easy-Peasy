
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
        
        self.uri = config.MONGO_URI
        self.uri = config.MONGO_URI
        self.db_name = config.MONGO_DB_NAME
        self.collection_name = config.MONGO_COLLECTION_NAME
        self.client = None
        self.db = None
        self.trades_collection = None
        
        self.connect()
        self._initialized = True

    def connect(self):
        """Establishes connection to MongoDB."""
        try:
            # Set shorter timeout for initial connection check
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            
            # Trigger connection check
            self.client.admin.command('ping')
            
            self.db = self.client[self.db_name]
            self.db = self.client[self.db_name]
            self.trades_collection = self.db[self.collection_name]
            
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

    def get_trades(self, filter_query: dict = {}, sort_by: str = "timestamp", ascending: bool = False, limit: int = 0):
        """
        Retrieves trades based on filter.
        """
        try:
            if self.db is None:
                if not self.connect():
                    return []
            
            direction = ASCENDING if ascending else DESCENDING
            cursor = self.trades_collection.find(filter_query).sort(sort_by, direction)
            
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
            return self.trades_collection.count_documents(filter_query)
        except Exception as e:
            logger.error(f"❌ Error counting trades: {e}")
            return 0
