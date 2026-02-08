"""File-based store implementation with cross-process locking."""

import fcntl
import json
import os
import time
from pathlib import Path

from ..record import Record
from .base import Store


class FileStore(Store):
    """File-based store for idempotency records.

    Uses JSON files for persistence and fcntl for cross-process locking.
    Safe for multi-process scenarios (e.g., gunicorn workers, celery).

    Args:
        directory: Path to directory for storing records
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock_handles: dict[str, int] = {}

    def _record_path(self, key: str) -> Path:
        """Get file path for a record."""
        # Use hash to avoid filesystem issues with special chars
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.directory / f"{safe_key}.json"

    def _lock_path(self, key: str) -> Path:
        """Get lock file path for a key."""
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.directory / f"{safe_key}.lock"

    def get(self, key: str) -> Record | None:
        """Retrieve a record, checking TTL expiration."""
        record_path = self._record_path(key)

        if not record_path.exists():
            return None

        try:
            with open(record_path) as f:
                data = json.load(f)

            # Check TTL expiration
            if "expires_at" in data and data["expires_at"] is not None:
                if time.time() > data["expires_at"]:
                    # Expired, clean up
                    self.delete(key)
                    return None

            # Remove metadata before creating Record
            data.pop("expires_at", None)
            return Record.from_dict(data)

        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None

    def set(self, record: Record, ttl: float | None = None) -> None:
        """Store a record with optional TTL."""
        record_path = self._record_path(record.key)

        data = record.to_dict()
        if ttl is not None:
            data["expires_at"] = time.time() + ttl
        else:
            data["expires_at"] = None

        # Write atomically using temp file + rename
        temp_path = record_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        temp_path.replace(record_path)

    def delete(self, key: str) -> None:
        """Delete a record and its lock file."""
        record_path = self._record_path(key)
        lock_path = self._lock_path(key)

        record_path.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)

    def acquire_lock(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire a cross-process lock using fcntl.

        Args:
            key: The idempotency key
            timeout: Maximum time to wait for lock (seconds)

        Returns:
            True if lock acquired, False if timeout
        """
        lock_path = self._lock_path(key)
        start_time = time.time()

        # Open lock file (create if doesn't exist)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)

        try:
            # Try to acquire lock with timeout
            while True:
                try:
                    # Non-blocking lock attempt
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._lock_handles[key] = fd
                    return True
                except BlockingIOError:
                    # Lock held by another process
                    if time.time() - start_time >= timeout:
                        os.close(fd)
                        return False
                    # Wait a bit before retrying
                    time.sleep(0.01)
        except Exception:
            os.close(fd)
            raise

    def release_lock(self, key: str) -> None:
        """Release a cross-process lock."""
        if key not in self._lock_handles:
            return

        fd = self._lock_handles[key]
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            # Lock already released or file descriptor invalid
            pass
        finally:
            del self._lock_handles[key]

    def clear(self) -> None:
        """Clear all records and locks (useful for testing)."""
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)
        for path in self.directory.glob("*.lock"):
            path.unlink(missing_ok=True)
