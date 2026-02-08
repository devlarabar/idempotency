"""Idempotency Guard - Function-level idempotency for Python.

Prevents duplicate side effects caused by retries, race conditions,
or replayed events.

Example:
    @idempotent(ttl=300)
    def create_invoice(user_id, amount):
        charge_card(user_id, amount)
        return {"invoice_id": 123}
"""

from .decorator import idempotent
from .exceptions import (
    DuplicateExecutionError,
    IdempotencyError,
    LockTimeoutError,
    SerializationError,
)
from .stores import MemoryStore, Store

__version__ = "0.1.0"

__all__ = [
    "idempotent",
    "IdempotencyError",
    "DuplicateExecutionError",
    "LockTimeoutError",
    "SerializationError",
    "Store",
    "MemoryStore",
]
