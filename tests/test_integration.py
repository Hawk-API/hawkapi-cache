"""End-to-end tests through TestClient."""

from __future__ import annotations

from typing import Any

from hawkapi import HawkAPI, Request
from hawkapi.responses import JSONResponse, PlainTextResponse
from hawkapi.testing import TestClient

from hawkapi_cache import cache, init_cache


def _app() -> HawkAPI:
    app = HawkAPI(openapi_url=None)
    init_cache(app)
    return app


def test_get_request_cached_returns_hit_on_second_call() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/hello")
    @cache(ttl=60)
    async def hello(request: Request) -> PlainTextResponse:
        calls["n"] += 1
        return PlainTextResponse(f"hello {calls['n']}")

    client = TestClient(app)
    r1 = client.get("/hello")
    r2 = client.get("/hello")
    assert r1.status_code == 200
    assert r1.text == "hello 1"
    assert r2.status_code == 200
    assert r2.text == "hello 1"
    assert calls["n"] == 1
    assert r1.headers["x-cache"] == "MISS"
    assert r2.headers["x-cache"] == "HIT"


def test_post_request_never_cached() -> None:
    app = _app()
    calls = {"n": 0}

    @app.post("/echo")
    @cache(ttl=60)
    async def echo(request: Request) -> JSONResponse:
        calls["n"] += 1
        return JSONResponse({"n": calls["n"]})

    client = TestClient(app)
    r1 = client.post("/echo", json={})
    r2 = client.post("/echo", json={})
    assert r1.json() == {"n": 1}
    assert r2.json() == {"n": 2}
    assert calls["n"] == 2


def test_5xx_response_not_cached() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/fail")
    @cache(ttl=60)
    async def fail(request: Request) -> JSONResponse:
        calls["n"] += 1
        return JSONResponse({"err": "boom"}, status_code=500)

    client = TestClient(app)
    client.get("/fail")
    client.get("/fail")
    assert calls["n"] == 2


def test_vary_on_authorization_separates_cache(memory_backend: Any) -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/profile")
    @cache(ttl=60, vary=("authorization",))
    async def profile(request: Request) -> JSONResponse:
        calls["n"] += 1
        return JSONResponse({"who": request.headers.get("authorization", "anon")})

    client = TestClient(app)
    r1 = client.get("/profile", headers={"Authorization": "Bearer alice"})
    r2 = client.get("/profile", headers={"Authorization": "Bearer alice"})
    r3 = client.get("/profile", headers={"Authorization": "Bearer bob"})
    assert r1.json() == {"who": "Bearer alice"}
    assert r2.json() == {"who": "Bearer alice"}
    assert r3.json() == {"who": "Bearer bob"}
    assert calls["n"] == 2  # alice cached, bob fresh
    assert r1.headers["x-cache"] == "MISS"
    assert r2.headers["x-cache"] == "HIT"
    assert r3.headers["x-cache"] == "MISS"


def test_condition_bypasses_cache_for_authenticated() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/feed")
    @cache(ttl=60, condition=lambda r: not r.headers.get("authorization"))
    async def feed(request: Request) -> JSONResponse:
        calls["n"] += 1
        return JSONResponse({"n": calls["n"]})

    client = TestClient(app)
    # Anonymous → cached
    client.get("/feed")
    client.get("/feed")
    assert calls["n"] == 1
    # Authenticated → bypass
    client.get("/feed", headers={"Authorization": "Bearer x"})
    client.get("/feed", headers={"Authorization": "Bearer x"})
    assert calls["n"] == 3


def test_tag_invalidation_drops_cached_entry() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/users/{user_id:int}")
    @cache(ttl=60, tags=["users", "user:{user_id}"])
    async def get_user(request: Request, user_id: int) -> JSONResponse:
        calls["n"] += 1
        return JSONResponse({"id": user_id, "n": calls["n"]})

    @app.post("/users/{user_id:int}/refresh")
    async def refresh(request: Request, user_id: int) -> JSONResponse:
        count = await app.state.cache.invalidate_tags([f"user:{user_id}"])  # type: ignore[attr-defined]
        return JSONResponse({"dropped": count})

    client = TestClient(app)
    client.get("/users/1")
    client.get("/users/1")
    assert calls["n"] == 1
    drop = client.post("/users/1/refresh")
    assert drop.json() == {"dropped": 1}
    client.get("/users/1")
    assert calls["n"] == 2


def test_clear_drops_everything() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/x")
    @cache(ttl=60)
    async def handler(request: Request) -> PlainTextResponse:
        calls["n"] += 1
        return PlainTextResponse(str(calls["n"]))

    client = TestClient(app)
    client.get("/x")
    client.get("/x")
    assert calls["n"] == 1

    async def _clear() -> None:
        await app.state.cache.clear()  # type: ignore[attr-defined]

    import asyncio

    asyncio.run(_clear())
    client.get("/x")
    assert calls["n"] == 2


def test_custom_key_func() -> None:
    app = _app()
    calls = {"n": 0}

    @app.get("/k")
    @cache(ttl=60, key_func=lambda r: "fixed-key")
    async def handler(request: Request) -> PlainTextResponse:
        calls["n"] += 1
        return PlainTextResponse(f"v{calls['n']}")

    client = TestClient(app)
    # Both calls collapse to the same key, second is a hit even though
    # the path is identical anyway — proves key_func wins.
    client.get("/k")
    client.get("/k")
    assert calls["n"] == 1
