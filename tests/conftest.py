"""Shared fixtures."""

from __future__ import annotations

import pytest

from hawkapi_cache import MemoryCacheBackend


@pytest.fixture
def memory_backend() -> MemoryCacheBackend:
    return MemoryCacheBackend()


@pytest.fixture
def small_memory_backend() -> MemoryCacheBackend:
    """A tiny LRU for eviction tests."""
    return MemoryCacheBackend(max_size=3)
