"""Redis-backed cache backend (optional ``hawkapi-cache[redis]`` extra)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class RedisCacheBackend:
    """Redis-backed cache.

    Keys are stored under ``{prefix}{key}``. Each tag maps to a Redis SET of
    keys at ``{prefix}tag:{tag}`` so ``invalidate_tags`` is a pipelined
    ``SUNION`` + ``DEL``.
    """

    def __init__(self, client: Any, *, prefix: str = "hawkapi-cache:") -> None:
        self._client = client
        self._prefix = prefix

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        prefix: str = "hawkapi-cache:",
        **client_kwargs: Any,
    ) -> RedisCacheBackend:
        """Build from a Redis connection URL (e.g. ``redis://localhost:6379/0``)."""
        import redis.asyncio as redis_aio  # noqa: PLC0415  # pyright: ignore[reportMissingImports]

        client: Any = redis_aio.Redis.from_url(url, **client_kwargs)
        return cls(client, prefix=prefix)

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _tag_key(self, tag: str) -> str:
        return f"{self._prefix}tag:{tag}"

    async def get(self, key: str) -> bytes | None:
        result: Any = await self._client.get(self._key(key))
        if result is None:
            return None
        if isinstance(result, bytes):
            return result
        return bytes(result)

    async def set(
        self,
        key: str,
        value: bytes,
        *,
        ttl: int,
        tags: Sequence[str] = (),
    ) -> None:
        full_key = self._key(key)
        pipe: Any = self._client.pipeline(transaction=False)
        pipe.set(full_key, value, ex=ttl)
        for tag in tags:
            pipe.sadd(self._tag_key(tag), full_key)
            # Tag index lives slightly longer than the entry so a late
            # invalidate still catches keys that are still alive.
            pipe.expire(self._tag_key(tag), ttl + 60)
        await pipe.execute()

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    async def invalidate_tags(self, tags: Sequence[str]) -> int:
        if not tags:
            return 0
        tag_keys = [self._tag_key(t) for t in tags]
        keys: Any = await self._client.sunion(*tag_keys)
        if not keys:
            await self._client.delete(*tag_keys)
            return 0
        keys_list = list(keys)
        await self._client.delete(*keys_list, *tag_keys)
        return len(keys_list)

    async def clear(self) -> None:
        # Scan keys under our prefix and delete them — avoids FLUSHDB on a
        # shared Redis instance. Use SCAN with a generous count for speed.
        cursor: int = 0
        pattern = f"{self._prefix}*"
        while True:
            cursor_out: int
            keys: list[bytes]
            cursor_out, keys = await self._client.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                await self._client.delete(*keys)
            cursor = cursor_out
            if cursor == 0:
                break

    async def start(self) -> None:
        # Verify reachability — fail fast at app startup rather than per-request.
        await self._client.ping()

    async def close(self) -> None:
        aclose: Any = getattr(self._client, "aclose", None)
        if aclose is not None:
            await aclose()
        else:
            await self._client.close()


__all__ = ["RedisCacheBackend"]
