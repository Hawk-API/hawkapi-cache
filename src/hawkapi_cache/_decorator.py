"""The ``@cache(...)`` decorator."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from hawkapi.requests.request import Request
from hawkapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from hawkapi.responses.response import Response

from hawkapi_cache._key import interpolate_tags, make_key
from hawkapi_cache._serialize import decode, encode

# JSONResponse does not inherit from Response in HawkAPI — both are first-class
# response shapes with a ``status_code``, ``body``, and ``_build_raw_headers``.
# Enumerate the cacheable types explicitly.
_CACHEABLE_RESPONSE_TYPES: tuple[type, ...] = (
    Response,
    JSONResponse,
    PlainTextResponse,
    HTMLResponse,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("hawkapi_cache")

_CACHEABLE_METHODS = frozenset({"GET", "HEAD"})


def cache(
    *,
    ttl: int = 60,
    tags: Sequence[str] = (),
    vary: Sequence[str] = (),
    key_func: Callable[[Request], str] | None = None,
    condition: Callable[[Request], bool] | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Cache the wrapped handler's response.

    Parameters:
        ttl: Time-to-live in seconds.
        tags: Tags for grouped invalidation. ``{name}`` placeholders are
            substituted from path params (e.g. ``"user:{user_id}"``).
        vary: Request headers that affect the response (e.g. ``("authorization",)``).
            Different values produce different cache keys.
        key_func: Custom key builder. Receives the ``Request`` and must
            return a string key.
        condition: Predicate that disables caching when it returns False.
            Use this to bypass cache for authenticated users etc.

    Only ``GET`` / ``HEAD`` requests with 2xx responses are cached. Other
    methods and non-2xx responses pass through untouched.
    """

    def decorator(
        handler: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        sig = inspect.signature(handler)
        has_request_param = any(
            (p.annotation is Request or p.name == "request") for p in sig.parameters.values()
        )

        @wraps(handler)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _find_request(args, kwargs, has_request_param)
            if request is None:
                # Handler doesn't take Request — cannot cache; pass through.
                return await handler(*args, **kwargs)

            method = request.method.upper()
            if method not in _CACHEABLE_METHODS:
                return await handler(*args, **kwargs)

            if condition is not None and not condition(request):
                return await handler(*args, **kwargs)

            plugin = _get_plugin(request)
            if plugin is None:
                return await handler(*args, **kwargs)

            base_key = (
                key_func(request) if key_func is not None else _build_default_key(request, vary)
            )
            cache_key = plugin.key_prefix + base_key

            cached = await plugin.backend.get(cache_key)
            decoded: tuple[int, list[tuple[bytes, bytes]], bytes] | None = None
            if cached is not None:
                try:
                    decoded = decode(cached)
                except Exception as exc:
                    # Corrupt entry — log + treat as miss, never propagate.
                    logger.warning(
                        "cache: corrupt entry for key %s, treating as miss: %s",
                        cache_key,
                        exc,
                    )
            if decoded is not None:
                status, headers, body = decoded
                rebuilt = Response(
                    content=body,
                    status_code=status,
                )
                rebuilt._headers = _headers_to_dict(headers)  # pyright: ignore[reportPrivateUsage]
                rebuilt._headers["x-cache"] = "HIT"  # pyright: ignore[reportPrivateUsage]
                # Cached responses must not themselves be revalidated by
                # downstream caches (the handler already controlled freshness).
                rebuilt._headers.setdefault("cache-control", "no-store")  # pyright: ignore[reportPrivateUsage]
                return rebuilt

            result = await handler(*args, **kwargs)
            response = _coerce_response(result)
            if response is None or not (200 <= response.status_code < 300):
                return result

            interpolated = interpolate_tags(tags, dict(request.path_params))
            raw_headers = response._build_raw_headers()  # pyright: ignore[reportPrivateUsage]
            await plugin.backend.set(
                cache_key,
                encode(response.status_code, raw_headers, response.body),
                ttl=ttl,
                tags=interpolated,
            )
            response._headers["x-cache"] = "MISS"  # pyright: ignore[reportPrivateUsage]
            return response

        return wrapper

    return decorator


def _find_request(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    has_request_param: bool,
) -> Request | None:
    if not has_request_param:
        return None
    for value in (*args, *kwargs.values()):
        if isinstance(value, Request):
            return value
    return None


def _build_default_key(request: Request, vary: Sequence[str]) -> str:
    vary_values = tuple((request.headers.get(h.lower(), "") or "") for h in vary)
    raw_qs: Any = request.scope.get("query_string", b"")
    query = raw_qs.decode("latin-1") if isinstance(raw_qs, bytes) else str(raw_qs)
    path = request.scope.get("path", "")
    return make_key(request.method, str(path), query, vary_values)


def _get_plugin(request: Request) -> Any:
    from hawkapi_cache._plugin import resolve_plugin  # noqa: PLC0415

    return resolve_plugin(request.scope.get("app"))


def _headers_to_dict(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    # Strip CR/LF from cached header values — a malicious entry must not be
    # able to inject new headers or split the response (CWE-444).
    return {
        k.decode("latin-1"): v.decode("latin-1").replace("\r", "").replace("\n", "")
        for k, v in headers
    }


def _coerce_response(result: Any) -> Any | None:
    """Return *result* if it is a cacheable response type, else ``None``."""
    if isinstance(result, _CACHEABLE_RESPONSE_TYPES):
        return result
    return None


__all__ = ["cache"]
