"""Storage backends for idempotency records."""

from .base import Store
from .memory import MemoryStore

__all__ = ["Store", "MemoryStore", "FileStore", "RedisStore"]


def __getattr__(name: str) -> type:
    if name == "RedisStore":
        from .redis import RedisStore

        return RedisStore
    if name == "FileStore":
        from .file import FileStore

        return FileStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
