# Idempotency Guard - Architecture & Plan

> A function-level idempotency guard that prevents duplicate side effects caused
> by retries, race conditions, or replayed events.

## Core Concept

```python
@idempotent(ttl=300)
def create_invoice(user_id, amount):
    charge_card(user_id, amount)  # MUST NOT run twice
    send_email(user_id)
    return {"invoice_id": 123}
```

Same inputs → same effect, **at most once**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    @idempotent decorator                │
├─────────────────────────────────────────────────────────┤
│  1. Compute key (function + args)                       │
│  2. Check store → not found / in_progress / completed   │
│  3. Acquire lock (atomic)                               │
│  4. Execute function                                    │
│  5. Store result + status                               │
│  6. Release lock                                        │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    Store Interface                      │
├─────────────────────────────────────────────────────────┤
│  get(key) → Record | None                               │
│  set(key, record, ttl)                                  │
│  acquire_lock(key, timeout) → bool                      │
│  release_lock(key)                                      │
│  delete(key)                                            │
└─────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   MemoryStore         FileStore          RedisStore
```

### Record Schema

```python
{
    "key": "create_invoice:user_id=123:amount=100",
    "status": "in_progress" | "completed" | "failed",
    "result": <serialized return value>,
    "error": <serialized exception> | None,
    "started_at": 1700000000.0,
    "completed_at": 1700000005.0 | None,
    "heartbeat": 1700000003.0  # for crash detection
}
```

---

## API Design

```python
# Basic usage
@idempotent(ttl=300)
def create_invoice(user_id, amount): ...

# Explicit key function
@idempotent(key=lambda user_id, amount: f"invoice:{user_id}:{amount}")
def create_invoice(user_id, amount): ...

# Duplicate behavior
@idempotent(on_duplicate="return")  # return stored result (default)
@idempotent(on_duplicate="raise")   # raise DuplicateExecutionError
@idempotent(on_duplicate="wait")    # block until first completes

# Failure handling
@idempotent(on_failure="unlock")    # allow retry on failure (default)
@idempotent(on_failure="lock")      # failures are also idempotent

# Storage backend
@idempotent(store=MemoryStore())
@idempotent(store=FileStore("/tmp/idempotency"))
@idempotent(store=RedisStore(redis_client))

# Async support
@idempotent(ttl=300)
async def create_invoice(user_id, amount): ...
```

---

## Edge Cases & Solutions

| Edge Case | Problem | Solution |
|-----------|---------|----------|
| **Crash mid-execution** | Key stuck as `in_progress` forever | Heartbeat + timeout takeover. If `heartbeat` older than threshold, assume dead and allow retry |
| **Concurrent calls** | Race condition on check-then-set | Atomic lock acquisition (Redis SETNX, file locks, threading.Lock) |
| **Function raises** | Should failure be idempotent? | Configurable via `on_failure`. Default: unlock so retry is allowed |
| **Unhashable args** | dicts, objects can't be hashed | JSON serialization with sorted keys. User can provide custom `key` function |
| **Result not serializable** | Can't store lambdas, connections | Store `None` for result, log warning. Or raise if `on_duplicate="return"` |
| **TTL expires mid-wait** | Waiting caller gets stale state | Re-check after wait completes |
| **Async + sync mix** | Can't use threading.Lock in async | Detect async context, use asyncio.Lock or async Redis ops |
| **Process isolation** | MemoryStore doesn't share across processes | Document limitation. Use FileStore/RedisStore for multi-process |

---

## Module Structure

```
idempotency/
├── stores/
│   ├── __init__.py
│   ├── base.py          # Store protocol/ABC
│   ├── memory.py        # MemoryStore (dict + threading.Lock)
│   ├── file.py          # FileStore (JSON files + file locks)
│   └── redis.py         # RedisStore (Redis + Lua scripts)
├── __init__.py          # public API exports
├── decorator.py         # @idempotent implementation
├── key.py               # key generation logic
├── record.py            # Record dataclass
└── exceptions.py        # Custom exceptions for the library
```

---

## To-Do

### Advanced Features
- [ ] `on_duplicate="raise"` and `"wait"` modes
- [ ] `on_failure="lock"` mode
- [ ] Crash recovery (heartbeat + timeout takeover)
- [ ] Custom `key` function support
- [ ] Async support (`async def` detection + async stores)

### Polish
- [ ] Comprehensive edge case tests
- [ ] Documentation (README, docstrings)
- [ ] CI/CD setup

---

## Out of Scope (Deliberate)

- **Distributed transactions** - we guard single functions, not sagas
- **Result caching for performance** - use `functools.lru_cache` for that
- **Automatic retries** - use `tenacity` for that
- **HTTP middleware** - this is function-level, not request-level
- **Database-backed store** - Redis/file covers most cases

---

## Dependencies

**Required**: None (stdlib only for core)

**Optional**:
- `redis` - for RedisStore
- `filelock` - for cross-process file locking (or use `fcntl`)

**Dev**:
- `pytest`, `pytest-asyncio`
- `ruff`
- `mypy`
