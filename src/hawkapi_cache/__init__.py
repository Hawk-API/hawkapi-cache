"""hawkapi-cache — response caching for HawkAPI.

Provides ``init_cache(app, ...)``, a ``@cache(...)`` decorator, and two
backends (in-memory + Redis) with tag-based invalidation.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from hawkapi_cache._backends import CacheBackend, MemoryCacheBackend
from hawkapi_cache._decorator import cache
from hawkapi_cache._plugin import CachePlugin, init_cache
from hawkapi_cache._redis import RedisCacheBackend

try:
    __version__ = version("hawkapi-cache")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

__all__ = [
    "CacheBackend",
    "CachePlugin",
    "MemoryCacheBackend",
    "RedisCacheBackend",
    "__version__",
    "cache",
    "init_cache",
]
