"""Resource tracking per QED v7:315-317."""
import time
from datetime import datetime, timezone

from ledger.core import emit_receipt

# Track last measurement time for cycle duration
_last_measurement = None


def track_resources(tenant_id: str = "default") -> dict:
    """Monitor compute, memory, and cost usage.

    V1 implementation uses placeholder values. Structure matters more than real metrics.
    Real metrics can be obtained via psutil if available.
    """
    global _last_measurement

    now = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Calculate cycle duration
    if _last_measurement is not None:
        cycle_duration_ms = int((now - _last_measurement) * 1000)
    else:
        cycle_duration_ms = 0
    _last_measurement = now

    # Try to get real metrics via psutil, fallback to placeholders
    try:
        import psutil
        proc = psutil.Process()
        compute_used = proc.cpu_times().user + proc.cpu_times().system
        memory_used = proc.memory_info().rss / (1024 * 1024)  # MB
        io_ops = proc.io_counters().read_count + proc.io_counters().write_count
    except (ImportError, AttributeError):
        # Placeholder values for v1
        compute_used = 0.0
        memory_used = 0.0
        io_ops = 0

    return emit_receipt("resource", {
        "compute_used": round(compute_used, 3),
        "memory_used": round(memory_used, 2),
        "io_operations": io_ops,
        "cost": 0.0,  # Placeholder for cost tracking
        "cycle_duration_ms": cycle_duration_ms,
        "timestamp": timestamp
    }, tenant_id=tenant_id)
