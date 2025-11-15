"""
Redis client for local edge caching in the frontend
Provides cache-aside pattern for aggregated data
"""
import redis
import json
import logging
from typing import Optional, Dict, Any
from modules.config import config

class RedisEdgeClient:
    """Redis client for edge node local caching"""
    
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.logger = logging.getLogger('RedisEdgeClient')
        
        # Redis configuration (can be local or remote)
        self.host = getattr(config, 'REDIS_HOST', 'localhost')
        self.port = int(getattr(config, 'REDIS_PORT', 6379))
        self.db = int(getattr(config, 'REDIS_DB', 0))
        
    def connect(self) -> bool:
        """Connect to Redis server"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.client.ping()
            self.is_connected = True
            self.logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return True
        except redis.ConnectionError as e:
            self.logger.warning(f"Redis connection failed: {e}. Running without cache.")
            self.is_connected = False
            return False
        except Exception as e:
            self.logger.error(f"Redis error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            try:
                self.client.close()
                self.is_connected = False
                self.logger.info("Disconnected from Redis")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Redis: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_connected or not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except json.JSONDecodeError:
            self.logger.warning(f"Failed to decode cached value for key: {key}")
            # Delete corrupted cache entry
            try:
                self.client.delete(key)
            except Exception:
                pass
            return None
        except Exception as e:
            self.logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            serialized = json.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            self.logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_connected or not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            self.logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def keys(self, pattern: str = "*") -> list:
        """Get all keys matching pattern"""
        if not self.is_connected or not self.client:
            return []
        
        try:
            return self.client.keys(pattern)
        except Exception as e:
            self.logger.error(f"Error getting keys with pattern {pattern}: {e}")
            return []
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace"""
        if not self.is_connected or not self.client:
            return 0
        
        try:
            pattern = f"{namespace}:*"
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            self.logger.error(f"Error clearing namespace {namespace}: {e}")
            return 0

