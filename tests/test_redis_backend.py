"""RedisCacheBackend tests via fakeredis."""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip("fakeredis")

from hawkapi_cache import RedisCacheBackend  # noqa: E402


@pytest.fixture
async def redis_backend() -> RedisCacheBackend:
    client = fakeredis.FakeAsyncRedis()
    backend = RedisCacheBackend(client, prefix="test:")
    yield backend
    await backend.close()


async def test_set_get_roundtrip(redis_backend: RedisCacheBackend) -> None:
    await redis_backend.set("k", b"v", ttl=60)
    assert await redis_backend.get("k") == b"v"


async def test_missing_key_returns_none(redis_backend: RedisCacheBackend) -> None:
    assert await redis_backend.get("nope") is None


async def test_delete(redis_backend: RedisCacheBackend) -> None:
    await redis_backend.set("k", b"v", ttl=60)
    await redis_backend.delete("k")
    assert await redis_backend.get("k") is None


async def test_tags_invalidate(redis_backend: RedisCacheBackend) -> None:
    await redis_backend.set("u1", b"a", ttl=60, tags=["users", "user:1"])
    await redis_backend.set("u2", b"b", ttl=60, tags=["users", "user:2"])
    await redis_backend.set("o", b"x", ttl=60, tags=["other"])

    count = await redis_backend.invalidate_tags(["users"])
    assert count == 2
    assert await redis_backend.get("u1") is None
    assert await redis_backend.get("u2") is None
    assert await redis_backend.get("o") == b"x"


async def test_invalidate_unknown_tag_returns_zero(redis_backend: RedisCacheBackend) -> None:
    assert await redis_backend.invalidate_tags(["nonexistent"]) == 0


async def test_clear_scans_and_deletes(redis_backend: RedisCacheBackend) -> None:
    await redis_backend.set("a", b"1", ttl=60)
    await redis_backend.set("b", b"2", ttl=60)
    await redis_backend.clear()
    assert await redis_backend.get("a") is None
    assert await redis_backend.get("b") is None


async def test_start_pings(redis_backend: RedisCacheBackend) -> None:
    # Should not raise — fakeredis supports PING.
    await redis_backend.start()
