"""Entropy module - re-exports from quantum and cycle for convenience."""
from loop.src.quantum import (
    shannon_entropy,
    entropy_delta,
    stoprule_entropy_violation,
)
from loop.src.cycle import compute_stream_entropy


def system_entropy(receipts: list) -> float:
    """Compute entropy of receipt stream."""
    return compute_stream_entropy(receipts)


def entropy_conservation(cycle_data: dict) -> dict:
    """Check entropy conservation across a cycle.

    Args:
        cycle_data: Dict with 'sensed', 'emitted', 'work' keys

    Returns:
        Dict with 'valid', 'entropy_in', 'entropy_out', 'delta' keys
    """
    sensed = cycle_data.get("sensed", [])
    emitted = cycle_data.get("emitted", [])
    work = cycle_data.get("work", {})

    # Compute entropy of input receipts
    entropy_in = system_entropy(sensed) if sensed else 0.0

    # Compute entropy of output receipts
    entropy_out = system_entropy(emitted) if emitted else 0.0

    # Work adds entropy (work is energy converted to entropy)
    work_entropy = (work.get("cpu_ms", 0) + work.get("io_ops", 0) * 10) / 1000.0

    # Entropy cannot decrease without work (second law)
    delta = entropy_out - entropy_in

    # Conservation valid if entropy increased or work was done
    valid = delta >= 0 or work_entropy >= abs(delta)

    return {
        "valid": valid,
        "entropy_in": entropy_in,
        "entropy_out": entropy_out,
        "delta": delta,
        "work_entropy": work_entropy,
    }


__all__ = [
    "shannon_entropy",
    "entropy_delta",
    "stoprule_entropy_violation",
    "compute_stream_entropy",
    "system_entropy",
    "entropy_conservation",
]
