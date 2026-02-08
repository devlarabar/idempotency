"""Exceptions for idempotency guard."""


class IdempotencyError(Exception):
    """Base exception for idempotency-related errors."""

    pass


class DuplicateExecutionError(IdempotencyError):
    """Raised when a duplicate execution is detected and on_duplicate='raise'."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Duplicate execution detected for key: {key}")


class LockTimeoutError(IdempotencyError):
    """Raised when unable to acquire lock within timeout."""

    def __init__(self, key: str, timeout: float) -> None:
        self.key = key
        self.timeout = timeout
        super().__init__(
            f"Failed to acquire lock for key '{key}' within {timeout}s"
        )


class SerializationError(IdempotencyError):
    """Raised when result cannot be serialized."""

    def __init__(self, value: object, reason: str) -> None:
        self.value = value
        self.reason = reason
        super().__init__(f"Cannot serialize result: {reason}")
