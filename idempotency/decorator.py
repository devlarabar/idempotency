"""Main idempotent decorator implementation."""

import functools
import json
import pickle
import time
from collections.abc import Callable
from typing import TypeVar

from .exceptions import DuplicateExecutionError, LockTimeoutError
from .key import generate_key
from .record import Record
from .stores import MemoryStore, Store

F = TypeVar("F", bound=Callable)


def idempotent(
    ttl: float | None = None,
    store: Store | None = None,
    key: Callable[..., str] | None = None,
    on_duplicate: str = "return",
    on_failure: str = "unlock",
) -> Callable[[F], F]:
    """Decorator to make a function idempotent.

    Args:
        ttl: Time-to-live for idempotency records (seconds)
        store: Storage backend (defaults to MemoryStore)
        key: Custom key generation function
        on_duplicate: Behavior when duplicate detected:
            - "return": Return stored result (default)
            - "raise": Raise DuplicateExecutionError
            - "wait": Wait for first execution to complete
        on_failure: Behavior when function raises:
            - "unlock": Allow retry (default)
            - "lock": Failures are also idempotent

    Example:
        @idempotent(ttl=300)
        def create_invoice(user_id, amount):
            charge_card(user_id, amount)
            return {"invoice_id": 123}
    """
    if on_duplicate not in ("return", "raise", "wait"):
        raise ValueError(
            f"on_duplicate must be 'return', 'raise', or 'wait', got '{on_duplicate}'"
        )

    if on_failure not in ("unlock", "lock"):
        raise ValueError(f"on_failure must be 'unlock' or 'lock', got '{on_failure}'")

    # Use default store if none provided
    _store = store or MemoryStore()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            # Generate idempotency key
            idem_key = generate_key(func, args, kwargs, custom_key_func=key)

            # Check if operation already exists
            existing = _store.get(idem_key)

            if existing:
                # Handle based on status and config
                if existing.status == "completed":
                    if on_duplicate == "return" or on_duplicate == "wait":
                        # Both return the cached result
                        return _deserialize_result(existing.result)
                    elif on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)

                elif existing.status == "failed":
                    if on_failure == "lock":
                        # Failures are idempotent, treat like completed
                        if on_duplicate == "return" or on_duplicate == "wait":
                            # Re-raise the original exception
                            if existing.error:
                                exc = pickle.loads(bytes.fromhex(existing.error))
                                raise exc
                            raise Exception("Unknown error")
                        elif on_duplicate == "raise":
                            raise DuplicateExecutionError(idem_key)
                    # If on_failure == "unlock", fall through to allow retry

                elif existing.status == "in_progress":
                    if on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)
                    # If "return" or "wait", fall through to wait for completion

            # Try to acquire lock
            if not _store.acquire_lock(idem_key, timeout=10.0):
                # Couldn't acquire lock, check status again
                existing = _store.get(idem_key)
                if existing and existing.status == "completed":
                    if on_duplicate == "return" or on_duplicate == "wait":
                        return _deserialize_result(existing.result)
                    elif on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)

                # Check for failed status with lock mode
                if existing and existing.status == "failed" and on_failure == "lock":
                    if on_duplicate == "return" or on_duplicate == "wait":
                        if existing.error:
                            exc = pickle.loads(bytes.fromhex(existing.error))
                            raise exc
                        raise Exception("Unknown error")
                    elif on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)

                # Still in progress or failed to acquire
                raise LockTimeoutError(idem_key, 10.0)

            try:
                # Double-check after acquiring lock
                existing = _store.get(idem_key)
                if existing and existing.status == "completed":
                    if on_duplicate == "return" or on_duplicate == "wait":
                        return _deserialize_result(existing.result)
                    elif on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)

                # Check for failed status
                if existing and existing.status == "failed" and on_failure == "lock":
                    if on_duplicate == "return" or on_duplicate == "wait":
                        if existing.error:
                            exc = pickle.loads(bytes.fromhex(existing.error))
                            raise exc
                        raise Exception("Unknown error")
                    elif on_duplicate == "raise":
                        raise DuplicateExecutionError(idem_key)

                # Mark as in-progress
                record = Record(key=idem_key, status="in_progress")
                _store.set(record, ttl=ttl)

                # Execute function
                try:
                    result = func(*args, **kwargs)

                    # Serialize result
                    serialized_result = _serialize_result(result)

                    # Mark as completed
                    record.status = "completed"
                    record.result = serialized_result
                    record.completed_at = time.time()
                    _store.set(record, ttl=ttl)

                    return result

                except Exception as e:
                    # Mark as failed
                    record.status = "failed"
                    # Pickle the exception to preserve type and traceback
                    record.error = pickle.dumps(e).hex()
                    record.completed_at = time.time()

                    if on_failure == "lock":
                        # Store the failure
                        _store.set(record, ttl=ttl)
                    else:
                        # Delete so retry is allowed
                        _store.delete(idem_key)

                    raise

            finally:
                # Always release lock
                _store.release_lock(idem_key)

        return wrapper

    return decorator


def _serialize_result(result: object) -> object:
    """Serialize result for storage.

    Args:
        result: The function return value

    Returns:
        Serialized result (JSON-compatible)

    Raises:
        SerializationError: If result cannot be serialized
    """
    try:
        # Test if JSON-serializable
        json.dumps(result)
        return result
    except (TypeError, ValueError):
        # Can't serialize (e.g., lambdas, file handles)
        # Store None so on_duplicate="return" still works
        return None


def _deserialize_result(result: object) -> object:
    """Deserialize result from storage.

    Args:
        result: The stored result

    Returns:
        Deserialized result
    """
    return result
