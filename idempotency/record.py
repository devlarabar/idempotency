"""Record dataclass for storing execution state."""

import time
from dataclasses import dataclass, field
from typing import Literal

from idempotency.utils import ensure_float


@dataclass
class Record:
    """Represents the state of an idempotent execution.

    Attributes:
        key: Unique identifier for this operation
        status: Current execution status
        result: Serialized return value (if completed successfully)
        error: Serialized exception (if failed)
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution finished
        heartbeat: Last heartbeat timestamp (for crash detection)
    """

    key: str
    status: Literal["in_progress", "completed", "failed"]
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    heartbeat: float = field(default_factory=time.time)
    result: object = None
    error: str | None = None  # Pickled exception for re-raising

    def to_dict(self) -> dict[str, object]:
        """Convert record to dictionary for serialization."""
        return {
            "key": self.key,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "heartbeat": self.heartbeat,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Record":
        """Create record from dictionary."""
        status = data["status"]
        if status not in ("in_progress", "completed", "failed"):
            raise ValueError(f"Invalid status: {status}")

        started_at = ensure_float(value=data["started_at"])
        completed_at = ensure_float(value=data.get("completed_at"), default=None)
        heartbeat = ensure_float(value=data["heartbeat"])

        return cls(
            key=str(data["key"]),
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            completed_at=completed_at,
            heartbeat=heartbeat,
            result=data.get("result"),
            error=str(data["error"]) if data.get("error") else None,
        )

    def is_stale(self, timeout: float) -> bool:
        """Check if record is stale (likely from crashed process).

        Args:
            timeout: Seconds after which a heartbeat is considered stale

        Returns:
            True if heartbeat is older than timeout
        """
        if self.status != "in_progress":
            return False
        return (time.time() - self.heartbeat) > timeout
