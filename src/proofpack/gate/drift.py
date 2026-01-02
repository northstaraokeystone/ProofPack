"""Context drift measurement.

Measures how much context has changed since reasoning started.
"""
import time

from proofpack.core.receipt import dual_hash, emit_receipt


def measure_drift(
    initial_context: str | dict,
    current_context: str | dict,
    tenant_id: str = "default"
) -> float:
    """Measure context drift since reasoning started.

    Compares hashes of initial and current context.
    Returns drift_score (0-1):
    - 0.0 = identical context
    - 1.0 = completely different context
    """
    t0 = time.perf_counter()

    # Hash both contexts
    if isinstance(initial_context, dict):
        initial_hash = dual_hash(str(sorted(initial_context.items())))
    else:
        initial_hash = dual_hash(str(initial_context))

    if isinstance(current_context, dict):
        current_hash = dual_hash(str(sorted(current_context.items())))
    else:
        current_hash = dual_hash(str(current_context))

    # If hashes match exactly, no drift
    if initial_hash == current_hash:
        drift_score = 0.0
    else:
        # Calculate character-level similarity between hashes
        # This gives us a rough measure of how different the contexts are
        initial_chars = set(initial_hash)
        current_chars = set(current_hash)

        intersection = len(initial_chars & current_chars)
        union = len(initial_chars | current_chars)

        jaccard = intersection / union if union > 0 else 0.0
        drift_score = 1.0 - jaccard

    elapsed_ms = (time.perf_counter() - t0) * 1000

    emit_receipt("drift_measurement", {
        "initial_hash": initial_hash[:16] + "...",
        "current_hash": current_hash[:16] + "...",
        "drift_score": drift_score,
        "measurement_ms": elapsed_ms
    }, tenant_id=tenant_id)

    return drift_score


def detect_significant_drift(
    drift_score: float,
    threshold: float = 0.3
) -> bool:
    """Detect if drift is significant enough to warrant re-evaluation."""
    return drift_score > threshold


def stoprule_context_drift(drift_score: float, threshold: float = 0.5):
    """Stoprule if context drift exceeds safety threshold."""
    if drift_score > threshold:
        emit_receipt("anomaly", {
            "metric": "context_drift",
            "baseline": threshold,
            "delta": drift_score - threshold,
            "classification": "drift",
            "action": "escalate"
        })
