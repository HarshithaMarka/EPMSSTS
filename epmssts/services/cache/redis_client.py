"""
Redis caching service for session management.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import redis

from epmssts.config import settings


class CacheService:
    """Redis-based caching service."""
    
    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL. If None, uses settings.
        """
        self._url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None
        self._ttl = settings.redis_ttl_seconds
    
    def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._client = redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Test connection
            self._client.ping()
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Redis: {exc}") from exc
    
    def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None
    
    def _ensure_connected(self) -> redis.Redis:
        """Ensure client is connected."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    def set_session(
        self, session_id: UUID, data: dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """
        Store session data.
        
        Args:
            session_id: Session UUID.
            data: Session data dictionary.
            ttl: Time-to-live in seconds. If None, uses default.
        """
        client = self._ensure_connected()
        key = f"session:{session_id}"
        value = json.dumps(data)
        client.setex(key, ttl or self._ttl, value)
    
    def get_session(self, session_id: UUID) -> Optional[dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Session UUID.
            
        Returns:
            Session data dictionary, or None if not found.
        """
        client = self._ensure_connected()
        key = f"session:{session_id}"
        value = client.get(key)
        
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    def delete_session(self, session_id: UUID) -> None:
        """
        Delete session data.
        
        Args:
            session_id: Session UUID.
        """
        client = self._ensure_connected()
        key = f"session:{session_id}"
        client.delete(key)
    
    def set_cache(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """
        Store arbitrary cache data.
        
        Args:
            key: Cache key.
            value: Value to cache (will be JSON-serialized).
            ttl: Time-to-live in seconds. If None, uses default.
        """
        client = self._ensure_connected()
        serialized = json.dumps(value)
        client.setex(key, ttl or self._ttl, serialized)
    
    def get_cache(self, key: str) -> Optional[Any]:
        """
        Retrieve cached data.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached value, or None if not found.
        """
        client = self._ensure_connected()
        value = client.get(key)
        
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    def delete_cache(self, key: str) -> None:
        """
        Delete cached data.
        
        Args:
            key: Cache key.
        """
        client = self._ensure_connected()
        client.delete(key)
    
    def clear_all(self) -> None:
        """
        Clear all cache data (use with caution).
        """
        client = self._ensure_connected()
        client.flushdb()
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get Redis statistics.
        
        Returns:
            Dictionary with Redis info.
        """
        client = self._ensure_connected()
        info = client.info()
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "0"),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }


__all__ = ["CacheService"]
