"""Tests for store implementations."""

import time

from idempotency.record import Record
from idempotency.stores import MemoryStore


def test_memory_store_get_set():
    """Test basic get/set operations."""
    store = MemoryStore()

    record = Record(key="test:1", status="completed", result={"data": 123})
    store.set(record, ttl=None)

    retrieved = store.get("test:1")
    assert retrieved is not None
    assert retrieved.key == "test:1"
    assert retrieved.status == "completed"
    assert retrieved.result == {"data": 123}


def test_memory_store_ttl():
    """Test TTL expiration."""
    store = MemoryStore()

    record = Record(key="test:1", status="completed")
    store.set(record, ttl=0.1)  # 100ms

    # Should exist immediately
    assert store.get("test:1") is not None

    # Wait for expiration
    time.sleep(0.15)

    # Should be gone
    assert store.get("test:1") is None


def test_memory_store_delete():
    """Test record deletion."""
    store = MemoryStore()

    record = Record(key="test:1", status="completed")
    store.set(record)

    assert store.get("test:1") is not None

    store.delete("test:1")

    assert store.get("test:1") is None


def test_memory_store_lock():
    """Test lock acquisition and release."""
    store = MemoryStore()

    # Acquire lock
    assert store.acquire_lock("test:1", timeout=1.0) is True

    # Can't acquire again (would block)
    assert store.acquire_lock("test:1", timeout=0.1) is False

    # Release lock
    store.release_lock("test:1")

    # Can acquire again
    assert store.acquire_lock("test:1", timeout=1.0) is True
    store.release_lock("test:1")


def test_memory_store_clear():
    """Test clearing all records."""
    store = MemoryStore()

    store.set(Record(key="test:1", status="completed"))
    store.set(Record(key="test:2", status="completed"))

    assert store.get("test:1") is not None
    assert store.get("test:2") is not None

    store.clear()

    assert store.get("test:1") is None
    assert store.get("test:2") is None


def test_record_to_dict():
    """Test record serialization to dict."""
    record = Record(
        key="test:1",
        status="completed",
        result={"data": 123},
        error=None
    )

    data = record.to_dict()

    assert data["key"] == "test:1"
    assert data["status"] == "completed"
    assert data["result"] == {"data": 123}
    assert data["error"] is None
    assert "started_at" in data
    assert "heartbeat" in data


def test_record_from_dict():
    """Test record deserialization from dict."""
    data = {
        "key": "test:1",
        "status": "completed",
        "started_at": 1700000000.0,
        "completed_at": 1700000005.0,
        "heartbeat": 1700000003.0,
        "result": {"data": 123},
        "error": None,
    }

    record = Record.from_dict(data)

    assert record.key == "test:1"
    assert record.status == "completed"
    assert record.result == {"data": 123}
    assert record.started_at == 1700000000.0


def test_record_is_stale():
    """Test stale record detection."""
    record = Record(key="test:1", status="in_progress")

    # Fresh record
    assert record.is_stale(timeout=10.0) is False

    # Manually set old heartbeat
    record.heartbeat = time.time() - 15.0

    # Should be stale
    assert record.is_stale(timeout=10.0) is True

    # Completed records are never stale
    record.status = "completed"
    assert record.is_stale(timeout=10.0) is False
