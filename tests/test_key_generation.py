"""Tests for key generation logic."""

from idempotency.key import _normalize_args, _serialize_value, generate_key


def dummy_function(a, b, c=None):
    """Dummy function for testing."""
    pass


def test_generate_key_basic():
    """Test basic key generation."""
    key = generate_key(dummy_function, (1, 2), {"c": 3}, None)

    assert "dummy_function" in key
    assert "arg0=1" in key
    assert "arg1=2" in key
    assert "c=3" in key


def test_generate_key_same_args_same_key():
    """Test that same args produce same key."""
    key1 = generate_key(dummy_function, (1, 2), {"c": 3}, None)
    key2 = generate_key(dummy_function, (1, 2), {"c": 3}, None)

    assert key1 == key2


def test_generate_key_different_args_different_key():
    """Test that different args produce different keys."""
    key1 = generate_key(dummy_function, (1, 2), {"c": 3}, None)
    key2 = generate_key(dummy_function, (1, 2), {"c": 4}, None)

    assert key1 != key2


def test_generate_key_dict_order_stable():
    """Test that dict key order doesn't affect key."""
    key1 = generate_key(
        dummy_function,
        (),
        {"a": 1, "b": 2, "c": 3},
        None
    )
    key2 = generate_key(
        dummy_function,
        (),
        {"c": 3, "a": 1, "b": 2},
        None
    )

    assert key1 == key2


def test_generate_key_custom_function():
    """Test custom key generation function."""
    def custom_key_func(a, b, c=None):
        return f"custom:{a}:{b}"

    key = generate_key(
        dummy_function,
        (1, 2),
        {"c": 3},
        custom_key_func
    )

    assert key == "custom:1:2"


def test_serialize_value_primitives():
    """Test serialization of primitive types."""
    assert _serialize_value(42) == "42"
    assert _serialize_value("hello") == '"hello"'
    assert _serialize_value(True) == "true"
    assert _serialize_value(None) == "null"
    assert _serialize_value(3.14) == "3.14"


def test_serialize_value_collections():
    """Test serialization of collections."""
    # List
    assert _serialize_value([1, 2, 3]) == '["1", "2", "3"]'

    # Dict (sorted keys)
    result = _serialize_value({"b": 2, "a": 1})
    assert '"a"' in result
    assert '"b"' in result

    # Set (converted to sorted list)
    result = _serialize_value({3, 1, 2})
    assert "1" in result


def test_normalize_args():
    """Test argument normalization."""
    normalized = _normalize_args((1, 2), {"c": 3, "d": 4})

    assert "arg0" in normalized
    assert "arg1" in normalized
    assert "c" in normalized
    assert "d" in normalized
    assert normalized["arg0"] == "1"
    assert normalized["arg1"] == "2"
    assert normalized["c"] == "3"
    assert normalized["d"] == "4"


def test_generate_key_long_key_hashing():
    """Test that very long keys get hashed."""
    # Create args that will produce a very long key
    long_string = "x" * 300

    key = generate_key(
        dummy_function,
        (long_string,),
        {},
        None
    )

    # Should be hashed and shorter
    assert len(key) < 250
    assert "dummy_function" in key
