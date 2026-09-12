import time
from typing import Any, Optional, Dict
from collections import OrderedDict
import threading

from app.config import settings
from app.utils.logger import logger


class InMemoryCache:
    """Thread-safe, TTL-based in-memory cache with size limiting."""

    def __init__(self, max_entries: int = 1000, default_ttl: int = 3600):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Gets a value from cache if it exists and has not expired."""
        if not settings.CACHE_ENABLED:
            return None

        with self._lock:
            if key not in self._store:
                return None

            entry = self._store[key]
            now = time.time()

            if now > entry["expires_at"]:
                # Expired
                del self._store[key]
                return None

            # Move to end (LRU behavior)
            self._store.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores a value in cache with an expiration timestamp."""
        if not settings.CACHE_ENABLED:
            return

        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl

        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            elif len(self._store) >= self.max_entries:
                # Evict oldest entry (FIFO / LRU)
                oldest_key, _ = self._store.popitem(last=False)
                logger.debug(f"Cache full. Evicted key: {oldest_key}")

            self._store[key] = {
                "value": value,
                "expires_at": expires_at,
            }

    def clear(self) -> None:
        """Clears all entries in the cache."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Returns current count of entries in the cache."""
        with self._lock:
            return len(self._store)


# Global singleton cache instance
cache_service = InMemoryCache(
    max_entries=settings.CACHE_MAX_ENTRIES,
    default_ttl=settings.CACHE_TTL_SECONDS
)
