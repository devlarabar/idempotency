"""Basic tests for idempotent decorator."""

import time

from idempotency import (
    DuplicateExecutionError,
    MemoryStore,
    idempotent,
)


def test_basic_idempotency():
    """Test that function only executes once for same inputs."""
    call_count = 0

    @idempotent(ttl=10)
    def create_invoice(user_id, amount):
        nonlocal call_count
        call_count += 1
        return {"invoice_id": 123, "amount": amount}

    # First call
    result1 = create_invoice(user_id=1, amount=100)
    assert result1 == {"invoice_id": 123, "amount": 100}
    assert call_count == 1

    # Second call with same args - should return cached result
    result2 = create_invoice(user_id=1, amount=100)
    assert result2 == {"invoice_id": 123, "amount": 100}
    assert call_count == 1  # Not incremented

    # Different args - should execute again
    result3 = create_invoice(user_id=2, amount=200)
    assert result3 == {"invoice_id": 123, "amount": 200}
    assert call_count == 2


def test_on_duplicate_raise():
    """Test that on_duplicate='raise' raises error on duplicate."""

    @idempotent(ttl=10, on_duplicate="raise")
    def create_invoice(user_id):
        return {"invoice_id": 123}

    # First call succeeds
    result = create_invoice(user_id=1)
    assert result == {"invoice_id": 123}

    # Second call raises
    try:
        create_invoice(user_id=1)
        assert False, "Should have raised DuplicateExecutionError"
    except DuplicateExecutionError as e:
        assert "user_id" in e.key


def test_ttl_expiration():
    """Test that records expire after TTL."""
    call_count = 0

    @idempotent(ttl=0.1)  # 100ms TTL
    def create_invoice(user_id):
        nonlocal call_count
        call_count += 1
        return {"invoice_id": 123}

    # First call
    create_invoice(user_id=1)
    assert call_count == 1

    # Immediate second call - cached
    create_invoice(user_id=1)
    assert call_count == 1

    # Wait for expiration
    time.sleep(0.15)

    # Should execute again
    create_invoice(user_id=1)
    assert call_count == 2


def test_failure_handling_unlock():
    """Test that failures allow retry by default."""
    call_count = 0

    @idempotent(ttl=10, on_failure="unlock")
    def failing_function(user_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("First call fails")
        return {"success": True}

    # First call fails
    try:
        failing_function(user_id=1)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    assert call_count == 1

    # Second call should be allowed (retry)
    result = failing_function(user_id=1)
    assert result == {"success": True}
    assert call_count == 2


def test_failure_handling_lock():
    """Test that on_failure='lock' makes failures idempotent."""
    call_count = 0

    @idempotent(ttl=10, on_failure="lock")
    def failing_function(user_id):
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fails")

    # First call fails
    try:
        failing_function(user_id=1)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    assert call_count == 1

    # Second call should return cached failure
    try:
        failing_function(user_id=1)
        assert False, "Should have raised Exception"
    except Exception:
        pass

    assert call_count == 1  # Not incremented


def test_different_arg_types():
    """Test key generation with various argument types."""
    call_count = 0

    @idempotent(ttl=10)
    def process_data(user_id, tags, metadata):
        nonlocal call_count
        call_count += 1
        return {"processed": True}

    # Call with list and dict
    process_data(1, ["a", "b"], {"key": "value"})
    assert call_count == 1

    # Same args - should be cached
    process_data(1, ["a", "b"], {"key": "value"})
    assert call_count == 1

    # Different order in list - different key
    process_data(1, ["b", "a"], {"key": "value"})
    assert call_count == 2


def test_custom_key_function():
    """Test using a custom key generation function."""
    call_count = 0

    @idempotent(
        ttl=10,
        key=lambda user_id, amount: f"invoice:{user_id}"
    )
    def create_invoice(user_id, amount):
        nonlocal call_count
        call_count += 1
        return {"invoice_id": 123, "amount": amount}

    # First call
    create_invoice(user_id=1, amount=100)
    assert call_count == 1

    # Different amount, but same user_id - should be cached
    # because custom key only uses user_id
    result = create_invoice(user_id=1, amount=200)
    assert result == {"invoice_id": 123, "amount": 100}  # Original result
    assert call_count == 1


def test_shared_store():
    """Test that multiple functions can share a store."""
    store = MemoryStore()
    call_count_a = 0
    call_count_b = 0

    @idempotent(ttl=10, store=store)
    def function_a(x):
        nonlocal call_count_a
        call_count_a += 1
        return x * 2

    @idempotent(ttl=10, store=store)
    def function_b(x):
        nonlocal call_count_b
        call_count_b += 1
        return x * 3

    # Each function should have its own key space
    function_a(5)
    function_b(5)
    assert call_count_a == 1
    assert call_count_b == 1

    # Calling again should use cache
    function_a(5)
    function_b(5)
    assert call_count_a == 1
    assert call_count_b == 1


def test_on_duplicate_wait():
    """Test that on_duplicate='wait' returns cached result when complete."""
    call_count = 0

    @idempotent(ttl=10, on_duplicate="wait")
    def create_invoice(user_id):
        nonlocal call_count
        call_count += 1
        return {"invoice_id": 123}

    # First call
    result1 = create_invoice(user_id=1)
    assert result1 == {"invoice_id": 123}
    assert call_count == 1

    # Second call should wait (but since first is done, returns immediately)
    result2 = create_invoice(user_id=1)
    assert result2 == {"invoice_id": 123}
    assert call_count == 1  # Not executed again


def test_exception_type_preserved():
    """Test that original exception type is preserved with on_failure='lock'."""
    call_count = 0

    @idempotent(ttl=10, on_failure="lock")
    def failing_function(user_id):
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid user ID")

    # First call fails with ValueError
    try:
        failing_function(user_id=1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(e) == "Invalid user ID"
        assert call_count == 1

    # Second call should re-raise the same ValueError type
    try:
        failing_function(user_id=1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(e) == "Invalid user ID"
        assert call_count == 1  # Not executed again
