"""Cache key + tag interpolation tests."""

from __future__ import annotations

from hawkapi_cache._key import interpolate_tags, make_key


def test_key_is_deterministic() -> None:
    k1 = make_key("GET", "/users/1", "", ())
    k2 = make_key("GET", "/users/1", "", ())
    assert k1 == k2


def test_key_varies_with_method() -> None:
    assert make_key("GET", "/users/1", "", ()) != make_key("POST", "/users/1", "", ())


def test_key_varies_with_path() -> None:
    assert make_key("GET", "/users/1", "", ()) != make_key("GET", "/users/2", "", ())


def test_key_varies_with_query() -> None:
    assert make_key("GET", "/users", "limit=10", ()) != make_key("GET", "/users", "limit=20", ())


def test_key_varies_with_vary_values() -> None:
    a = make_key("GET", "/u", "", ("token-a",))
    b = make_key("GET", "/u", "", ("token-b",))
    assert a != b


def test_key_length_32_hex() -> None:
    key = make_key("GET", "/", "", ())
    assert len(key) == 32
    int(key, 16)  # parses as hex


def test_interpolate_tags_simple() -> None:
    tags = interpolate_tags(["user:{user_id}"], {"user_id": "42"})
    assert tags == ["user:42"]


def test_interpolate_tags_missing_placeholder_kept() -> None:
    tags = interpolate_tags(["user:{user_id}"], {})
    assert tags == ["user:{user_id}"]


def test_interpolate_tags_no_placeholder() -> None:
    tags = interpolate_tags(["users"], {"user_id": "42"})
    assert tags == ["users"]
