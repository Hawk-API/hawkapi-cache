"""``CachePlugin`` and ``init_cache`` — wire a cache backend into HawkAPI."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from hawkapi.plugins import Plugin

from hawkapi_cache._backends import CacheBackend, MemoryCacheBackend

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger("hawkapi_cache")


class _StateNamespace:
    """Lightweight attribute bag for ``app.state`` when none exists."""

    cache: Any  # set by ``CachePlugin.attach``


class CachePlugin(Plugin):
    """HawkAPI plugin that owns a cache backend.

    The backend lifecycle is tied to ASGI startup / shutdown. Handlers reach
    the plugin via ``app.state.cache`` after ``init_cache(app, ...)`` has been
    called, or by accessing ``plugin`` directly.
    """

    def __init__(
        self,
        *,
        backend: CacheBackend | None = None,
        key_prefix: str = "hawkapi-cache:",
    ) -> None:
        self.backend: CacheBackend = backend or MemoryCacheBackend()
        self.key_prefix = key_prefix
        self._app: Any = None

    def on_route_registered(self, route: Any) -> Any:
        return route

    def on_schema_generated(self, spec: dict[str, Any]) -> dict[str, Any]:
        return spec

    def on_startup(self) -> None:
        coro = self.backend.start()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(coro)
        else:
            asyncio.run(coro)

    def on_shutdown(self) -> None:
        coro = self.backend.close()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(coro)
        else:
            asyncio.run(coro)

    def on_exception(self, request: Any, exc: Exception) -> None:
        return None

    def on_middleware_added(self, middleware_class: type, kwargs: dict[str, Any]) -> None:
        return None

    # --- helpers usable from handlers --------------------------------------

    async def invalidate_tags(self, tags: Sequence[str]) -> int:
        """Drop every cached entry tagged with any of *tags*. Returns the count."""
        return await self.backend.invalidate_tags(tags)

    async def invalidate_key(self, key: str) -> None:
        """Drop a specific cache key."""
        await self.backend.delete(key)

    async def clear(self) -> None:
        """Drop every cached entry."""
        await self.backend.clear()

    def attach(self, app: Any) -> None:
        """Mount this plugin's accessor on ``app.state.cache``."""
        self._app = app
        if getattr(app, "state", None) is None:
            app.state = _StateNamespace()
        app.state.cache = self
        # Module-level lookup so the ``@cache`` decorator can find the plugin
        # without relying on ``scope["app"]`` (which TestClient doesn't set).
        _ACTIVE_PLUGINS[id(app)] = self
        _LAST_PLUGIN[0] = self


_ACTIVE_PLUGINS: dict[int, CachePlugin] = {}
_LAST_PLUGIN: list[CachePlugin | None] = [None]


def resolve_plugin(app: Any) -> CachePlugin | None:
    """Look up the cache plugin for *app*, or the last-attached one as a fallback.

    TestClient does not populate ``scope["app"]``, so the decorator cannot rely
    on the request alone. The module-level registry keyed by ``id(app)``
    handles multi-app processes; ``_LAST_PLUGIN`` is the common single-app
    fast path.
    """
    if app is not None:
        plugin = _ACTIVE_PLUGINS.get(id(app))
        if plugin is not None:
            return plugin
    return _LAST_PLUGIN[0]


def init_cache(
    app: Any,
    *,
    backend: CacheBackend | None = None,
    key_prefix: str = "hawkapi-cache:",
) -> CachePlugin:
    """Register and mount a :class:`CachePlugin` in one call.

    ```python
    from hawkapi import HawkAPI
    from hawkapi_cache import init_cache, RedisCacheBackend

    app = HawkAPI()
    init_cache(app, backend=RedisCacheBackend.from_url("redis://localhost:6379/0"))
    ```

    After this call:

    * The plugin's lifecycle hooks are registered on the app.
    * ``app.state.cache`` exposes the plugin (``await app.state.cache.invalidate_tags(...)``).
    """
    plugin = CachePlugin(backend=backend, key_prefix=key_prefix)
    app.add_plugin(plugin)
    plugin.attach(app)
    return plugin


__all__ = ["CachePlugin", "init_cache"]
