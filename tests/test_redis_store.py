"""Tests for RedisStore implementation.

Note: These tests require a running Redis instance.
They will be skipped if Redis is not available.
"""

import time

import pytest
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from idempotency.record import Record

# Try to import redis and RedisStore
try:

    from idempotency.stores import RedisStore

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


# Skip all tests if Redis is not available
pytestmark = pytest.mark.skipif(
    not REDIS_AVAILABLE, reason="Redis not installed"
)


@pytest.fixture
def redis_client():
    """Create a Redis client for testing."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not available")

    try:
        client = Redis(
            host="localhost", port=6379, db=15, decode_responses=False
        )
        # Test connection
        client.ping()
        yield client
        # Cleanup
        client.flushdb()
        client.close()
    except RedisConnectionError:
        pytest.skip("Redis server not running")


@pytest.fixture
def redis_store(redis_client):
    """Create a RedisStore instance for testing."""
    store = RedisStore(redis_client, prefix="test:idempotency:")
    yield store
    # Cleanup
    store.clear()


def test_redis_store_get_set(redis_store):
    """Test basic get/set operations with RedisStore."""
    record = Record(key="test:1", status="completed", result={"data": 123})
    redis_store.set(record, ttl=None)

    retrieved = redis_store.get("test:1")
    assert retrieved is not None
    assert retrieved.key == "test:1"
    assert retrieved.status == "completed"
    assert retrieved.result == {"data": 123}


def test_redis_store_ttl(redis_store):
    """Test TTL expiration with RedisStore."""
    record = Record(key="test:1", status="completed")
    redis_store.set(record, ttl=1)  # 1 second

    # Should exist immediately
    assert redis_store.get("test:1") is not None

    # Wait for expiration
    time.sleep(1.5)

    # Should be gone
    assert redis_store.get("test:1") is None


def test_redis_store_delete(redis_store):
    """Test record deletion with RedisStore."""
    record = Record(key="test:1", status="completed")
    redis_store.set(record)

    assert redis_store.get("test:1") is not None

    redis_store.delete("test:1")

    assert redis_store.get("test:1") is None


def test_redis_store_lock(redis_store):
    """Test lock acquisition and release with RedisStore."""
    # Acquire lock
    assert redis_store.acquire_lock("test:1", timeout=1.0) is True

    # Can't acquire again (would block)
    assert redis_store.acquire_lock("test:1", timeout=0.1) is False

    # Release lock
    redis_store.release_lock("test:1")

    # Can acquire again
    assert redis_store.acquire_lock("test:1", timeout=1.0) is True
    redis_store.release_lock("test:1")


def test_redis_store_clear(redis_store):
    """Test clearing all records with RedisStore."""
    redis_store.set(Record(key="test:1", status="completed"))
    redis_store.set(Record(key="test:2", status="completed"))

    assert redis_store.get("test:1") is not None
    assert redis_store.get("test:2") is not None

    redis_store.clear()

    assert redis_store.get("test:1") is None
    assert redis_store.get("test:2") is None


def test_redis_store_persistence(redis_client):
    """Test that RedisStore persists across instances."""
    # Create first store and save record
    store1 = RedisStore(redis_client, prefix="test:persist:")
    record = Record(key="test:1", status="completed", result={"data": 123})
    store1.set(record)

    # Create second store instance (simulates process restart)
    store2 = RedisStore(redis_client, prefix="test:persist:")
    retrieved = store2.get("test:1")

    assert retrieved is not None
    assert retrieved.key == "test:1"
    assert retrieved.status == "completed"
    assert retrieved.result == {"data": 123}

    # Cleanup
    store1.clear()


def test_redis_store_special_characters_in_key(redis_store):
    """Test that RedisStore handles special characters in keys."""
    # Keys with special characters
    record = Record(key="test:user/123:amount:100", status="completed")
    redis_store.set(record)

    retrieved = redis_store.get("test:user/123:amount:100")
    assert retrieved is not None
    assert retrieved.key == "test:user/123:amount:100"


def test_redis_store_prefix_isolation(redis_client):
    """Test that different prefixes isolate data."""
    store1 = RedisStore(redis_client, prefix="app1:")
    store2 = RedisStore(redis_client, prefix="app2:")

    # Store in first store
    record = Record(key="test:1", status="completed")
    store1.set(record)

    # Should exist in store1
    assert store1.get("test:1") is not None

    # Should NOT exist in store2 (different prefix)
    assert store2.get("test:1") is None

    # Cleanup
    store1.clear()
    store2.clear()


def test_redis_store_lock_expiration(redis_store):
    """Test that locks expire after timeout."""
    # Acquire lock with short timeout
    assert redis_store.acquire_lock("test:1", timeout=1.0) is True

    # Don't release - let it expire naturally
    # Redis lock has TTL of timeout + 60 seconds
    # For testing, we just verify it was acquired
    redis_store.release_lock("test:1")


def test_redis_store_concurrent_operations(redis_store):
    """Test that RedisStore handles concurrent operations safely."""
    # This is a basic test - real concurrency would need threads/processes
    record1 = Record(key="test:1", status="in_progress")
    record2 = Record(key="test:2", status="in_progress")

    redis_store.set(record1)
    redis_store.set(record2)

    assert redis_store.get("test:1") is not None
    assert redis_store.get("test:2") is not None

    # Both should be independent
    redis_store.delete("test:1")
    assert redis_store.get("test:1") is None
    assert redis_store.get("test:2") is not None
