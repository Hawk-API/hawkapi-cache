"""Cache backend Protocol + in-memory implementation."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class CacheBackend(Protocol):
    """Pluggable cache storage."""

    async def get(self, key: str) -> bytes | None: ...

    async def set(
        self,
        key: str,
        value: bytes,
        *,
        ttl: int,
        tags: Sequence[str] = (),
    ) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def invalidate_tags(self, tags: Sequence[str]) -> int: ...

    async def clear(self) -> None: ...

    async def start(self) -> None: ...

    async def close(self) -> None: ...


class MemoryCacheBackend:
    """In-process cache with LRU eviction and per-key TTL.

    Safe for single-process asyncio apps. NOT shared across workers — use
    ``RedisCacheBackend`` for that.
    """

    def __init__(self, *, max_size: int | None = 10_000) -> None:
        self._max_size = max_size
        self._store: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
        # Tag -> set of keys for O(1) invalidation by tag.
        self._tags: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at <= time.monotonic():
                # Expired — drop lazily.
                self._store.pop(key, None)
                return None
            # LRU touch — most-recently-used moves to the end.
            self._store.move_to_end(key)
            return value

    async def set(
        self,
        key: str,
        value: bytes,
        *,
        ttl: int,
        tags: Sequence[str] = (),
    ) -> None:
        async with self._lock:
            expires_at = time.monotonic() + ttl
            self._store[key] = (value, expires_at)
            self._store.move_to_end(key)
            for tag in tags:
                self._tags.setdefault(tag, set()).add(key)
            if self._max_size is not None and len(self._store) > self._max_size:
                # Drop oldest entries until under the cap.
                while len(self._store) > self._max_size:
                    old_key, _ = self._store.popitem(last=False)
                    for keys in self._tags.values():
                        keys.discard(old_key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)
            for keys in self._tags.values():
                keys.discard(key)

    async def invalidate_tags(self, tags: Sequence[str]) -> int:
        async with self._lock:
            keys_to_drop: set[str] = set()
            for tag in tags:
                keys_to_drop.update(self._tags.pop(tag, set()))
            for key in keys_to_drop:
                self._store.pop(key, None)
            # Also clean up the dropped keys from other tag index entries.
            for keys in self._tags.values():
                keys.difference_update(keys_to_drop)
            return len(keys_to_drop)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
            self._tags.clear()

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None


__all__ = ["CacheBackend", "MemoryCacheBackend"]
