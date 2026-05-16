# hawkapi-cache

Response caching for [HawkAPI](https://github.com/ashimov/HawkAPI) — decorator + middleware + Redis/memory backends + tag-based invalidation.

## Install

```bash
pip install hawkapi-cache              # memory backend
pip install hawkapi-cache[redis]       # + Redis backend
```

## Quickstart

```python
from hawkapi import HawkAPI, Request
from hawkapi_cache import init_cache, cache, RedisCacheBackend

app = HawkAPI()
init_cache(app, backend=RedisCacheBackend.from_url("redis://localhost:6379/0"))

@app.get("/users/{user_id:int}")
@cache(ttl=60, tags=["users", "user:{user_id}"])
async def get_user(request: Request, user_id: int):
    return await db.fetch_user(user_id)

@app.post("/users/{user_id:int}/refresh")
async def refresh(request: Request, user_id: int):
    await app.state.cache.invalidate_tags([f"user:{user_id}"])
    return {"ok": True}
```

In-memory is the default (no Redis required):

```python
from hawkapi_cache import init_cache
init_cache(app)   # MemoryCacheBackend(max_size=10_000)
```

## `@cache(...)` reference

| Arg | Default | Notes |
|---|--:|---|
| `ttl` | `60` | Seconds. |
| `tags` | `()` | Group invalidation. `{name}` placeholders pulled from path params. |
| `vary` | `()` | Request headers that change the response. Values appended to the cache key. |
| `key_func` | `None` | `(Request) -> str` override. Replaces the default key entirely. |
| `condition` | `None` | `(Request) -> bool` — return `False` to bypass cache. |

Only `GET` / `HEAD` requests with `2xx` responses are cached. Other methods and non-2xx responses pass through.

Every cached response gets an `X-Cache: HIT` or `X-Cache: MISS` header.

## Recipes

### Per-user cache via `vary`

```python
@cache(ttl=60, vary=("authorization",))
async def me(request: Request):
    ...
```

### Bypass cache for authenticated users

```python
@cache(ttl=60, condition=lambda r: not r.headers.get("authorization"))
async def feed(request: Request):
    ...
```

### Tag-driven invalidation

```python
@cache(ttl=300, tags=["posts", "post:{post_id}"])
async def get_post(request: Request, post_id: int): ...

@app.put("/posts/{post_id:int}")
async def update(request: Request, post_id: int):
    ...
    await app.state.cache.invalidate_tags([f"post:{post_id}"])
```

### Custom key

```python
@cache(ttl=60, key_func=lambda r: f"my:{r.url.path}:{r.headers.get('x-tenant')}")
async def list_orders(request: Request): ...
```

## Backends

### `MemoryCacheBackend(max_size=10_000)`

LRU + per-key TTL, single-process. Use for tests and small deployments.

### `RedisCacheBackend.from_url("redis://host/0", prefix="hawkapi-cache:")`

Multi-process safe. Tag index uses Redis SETs; `invalidate_tags` is a pipelined `SUNION` + `DEL`. Add `hawkapi-cache[redis]` extra.

## Development

```bash
git clone https://github.com/ashimov/hawkapi-cache.git
cd hawkapi-cache
uv sync --extra dev
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run pyright src/
```

## License

MIT.
