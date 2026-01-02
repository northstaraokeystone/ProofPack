"""Pattern scanning on receipt streams."""
import time
from collections import defaultdict

from proofpack.core.receipt import dual_hash, emit_receipt


def scan(stream: list, tenant_id: str = "default") -> dict:
    """Scan receipt stream for patterns per QED v7:288-292 HUNTER agent.

    SLO: ≤100ms p95
    """
    t0 = time.perf_counter()

    # Track baseline metrics
    type_counts = defaultdict(int)
    timestamps = []

    for receipt in stream:
        rtype = receipt.get("receipt_type", "unknown")
        type_counts[rtype] += 1
        if "ts" in receipt:
            timestamps.append(receipt["ts"])

    # Identify patterns with signatures
    patterns_found = []
    confidence_scores = {}

    for rtype, count in type_counts.items():
        if count >= 2:  # Pattern threshold
            pattern_id = f"pattern_{rtype}"
            signature = dual_hash(f"{rtype}:{count}")[:16]
            patterns_found.append({
                "pattern_id": pattern_id,
                "count": count,
                "signature": signature
            })
            # Confidence based on frequency
            confidence_scores[pattern_id] = min(1.0, count / max(len(stream), 1))

    baseline_metrics = {
        "type_distribution": dict(type_counts),
        "stream_size": len(stream),
        "unique_types": len(type_counts)
    }

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return emit_receipt("scan", {
        "stream_size": len(stream),
        "patterns_found": patterns_found,
        "confidence_scores": confidence_scores,
        "baseline_metrics": baseline_metrics,
        "scan_duration_ms": round(elapsed_ms, 2)
    }, tenant_id=tenant_id)
