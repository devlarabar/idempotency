"""Base store interface for idempotency records."""

from abc import ABC, abstractmethod

from ..record import Record


class Store(ABC):
    """Abstract base class for idempotency stores.

    Stores are responsible for:
    - Persisting execution records
    - Providing atomic lock acquisition
    - Managing TTL/expiration
    """

    @abstractmethod
    def get(self, key: str) -> Record | None:
        """Retrieve a record by key.

        Args:
            key: The idempotency key

        Returns:
            Record if found, None otherwise
        """
        pass

    @abstractmethod
    def set(self, record: Record, ttl: float | None = None) -> None:
        """Store a record.

        Args:
            record: The record to store
            ttl: Time-to-live in seconds (None = no expiration)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a record.

        Args:
            key: The idempotency key
        """
        pass

    @abstractmethod
    def acquire_lock(self, key: str, timeout: float = 10.0) -> bool:
        """Attempt to acquire a lock for the given key.

        Args:
            key: The idempotency key
            timeout: Maximum time to wait for lock (seconds)

        Returns:
            True if lock acquired, False otherwise
        """
        pass

    @abstractmethod
    def release_lock(self, key: str) -> None:
        """Release a lock for the given key.

        Args:
            key: The idempotency key
        """
        pass
