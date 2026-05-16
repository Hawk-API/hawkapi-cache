"""Cache payload serialization via msgpack."""

from __future__ import annotations

from typing import Any, cast

import msgpack  # pyright: ignore[reportMissingTypeStubs]

# Defensive size limits — refuse to expand huge or deeply-nested payloads
# during decode. The cache stores HTTP responses, so 10MiB per bytes/string
# and 1024 entries per array/map is well above any realistic header set.
_MAX_BIN_LEN = 10_485_760
_MAX_STR_LEN = 10_485_760
_MAX_ARRAY_LEN = 1024
_MAX_MAP_LEN = 1024


def encode(status: int, headers: list[tuple[bytes, bytes]], body: bytes) -> bytes:
    """Pack a response triplet for storage in the cache backend."""
    packed: Any = msgpack.packb(  # pyright: ignore[reportUnknownMemberType]
        (status, list(headers), body),
        use_bin_type=True,
    )
    return cast(bytes, packed)


def decode(blob: bytes) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Unpack a cached response triplet.

    Enforces conservative size limits so a corrupt or malicious entry cannot
    consume unbounded memory during decode (CWE-409).
    """
    unpacked = cast(
        tuple[int, list[list[bytes]], bytes],
        msgpack.unpackb(  # pyright: ignore[reportUnknownMemberType]
            blob,
            raw=True,
            max_bin_len=_MAX_BIN_LEN,
            max_str_len=_MAX_STR_LEN,
            max_array_len=_MAX_ARRAY_LEN,
            max_map_len=_MAX_MAP_LEN,
        ),
    )
    status, headers, body = unpacked
    return status, [(h[0], h[1]) for h in headers], body


__all__ = ["encode", "decode"]
