"""MemoryCacheBackend tests."""

from __future__ import annotations

import asyncio

from hawkapi_cache import MemoryCacheBackend


async def test_set_get_roundtrip(memory_backend: MemoryCacheBackend) -> None:
    await memory_backend.set("k", b"v", ttl=10)
    assert await memory_backend.get("k") == b"v"


async def test_missing_key_returns_none(memory_backend: MemoryCacheBackend) -> None:
    assert await memory_backend.get("nope") is None


async def test_ttl_expires_value(memory_backend: MemoryCacheBackend) -> None:
    # Use a fake monotonic clock by setting a very short TTL and waiting.
    await memory_backend.set("k", b"v", ttl=1)
    await asyncio.sleep(1.05)
    assert await memory_backend.get("k") is None


async def test_delete_removes_value(memory_backend: MemoryCacheBackend) -> None:
    await memory_backend.set("k", b"v", ttl=10)
    await memory_backend.delete("k")
    assert await memory_backend.get("k") is None


async def test_clear_wipes_everything(memory_backend: MemoryCacheBackend) -> None:
    await memory_backend.set("a", b"1", ttl=10)
    await memory_backend.set("b", b"2", ttl=10)
    await memory_backend.clear()
    assert await memory_backend.get("a") is None
    assert await memory_backend.get("b") is None


async def test_lru_eviction(small_memory_backend: MemoryCacheBackend) -> None:
    # max_size=3 — set 4 keys, the oldest must be evicted.
    await small_memory_backend.set("a", b"1", ttl=60)
    await small_memory_backend.set("b", b"2", ttl=60)
    await small_memory_backend.set("c", b"3", ttl=60)
    await small_memory_backend.set("d", b"4", ttl=60)
    assert await small_memory_backend.get("a") is None
    assert await small_memory_backend.get("d") == b"4"


async def test_lru_touch_keeps_recently_used(small_memory_backend: MemoryCacheBackend) -> None:
    await small_memory_backend.set("a", b"1", ttl=60)
    await small_memory_backend.set("b", b"2", ttl=60)
    await small_memory_backend.set("c", b"3", ttl=60)
    # Touch 'a' to make it MRU.
    assert await small_memory_backend.get("a") == b"1"
    await small_memory_backend.set("d", b"4", ttl=60)
    # Now 'b' should be the oldest, not 'a'.
    assert await small_memory_backend.get("a") == b"1"
    assert await small_memory_backend.get("b") is None


async def test_invalidate_tags(memory_backend: MemoryCacheBackend) -> None:
    await memory_backend.set("u1", b"alice", ttl=60, tags=["users", "user:1"])
    await memory_backend.set("u2", b"bob", ttl=60, tags=["users", "user:2"])
    await memory_backend.set("other", b"x", ttl=60, tags=["misc"])

    count = await memory_backend.invalidate_tags(["users"])
    assert count == 2
    assert await memory_backend.get("u1") is None
    assert await memory_backend.get("u2") is None
    assert await memory_backend.get("other") == b"x"


async def test_invalidate_single_tag(memory_backend: MemoryCacheBackend) -> None:
    await memory_backend.set("u1", b"alice", ttl=60, tags=["users", "user:1"])
    await memory_backend.set("u2", b"bob", ttl=60, tags=["users", "user:2"])

    count = await memory_backend.invalidate_tags(["user:1"])
    assert count == 1
    assert await memory_backend.get("u1") is None
    assert await memory_backend.get("u2") == b"bob"


async def test_invalidate_empty_tag_returns_zero(memory_backend: MemoryCacheBackend) -> None:
    assert await memory_backend.invalidate_tags(["nonexistent"]) == 0


async def test_concurrent_writes_safe(memory_backend: MemoryCacheBackend) -> None:
    async def writer(idx: int) -> None:
        for i in range(10):
            await memory_backend.set(f"k{idx}-{i}", f"{idx}-{i}".encode(), ttl=60)

    await asyncio.gather(*[writer(i) for i in range(10)])
    # 100 writes total, all should be present.
    assert await memory_backend.get("k5-5") == b"5-5"
