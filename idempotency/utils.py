def ensure_float(value: object, default: float = 0.0) -> float:
    """Convert a value to float, with a default fallback."""
    try:
        return float(value) if isinstance(value, (int, float, str)) else default
    except (TypeError, ValueError):
        return default
