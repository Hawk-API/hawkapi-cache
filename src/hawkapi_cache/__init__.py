"""hawkapi-cache — response caching for HawkAPI.

Provides ``init_cache(app, ...)``, a ``@cache(...)`` decorator, and two
backends (in-memory + Redis) with tag-based invalidation.
"""

from __future__ import annotations

__version__ = "0.1.0"

from hawkapi_cache._backends import CacheBackend, MemoryCacheBackend
from hawkapi_cache._decorator import cache
from hawkapi_cache._plugin import CachePlugin, init_cache
from hawkapi_cache._redis import RedisCacheBackend

__all__ = [
    "CacheBackend",
    "CachePlugin",
    "MemoryCacheBackend",
    "RedisCacheBackend",
    "__version__",
    "cache",
    "init_cache",
]
