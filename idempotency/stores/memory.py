"""In-memory store implementation."""

import threading
import time

from ..record import Record
from .base import Store


class MemoryStore(Store):
    """Thread-safe in-memory store for idempotency records.

    Note: This store does NOT persist across processes or restarts.
    Use FileStore or RedisStore for multi-process scenarios.
    """

    def __init__(self) -> None:
        self._records: dict[str, tuple[Record, float | None]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def get(self, key: str) -> Record | None:
        """Retrieve a record, checking TTL expiration."""
        with self._global_lock:
            if key not in self._records:
                return None

            record, expires_at = self._records[key]

            # Check if expired
            if expires_at is not None and time.time() > expires_at:
                del self._records[key]
                if key in self._locks:
                    del self._locks[key]
                return None

            return record

    def set(self, record: Record, ttl: float | None = None) -> None:
        """Store a record with optional TTL."""
        with self._global_lock:
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl

            self._records[record.key] = (record, expires_at)

    def delete(self, key: str) -> None:
        """Delete a record and its lock."""
        with self._global_lock:
            self._records.pop(key, None)
            self._locks.pop(key, None)

    def acquire_lock(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire a lock for the given key.

        Uses threading.Lock for thread-safety within a single process.
        """
        # Get or create lock for this key
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            lock = self._locks[key]

        # Try to acquire with timeout
        return lock.acquire(timeout=timeout)

    def release_lock(self, key: str) -> None:
        """Release a lock for the given key."""
        with self._global_lock:
            if key in self._locks:
                try:
                    self._locks[key].release()
                except RuntimeError:
                    # Lock wasn't held, ignore
                    pass

    def clear(self) -> None:
        """Clear all records and locks (useful for testing)."""
        with self._global_lock:
            self._records.clear()
            self._locks.clear()
