"""Cache key + tag generation helpers."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

# Cap interpolated path-param values so a hostile path cannot inflate the
# Redis tag-key namespace with unbounded-length keys.
_MAX_TAG_LEN = 256


def make_key(
    method: str,
    path: str,
    query: str,
    vary_values: Sequence[str] = (),
) -> str:
    """Build a deterministic cache key from request components.

    Returns the first 32 hex chars of SHA-256 over the joined components —
    short, collision-resistant for any realistic cache size.
    """
    parts = "\x1f".join((method.upper(), path, query, *vary_values))
    digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
    return digest[:32]


def interpolate_tags(tags: Sequence[str], path_params: dict[str, Any]) -> list[str]:
    """Substitute ``{name}`` placeholders in tag strings with path-param values."""
    # Cap each value so a hostile path segment cannot produce an unbounded tag key.
    capped = {k: str(v)[:_MAX_TAG_LEN] for k, v in path_params.items()}
    out: list[str] = []
    for tag in tags:
        try:
            out.append(tag.format(**capped))
        except (KeyError, IndexError):
            # Unknown placeholder — keep tag as-is rather than failing the request.
            out.append(tag)
    return out


__all__ = ["make_key", "interpolate_tags"]
