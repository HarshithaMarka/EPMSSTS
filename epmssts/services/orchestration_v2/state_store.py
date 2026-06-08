"""External state store for orchestration traces and counters.

Uses Redis as the primary backend to keep orchestrator instances stateless.
Falls back to process-local memory only when Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio import Redis as AsyncRedis


logger = logging.getLogger(__name__)


class OrchestrationStateStore:
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._redis: Optional[Any] = None
        self._fallback: Dict[str, Dict[str, Any]] = {}
        self._fallback_expiry: Dict[str, float] = {}

    async def connect(self) -> bool:
        try:
            from redis.asyncio import Redis  # type: ignore
        except Exception:
            logger.warning("redis.asyncio is not available; using local fallback store")
            return False

        try:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            return True
        except Exception as exc:
            logger.warning("Redis connection failed, falling back to local store: %s", exc)
            self._redis = None
            return False

    @property
    def redis_connected(self) -> bool:
        return self._redis is not None

    async def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None):
        payload = json.dumps(value, default=str)
        if self._redis is not None:
            await self._redis.set(key, payload, ex=ttl or self.ttl_seconds)
            return

        self._fallback[key] = value
        self._fallback_expiry[key] = time.time() + float(ttl or self.ttl_seconds)

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        if self._redis is not None:
            payload = await self._redis.get(key)
            if not payload:
                return None
            return json.loads(payload)

        self._cleanup_local()
        return self._fallback.get(key)

    async def incr(self, key: str, ttl: Optional[int] = None) -> int:
        if self._redis is not None:
            value = await self._redis.incr(key)
            if value == 1:
                await self._redis.expire(key, ttl or self.ttl_seconds)
            return int(value)

        self._cleanup_local()
        current = int(self._fallback.get(key, {}).get("value", 0)) + 1
        self._fallback[key] = {"value": current}
        self._fallback_expiry[key] = time.time() + float(ttl or self.ttl_seconds)
        return current

    async def get_int(self, key: str, default: int = 0) -> int:
        if self._redis is not None:
            value = await self._redis.get(key)
            return int(value) if value is not None else default

        self._cleanup_local()
        data = self._fallback.get(key)
        if not data:
            return default
        return int(data.get("value", default))

    async def close(self):
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def _cleanup_local(self):
        now = time.time()
        expired = [key for key, expiry in self._fallback_expiry.items() if expiry <= now]
        for key in expired:
            self._fallback.pop(key, None)
            self._fallback_expiry.pop(key, None)
