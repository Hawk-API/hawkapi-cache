# Changelog

## [0.1.0] - 2026-05-16

Initial release.

### Added

- `init_cache(app, *, backend=...)` — registers `CachePlugin`, mounts on `app.state.cache`.
- `@cache(ttl=..., tags=..., vary=..., key_func=..., condition=...)` decorator.
- `MemoryCacheBackend(max_size=10_000)` — LRU + TTL, default.
- `RedisCacheBackend.from_url(...)` — multi-process via `hawkapi-cache[redis]` extra.
- Tag-based invalidation: `app.state.cache.invalidate_tags([...])`.
- `X-Cache: HIT` / `MISS` response header.
- Only `GET` / `HEAD` + 2xx responses are cached; other methods and statuses pass through.

[0.1.0]: https://github.com/ashimov/hawkapi-cache/releases/tag/v0.1.0
