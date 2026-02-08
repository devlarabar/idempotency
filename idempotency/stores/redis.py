"""Redis-based store implementation with atomic operations."""

import json
import time
from typing import TYPE_CHECKING

from ..record import Record
from .base import Store

if TYPE_CHECKING:
    from redis import Redis


class RedisStore(Store):
    """Redis-based store for idempotency records.

    Uses Redis for distributed locking and persistence.
    Safe for multi-process and multi-server scenarios.

    Args:
        client: Redis client instance
        prefix: Key prefix for namespacing (default: "idempotency:")
    """

    def __init__(self, client: "Redis", prefix: str = "idempotency:") -> None:
        self.client = client
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}{key}"

    def _lock_key(self, key: str) -> str:
        """Get lock key for a given key."""
        return f"{self.prefix}lock:{key}"

    def get(self, key: str) -> Record | None:
        """Retrieve a record from Redis."""
        data = self.client.get(self._key(key))
        if data is None:
            return None

        try:
            parsed = json.loads(data)
            return Record.from_dict(parsed)
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, record: Record, ttl: float | None = None) -> None:
        """Store a record in Redis with optional TTL."""
        key = self._key(record.key)
        data = json.dumps(record.to_dict())

        if ttl is not None:
            # Set with expiration
            self.client.setex(key, int(ttl), data)
        else:
            # Set without expiration
            self.client.set(key, data)

    def delete(self, key: str) -> None:
        """Delete a record and its lock from Redis."""
        self.client.delete(self._key(key))
        self.client.delete(self._lock_key(key))

    def acquire_lock(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire a distributed lock using Redis SET NX.

        Uses Redis SET with NX (set if not exists) and EX (expiration)
        for atomic lock acquisition.

        Args:
            key: The idempotency key
            timeout: Maximum time to wait for lock (seconds)

        Returns:
            True if lock acquired, False if timeout
        """
        lock_key = self._lock_key(key)
        start_time = time.time()
        lock_ttl = int(timeout) + 60  # Lock expires after timeout + buffer

        while True:
            # Try to acquire lock atomically
            # SET NX EX: set if not exists with expiration
            acquired = self.client.set(
                lock_key, "1", nx=True, ex=lock_ttl
            )

            if acquired:
                return True

            # Check timeout
            if time.time() - start_time >= timeout:
                return False

            # Wait a bit before retrying
            time.sleep(0.01)

    def release_lock(self, key: str) -> None:
        """Release a distributed lock."""
        self.client.delete(self._lock_key(key))

    def clear(self) -> None:
        """Clear all records with this prefix (useful for testing)."""
        # Get all keys with prefix
        pattern = f"{self.prefix}*"
        cursor = 0

        while True:
            cursor, keys = self.client.scan(cursor, match=pattern, count=100)
            if keys:
                self.client.delete(*keys)
            if cursor == 0:
                break
