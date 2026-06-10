# Changelog

## 0.2.1 — 2026-06-10

Security hardening.

### Changed

- Cache backend `get` / `set` failures (e.g. a Redis outage) are now caught and
  logged, degrading gracefully to a cache miss / uncached response instead of
  surfacing a 500 (CWE-703).
- Interpolated cache tag values are length-capped (256 chars) before use as
  Redis key components, so a hostile path segment cannot inflate the tag-key
  namespace (CWE-770).

## [0.2.0] - 2026-05-16

Security hardening.

### Changed

- Corrupt cache entries no longer raise — `decode()` failures are logged and
  treated as a miss so the handler is invoked to repopulate (CWE-502).
- `decode()` enforces conservative msgpack size limits
  (`max_bin_len` / `max_str_len` = 10 MiB, `max_array_len` / `max_map_len`
  = 1024) to prevent decompression-style memory blow-ups.
- The `@cache` decorator now prepends `plugin.key_prefix` to the computed
  cache key — previously `key_prefix` was ignored, breaking namespacing
  (CWE-436).
- CR / LF characters are stripped from cached header values during decode,
  closing a response-splitting vector if a corrupt entry was ever served
  (CWE-444).
- Cached responses carry `Cache-Control: no-store` by default so downstream
  caches don't re-store our replays.
- `on_startup` / `on_shutdown` now run the backend coroutine to completion
  instead of fire-and-forgetting it, so backend `close()` actually flushes.
- The active-plugin registry uses `WeakKeyDictionary` to eliminate the
  `id(app)` ABA hazard.

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

[0.1.0]: https://github.com/Hawk-API/hawkapi-cache/releases/tag/v0.1.0
