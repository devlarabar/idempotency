"""Tests for store implementations."""

import tempfile
import time
from pathlib import Path

from idempotency.record import Record
from idempotency.stores import FileStore, MemoryStore


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


# FileStore Tests


def test_file_store_get_set():
    """Test basic get/set operations with FileStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        record = Record(key="test:1", status="completed", result={"data": 123})
        store.set(record, ttl=None)

        retrieved = store.get("test:1")
        assert retrieved is not None
        assert retrieved.key == "test:1"
        assert retrieved.status == "completed"
        assert retrieved.result == {"data": 123}


def test_file_store_ttl():
    """Test TTL expiration with FileStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        record = Record(key="test:1", status="completed")
        store.set(record, ttl=0.1)  # 100ms

        # Should exist immediately
        assert store.get("test:1") is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be gone
        assert store.get("test:1") is None


def test_file_store_delete():
    """Test record deletion with FileStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        record = Record(key="test:1", status="completed")
        store.set(record)

        assert store.get("test:1") is not None

        store.delete("test:1")

        assert store.get("test:1") is None


def test_file_store_lock():
    """Test lock acquisition and release with FileStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        # Acquire lock
        assert store.acquire_lock("test:1", timeout=1.0) is True

        # Can't acquire again (would block)
        assert store.acquire_lock("test:1", timeout=0.1) is False

        # Release lock
        store.release_lock("test:1")

        # Can acquire again
        assert store.acquire_lock("test:1", timeout=1.0) is True
        store.release_lock("test:1")


def test_file_store_clear():
    """Test clearing all records with FileStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        store.set(Record(key="test:1", status="completed"))
        store.set(Record(key="test:2", status="completed"))

        assert store.get("test:1") is not None
        assert store.get("test:2") is not None

        store.clear()

        assert store.get("test:1") is None
        assert store.get("test:2") is None


def test_file_store_persistence():
    """Test that FileStore persists across instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create first store and save record
        store1 = FileStore(tmpdir)
        record = Record(key="test:1", status="completed", result={"data": 123})
        store1.set(record)

        # Create second store instance (simulates process restart)
        store2 = FileStore(tmpdir)
        retrieved = store2.get("test:1")

        assert retrieved is not None
        assert retrieved.key == "test:1"
        assert retrieved.status == "completed"
        assert retrieved.result == {"data": 123}


def test_file_store_special_characters_in_key():
    """Test that FileStore handles special characters in keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)

        # Keys with special characters
        record = Record(
            key="test:user/123:amount:100",
            status="completed"
        )
        store.set(record)

        retrieved = store.get("test:user/123:amount:100")
        assert retrieved is not None
        assert retrieved.key == "test:user/123:amount:100"


def test_file_store_directory_creation():
    """Test that FileStore creates directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = Path(tmpdir) / "nested" / "path"
        store = FileStore(nested_dir)

        # Directory should be created
        assert nested_dir.exists()
        assert nested_dir.is_dir()

        # Should be able to store records
        record = Record(key="test:1", status="completed")
        store.set(record)
        assert store.get("test:1") is not None
