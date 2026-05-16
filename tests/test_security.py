"""Regression tests for 0.2.0 hardening fixes."""

from __future__ import annotations

import asyncio

import pytest
from hawkapi import HawkAPI, Request
from hawkapi.responses import PlainTextResponse
from hawkapi.testing import TestClient

from hawkapi_cache import MemoryCacheBackend, cache, init_cache
from hawkapi_cache._serialize import decode, encode


def test_corrupt_cache_entry_treats_as_miss() -> None:
    """A garbage backend value must not crash the response; the handler runs."""
    app = HawkAPI(openapi_url=None)
    backend = MemoryCacheBackend()
    plugin = init_cache(app, backend=backend)

    calls = {"n": 0}

    @app.get("/x")
    @cache(ttl=60)
    async def handler(request: Request) -> PlainTextResponse:
        calls["n"] += 1
        return PlainTextResponse(f"v{calls['n']}")

    client = TestClient(app)
    # Prime the cache key by issuing a real request first.
    client.get("/x")
    assert calls["n"] == 1

    # Replace every stored entry with garbage bytes (msgpack-undecodable).
    async def _corrupt() -> None:
        for key in list(backend._store.keys()):  # noqa: SLF001
            await backend.set(key, b"\xc1\xc1\xc1\xc1", ttl=60)

    asyncio.run(_corrupt())

    # Should still succeed — the corrupt entry is treated as a miss.
    r = client.get("/x")
    assert r.status_code == 200
    assert calls["n"] == 2
    assert plugin.key_prefix  # touched to keep import live


def test_key_prefix_namespaces_keys() -> None:
    """Stored keys must include the plugin's ``key_prefix``."""
    app = HawkAPI(openapi_url=None)
    backend = MemoryCacheBackend()
    init_cache(app, backend=backend, key_prefix="myapp:")

    @app.get("/y")
    @cache(ttl=60)
    async def handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("hi")

    client = TestClient(app)
    client.get("/y")
    stored = list(backend._store.keys())  # noqa: SLF001
    assert stored, "expected exactly one cached entry"
    assert all(k.startswith("myapp:") for k in stored), stored


def test_msgpack_size_limit_enforced() -> None:
    """Oversized arrays inside an entry must fail decode rather than allocate."""
    # Build a payload whose header list exceeds the array cap (1024).
    huge_headers = [(b"h", b"v")] * 2000
    blob = encode(200, huge_headers, b"")
    with pytest.raises(Exception):  # noqa: B017, PT011
        decode(blob)


def test_crlf_stripped_from_cached_headers() -> None:
    """CR / LF injected into a cached header value must not survive replay."""
    app = HawkAPI(openapi_url=None)
    backend = MemoryCacheBackend()
    init_cache(app, backend=backend)

    @app.get("/z")
    @cache(ttl=60)
    async def handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    client.get("/z")  # populate

    # Manually rewrite the cached entry to embed CRLF in a header value.
    async def _poison() -> None:
        for key, (value, _exp) in list(backend._store.items()):
            status, headers, body = decode(value)
            poisoned = [*headers, (b"x-evil", b"good\r\nSet-Cookie: pwn=1")]
            from hawkapi_cache._serialize import encode as _encode  # noqa: PLC0415

            await backend.set(key, _encode(status, poisoned, body), ttl=60)

    asyncio.run(_poison())

    r = client.get("/z")
    assert r.status_code == 200
    # Whatever survived must contain no CR/LF.
    for v in r.headers.values():
        assert "\r" not in v and "\n" not in v
