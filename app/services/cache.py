from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional
import logging
from collections import defaultdict
import hashlib
import json


logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_calls: int = 10, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: Dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def can_proceed(self, key: str) -> bool:
        async with self._lock:
            now = time.time()
            # Clean old calls
            self.calls[key] = [t for t in self.calls[key] if now - t < self.window_seconds]
            return len(self.calls[key]) < self.max_calls

    async def record_call(self, key: str) -> None:
        async with self._lock:
            self.calls[key].append(time.time())

    async def wait_if_needed(self, key: str) -> None:
        while not await self.can_proceed(key):
            await asyncio.sleep(1)
        await self.record_call(key)


class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Create a cache key from function arguments."""
        data = {"args": args, "kwargs": kwargs}
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    return value
                else:
                    del self.cache[key]
            return None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self.cache[key] = (value, time.time())

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching a pattern."""
        async with self._lock:
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.cache[key]


# Global instances
_rate_limiter = RateLimiter()
_response_cache = ResponseCache()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter


def get_response_cache() -> ResponseCache:
    return _response_cache


async def cached_tool_call(tool_name: str, params: Dict[str, Any], ttl_seconds: int = 3600) -> Any:
    """Execute a tool call with caching and rate limiting."""
    cache = get_response_cache()
    rate_limiter = get_rate_limiter()
    
    # Create cache key
    cache_key = cache._make_key(tool_name, **params)
    
    # Check cache first
    cached_result = await cache.get(cache_key)
    if cached_result is not None:
        logger.info(f"Cache hit for {tool_name}")
        return cached_result
    
    # Rate limiting
    await rate_limiter.wait_if_needed(f"tool_{tool_name}")
    
    # Execute tool call (this should be implemented by the caller)
    # result = await actual_tool_call(tool_name, params)
    
    # Cache result
    # await cache.set(cache_key, result)
    
    return None  # Placeholder
