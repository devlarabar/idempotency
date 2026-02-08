"""Examples of using different storage backends."""


from idempotency import idempotent
from idempotency.stores import FileStore

# Example 1: MemoryStore (default, single process only)
print("=" * 60)
print("Example 1: MemoryStore (in-memory, single process)")
print("=" * 60)


@idempotent(ttl=300)
def create_invoice_memory(user_id: int, amount: float) -> dict:
    """Create an invoice (using default MemoryStore)."""
    print(f"  → Creating invoice for user {user_id}, amount ${amount}")
    return {"invoice_id": 123, "user_id": user_id, "amount": amount}


# First call - executes
result1 = create_invoice_memory(user_id=1, amount=100.0)
print(f"First call result: {result1}")

# Second call - returns cached result
result2 = create_invoice_memory(user_id=1, amount=100.0)
print(f"Second call result: {result2}")

# Different args - executes again
result3 = create_invoice_memory(user_id=2, amount=200.0)
print(f"Different args result: {result3}")

print()

# Example 2: FileStore (persistent, multi-process safe)
print("=" * 60)
print("Example 2: FileStore (persistent, multi-process safe)")
print("=" * 60)

file_store = FileStore("/tmp/idempotency_demo")


@idempotent(store=file_store, ttl=300)
def create_invoice_file(user_id: int, amount: float) -> dict:
    """Create an invoice (using FileStore)."""
    print(f"  → Creating invoice for user {user_id}, amount ${amount}")
    return {"invoice_id": 456, "user_id": user_id, "amount": amount}


# First call - executes
result1 = create_invoice_file(user_id=1, amount=100.0)
print(f"First call result: {result1}")

# Second call - returns cached result (even across process restarts!)
result2 = create_invoice_file(user_id=1, amount=100.0)
print(f"Second call result: {result2}")

print()

# Example 3: RedisStore (distributed, multi-server safe)
print("=" * 60)
print("Example 3: RedisStore (distributed, multi-server safe)")
print("=" * 60)

try:
    import redis

    from idempotency.stores import RedisStore

    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    redis_client.ping()  # Test connection

    redis_store = RedisStore(redis_client, prefix="myapp:")

    @idempotent(store=redis_store, ttl=300)
    def create_invoice_redis(user_id: int, amount: float) -> dict:
        """Create an invoice (using RedisStore)."""
        print(f"  → Creating invoice for user {user_id}, amount ${amount}")
        return {"invoice_id": 789, "user_id": user_id, "amount": amount}

    # First call - executes
    result1 = create_invoice_redis(user_id=1, amount=100.0)
    print(f"First call result: {result1}")

    # Second call - returns cached result
    result2 = create_invoice_redis(user_id=1, amount=100.0)
    print(f"Second call result: {result2}")

    print("\n✅ RedisStore example completed successfully!")

except ImportError:
    print("⚠️  Redis not installed. Install with: pip install redis")
except Exception as e:
    print(f"⚠️  Redis not available: {e}")
    print("   Make sure Redis is running: redis-server")

print()

# Example 4: Comparing stores
print("=" * 60)
print("Example 4: Store Comparison")
print("=" * 60)

print("""
Store Comparison:

┌─────────────┬────────────┬──────────────┬─────────────┐
│ Store       │ Persistent │ Multi-Process│ Multi-Server│
├─────────────┼────────────┼──────────────┼─────────────┤
│ MemoryStore │     ❌     │      ❌      │      ❌     │
│ FileStore   │     ✅     │      ✅      │      ❌     │
│ RedisStore  │     ✅     │      ✅      │      ✅     │
└─────────────┴────────────┴──────────────┴─────────────┘

Use Cases:

• MemoryStore: Single-process apps, testing, development
• FileStore: Multi-process apps (gunicorn, celery), local persistence
• RedisStore: Distributed systems, microservices, high availability

Performance:
• MemoryStore: Fastest (in-memory)
• FileStore: Medium (disk I/O)
• RedisStore: Fast (network + Redis speed)
""")

# Cleanup
print("Cleaning up demo files...")
file_store.clear()
print("✅ Phase 2 complete!")
