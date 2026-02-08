# Idempotency Guard

> A function-level idempotency guard that prevents duplicate side effects caused by retries, race conditions, or replayed events.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## The Problem

You write a function that charges a credit card, sends an email, or creates a database record. Then:

- The request times out
- The caller retries
- The function runs again
- **The user gets charged twice** 💀

APIs claim to be idempotent, but they often aren't. This library makes idempotency **automatic and declarative** at the function level.

## What This Is (and Isn't)

| This Library | Not This |
|--------------|----------|
| **Execution deduplication** | Result caching |
| **Side-effect protection** | Performance optimization |
| **"Same inputs → same effect, at most once"** | "Don't recompute expensive functions" |

**Use this for:** Payment processing, webhook handlers, job queues, API endpoints with side effects

**Don't use this for:** Speeding up pure functions (use `functools.lru_cache` instead)

## Installation

```bash
pip install idempotency-guard
```

**Optional dependencies:**

```bash
# For Redis support
pip install idempotency-guard[redis]

# For development
pip install idempotency-guard[dev]
```

## Quick Start

```python
from idempotency import idempotent

@idempotent(ttl=300)
def create_invoice(user_id: int, amount: float) -> dict:
    charge_card(user_id, amount)  # MUST NOT run twice
    send_email(user_id)
    return {"invoice_id": 123, "amount": amount}

# First call - executes
result = create_invoice(user_id=1, amount=100.0)

# Second call with same args - returns stored result, no side effects
result = create_invoice(user_id=1, amount=100.0)  # No charge, no email!

# Different args - executes again
result = create_invoice(user_id=2, amount=200.0)
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  1. Compute key from function name + arguments          │
│  2. Check store: not found / in_progress / completed    │
│  3. Acquire lock (atomic, prevents race conditions)     │
│  4. Execute function                                     │
│  5. Store result + status                               │
│  6. Release lock                                        │
└─────────────────────────────────────────────────────────┘
```

**Key insight:** The library tracks execution state (`in_progress`, `completed`, `failed`), not just results. This prevents race conditions and handles crashes gracefully.

## Storage Backends

Choose the right store for your deployment:

| Store | Persistent | Multi-Process | Multi-Server | Use Case |
|-------|------------|---------------|--------------|----------|
| **MemoryStore** | ❌ | ❌ | ❌ | Single-process apps, testing |
| **FileStore** | ✅ | ✅ | ❌ | Gunicorn workers, Celery tasks |
| **RedisStore** | ✅ | ✅ | ✅ | Distributed systems, microservices |

### MemoryStore (Default)

```python
from idempotency import idempotent

@idempotent(ttl=300)  # Uses MemoryStore by default
def my_function():
    ...
```

### FileStore

```python
from idempotency import idempotent
from idempotency.stores import FileStore

store = FileStore("/tmp/idempotency")

@idempotent(store=store, ttl=300)
def my_function():
    ...
```

**Features:**
- JSON file persistence
- Cross-process locking with `fcntl`
- Works on Linux and macOS

### RedisStore

```python
import redis
from idempotency import idempotent
from idempotency.stores import RedisStore

redis_client = redis.Redis(host="localhost", port=6379)
store = RedisStore(redis_client, prefix="myapp:")

@idempotent(store=store, ttl=300)
def my_function():
    ...
```

**Features:**
- Atomic lock acquisition with Redis SET NX
- Built-in TTL support
- Safe for distributed systems

## Configuration Options

### TTL (Time-to-Live)

How long to remember that an operation completed:

```python
@idempotent(ttl=300)  # 5 minutes
def create_invoice(user_id, amount):
    ...
```

After TTL expires, the operation can run again. This prevents permanent locks and handles legitimate retries.

### Custom Key Function

By default, the key is generated from function name + all arguments. You can customize this:

```python
@idempotent(
    ttl=300,
    key=lambda user_id, amount: f"invoice:{user_id}"
)
def create_invoice(user_id, amount):
    """Only one invoice per user, regardless of amount."""
    ...
```

### Duplicate Behavior

Control what happens when a duplicate call is detected:

```python
# Return stored result (default)
@idempotent(on_duplicate="return")
def create_invoice(user_id, amount):
    ...

# Raise an error
@idempotent(on_duplicate="raise")
def critical_operation(operation_id):
    ...

# Wait for first execution to complete
@idempotent(on_duplicate="wait")
def long_running_task(task_id):
    ...
```

### Failure Handling

Control whether failures are idempotent:

```python
# Allow retry on failure (default)
@idempotent(on_failure="unlock")
def flaky_api_call():
    ...

# Failures are also idempotent (no retry)
@idempotent(on_failure="lock")
def critical_operation():
    ...
```

## Real-World Examples

### Webhook Handler

```python
from idempotency import idempotent
from idempotency.stores import RedisStore

store = RedisStore(redis_client, prefix="webhooks:")

@idempotent(store=store, ttl=3600, on_duplicate="return")
def handle_stripe_webhook(event_id: str, payload: dict):
    """Process Stripe webhook - may be delivered multiple times."""
    if payload["type"] == "payment_intent.succeeded":
        charge_id = payload["data"]["object"]["id"]
        update_order_status(charge_id, "paid")
        send_confirmation_email(charge_id)
    
    return {"status": "processed"}
```

### Background Job

```python
from idempotency import idempotent
from idempotency.stores import FileStore

store = FileStore("/var/lib/myapp/idempotency")

@idempotent(store=store, ttl=86400)  # 24 hours
def process_daily_report(date: str):
    """Generate daily report - should only run once per day."""
    data = fetch_analytics(date)
    report = generate_pdf(data)
    upload_to_s3(report, f"reports/{date}.pdf")
    notify_team(f"Report for {date} is ready")
    
    return {"report_url": f"s3://reports/{date}.pdf"}
```

### API Endpoint with Retries

```python
from idempotency import idempotent
from idempotency.stores import RedisStore

store = RedisStore(redis_client)

@idempotent(
    store=store,
    ttl=300,
    key=lambda user_id, **kwargs: f"order:{user_id}:{kwargs.get('idempotency_key')}"
)
def create_order(user_id: int, items: list, idempotency_key: str):
    """Create order with client-provided idempotency key."""
    order = db.create_order(user_id=user_id, items=items)
    charge_payment(order.total)
    send_confirmation(order.id)
    
    return {"order_id": order.id, "total": order.total}
```

## Error Handling

The decorator preserves exception types and re-raises them:

```python
@idempotent(ttl=300)
def risky_operation():
    raise ValueError("Something went wrong")

try:
    risky_operation()
except ValueError as e:
    print(f"Caught: {e}")  # Original exception type preserved
```

By default, failures unlock the operation so it can be retried. Use `on_failure="lock"` to make failures idempotent too.

## Testing

The library includes utilities for testing:

```python
from idempotency.stores import MemoryStore

def test_my_function():
    store = MemoryStore()
    
    @idempotent(store=store, ttl=300)
    def my_function(x):
        return x * 2
    
    # First call
    assert my_function(5) == 10
    
    # Second call (cached)
    assert my_function(5) == 10
    
    # Clear store between tests
    store.clear()
```

## Performance

**MemoryStore:**
- ~0.1ms overhead per call
- Thread-safe with minimal locking

**FileStore:**
- ~1-5ms overhead (disk I/O)
- Safe for multi-process scenarios

**RedisStore:**
- ~1-3ms overhead (network + Redis)
- Scales horizontally

The overhead is negligible compared to typical side effects (API calls, database writes, emails).

## Limitations

**Not supported:**
- Windows file locking (FileStore uses `fcntl`, POSIX only)
- Async functions (coming in Phase 3)
- Distributed transactions across multiple functions
- Automatic retry logic (use `tenacity` for that)

**By design:**
- Results must be JSON-serializable (or use `on_duplicate="raise"`)
- TTL is required (prevents permanent locks)
- Not a replacement for database transactions

## Development

```bash
# Clone the repo
git clone https://github.com/yourusername/idempotency-guard.git
cd idempotency-guard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy idempotency
```

## Contributing

Contributions welcome! Please:

1. Write tests for new features
2. Follow existing code style (ruff + mypy)
3. Update documentation
4. Add examples for new functionality

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Why This Library Exists

Most systems rely on:
- API idempotency headers (external, caller-dependent)
- Manual guards scattered everywhere (inconsistent, error-prone)
- Hope (not a strategy)

This library provides a **missing middle layer** between business logic and infrastructure guarantees. It makes idempotency a first-class concept with a clean, declarative API.

## Acknowledgments

Inspired by:
- Stripe's idempotency implementation
- The need for better webhook handling
- Too many production incidents from duplicate charges

---

**Made with ❤️ for backend engineers who are tired of duplicate side effects.**
