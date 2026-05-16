"""Cache payload serialization via msgpack."""

from __future__ import annotations

from typing import Any, cast

import msgpack  # pyright: ignore[reportMissingTypeStubs]


def encode(status: int, headers: list[tuple[bytes, bytes]], body: bytes) -> bytes:
    """Pack a response triplet for storage in the cache backend."""
    packed: Any = msgpack.packb(  # pyright: ignore[reportUnknownMemberType]
        (status, list(headers), body),
        use_bin_type=True,
    )
    return cast(bytes, packed)


def decode(blob: bytes) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Unpack a cached response triplet."""
    unpacked = cast(
        tuple[int, list[list[bytes]], bytes],
        msgpack.unpackb(blob, raw=True),  # pyright: ignore[reportUnknownMemberType]
    )
    status, headers, body = unpacked
    return status, [(h[0], h[1]) for h in headers], body


__all__ = ["encode", "decode"]
