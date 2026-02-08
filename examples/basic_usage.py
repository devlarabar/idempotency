"""Basic usage examples for idempotency guard."""

from idempotency import idempotent


# Example 1: Basic idempotency
@idempotent(ttl=300)
def create_invoice(user_id, amount):
    """Create an invoice and charge the user."""
    print(f"💳 Charging user {user_id} ${amount}")
    print(f"📧 Sending invoice email to user {user_id}")
    return {"invoice_id": 12345, "amount": amount, "user_id": user_id}


# Example 2: Custom key function
@idempotent(
    ttl=300,
    key=lambda user_id, amount: f"invoice:{user_id}"
)
def create_invoice_per_user(user_id, amount):
    """Only one invoice per user, regardless of amount."""
    print(f"Creating invoice for user {user_id}")
    return {"invoice_id": 67890, "user_id": user_id}


# Example 3: Raise on duplicate
@idempotent(ttl=300, on_duplicate="raise")
def critical_operation(operation_id):
    """Operation that should never be duplicated."""
    print(f"⚠️  Executing critical operation {operation_id}")
    return {"status": "completed"}


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Basic Idempotency")
    print("=" * 60)

    # First call - executes
    result1 = create_invoice(user_id=123, amount=100)
    print(f"Result: {result1}\n")

    # Second call with same args - returns cached result
    print("Calling again with same arguments...")
    result2 = create_invoice(user_id=123, amount=100)
    print(f"Result: {result2}")
    print("Notice: No charging or email sending happened!\n")

    # Different args - executes again
    print("Calling with different arguments...")
    result3 = create_invoice(user_id=456, amount=200)
    print(f"Result: {result3}\n")

    print("=" * 60)
    print("Example 2: Custom Key Function")
    print("=" * 60)

    # First call
    result1 = create_invoice_per_user(user_id=789, amount=100)
    print(f"Result: {result1}\n")

    # Different amount, same user - still cached!
    print("Calling with different amount but same user...")
    result2 = create_invoice_per_user(user_id=789, amount=500)
    print(f"Result: {result2}")
    print("Notice: Amount is still 100 from first call!\n")

    print("=" * 60)
    print("Example 3: Raise on Duplicate")
    print("=" * 60)

    # First call succeeds
    result = critical_operation(operation_id="OP-001")
    print(f"Result: {result}\n")

    # Second call raises error
    print("Trying to call again...")
    try:
        critical_operation(operation_id="OP-001")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("This is expected - duplicate execution prevented!")
