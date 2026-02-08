"""Key generation for idempotent operations."""

import hashlib
import json
from collections.abc import Callable


def generate_key(
    func: Callable,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    custom_key_func: Callable[..., str] | None = None,
) -> str:
    """Generate a stable key for an idempotent operation.

    Args:
        func: The function being called
        args: Positional arguments
        kwargs: Keyword arguments
        custom_key_func: Optional custom key generation function

    Returns:
        A stable string key representing this operation

    The key format is: function_name:arg1=val1:arg2=val2:...
    """
    if custom_key_func:
        return custom_key_func(*args, **kwargs)

    func_name = f"{func.__module__}.{func.__qualname__}"

    # Normalize arguments to a stable representation
    normalized = _normalize_args(args, kwargs)

    # Create key parts
    parts = [func_name]
    parts.extend(f"{k}={v}" for k, v in sorted(normalized.items()))

    key = ":".join(parts)

    # Hash if too long (keep it manageable)
    if len(key) > 200:
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"{func_name}:{key_hash}"

    return key


def _normalize_args(
    args: tuple[object, ...], kwargs: dict[str, object]
) -> dict[str, str]:
    """Normalize arguments to a stable string representation.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Dictionary with stable string representations
    """
    normalized: dict[str, str] = {}

    # Handle positional args
    for i, arg in enumerate(args):
        normalized[f"arg{i}"] = _serialize_value(arg)

    # Handle keyword args
    for key, value in kwargs.items():
        normalized[key] = _serialize_value(value)

    return normalized


def _serialize_value(value: object) -> str:
    """Serialize a value to a stable string representation.

    Args:
        value: Value to serialize

    Returns:
        Stable string representation
    """
    # Handle common types directly
    if isinstance(value, (str, int, float, bool, type(None))):
        return json.dumps(value)

    # Handle collections
    if isinstance(value, (list, tuple)):
        return json.dumps([_serialize_value(v) for v in value])

    if isinstance(value, dict):
        # Sort keys for stability
        return json.dumps(
            {k: _serialize_value(v) for k, v in sorted(value.items())},
            sort_keys=True,
        )

    # Handle sets (convert to sorted list)
    if isinstance(value, set):
        return json.dumps(sorted(_serialize_value(v) for v in value))

    # Fallback: use repr (not ideal but better than failing)
    return repr(value)
