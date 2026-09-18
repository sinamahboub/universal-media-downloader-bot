"""
Optional caching layer for platform detection and media metadata.

Reduces redundant yt-dlp calls for frequently accessed URLs
and improves response times for repeated platform checks.
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CacheEntry:
    """Single cache entry with TTL support."""

    key: str
    value: Any
    created_at: float
    ttl: float
    access_count: int = 0

    def is_expired(self) -> bool:
        """Check if entry has exceeded its TTL."""
        return (time.time() - self.created_at) > self.ttl


class AsyncCache:
    """
    Async-safe in-memory cache with TTL and size limits.

    Not suitable for multi-process deployments; for production
    scale, replace with Redis or Memcached backend.
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _make_key(self, *args: Any) -> str:
        """Generate cache key from arguments."""
        raw = "|".join(str(a) for a in args)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, *args: Any) -> Any | None:
        """
        Get value from cache if present and not expired.

        Args:
            *args: Key components

        Returns:
            Cached value or None if miss/expired
        """
        key = self._make_key(*args)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            entry.access_count += 1
            self._hits += 1
            return entry.value

    async def set(self, value: Any, ttl: float | None = None, *args: Any) -> None:
        """
        Store value in cache.

        Args:
            value: Value to cache
            ttl: Time-to-live in seconds
            *args: Key components
        """
        key = self._make_key(*args)
        ttl = ttl if ttl is not None else self._default_ttl

        async with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_expired()
                if len(self._cache) >= self._max_size:
                    self._evict_lru()

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl,
            )

    async def invalidate(self, *args: Any) -> None:
        """Remove specific entry from cache."""
        key = self._make_key(*args)
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    def _evict_expired(self) -> None:
        """Remove expired entries."""
        expired = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired:
            del self._cache[key]

    def _evict_lru(self) -> None:
        """Remove least recently used entry."""
        if not self._cache:
            return
        lru_key = min(self._cache, key=lambda k: self._cache[k].access_count)
        del self._cache[lru_key]

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(self._hits / max(self._hits + self._misses, 1), 2),
        }
