"""Drift detection comparing to baseline.

Functions:
    detect_drift: Detect drift in metric values vs baseline
    compute_baseline: Compute baseline from historical receipts
    is_drifting: Check if drift score exceeds threshold
"""
import statistics
from datetime import datetime, timezone

from proofpack.core.receipt import emit_receipt


def detect_drift(
    receipts: list[dict],
    baseline: dict,
    metric_field: str,
    tenant_id: str = "default"
) -> dict:
    """Detect drift in metric values compared to baseline.

    Extracts metric values from receipts via metric_field, computes current_value
    as mean of recent values, and drift_score as relative change from baseline.

    Args:
        receipts: List of receipt dicts containing metric values
        baseline: Baseline dict with baseline_value
        metric_field: Field name to extract from receipts
        tenant_id: Tenant identifier

    Returns:
        drift_receipt dict
    """
    # Extract metric values from receipts
    values = []
    for receipt in receipts:
        value = receipt.get(metric_field)
        if value is not None:
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                pass

    # Compute current value as mean
    if values:
        current_value = statistics.mean(values)
    else:
        current_value = 0.0

    baseline_value = baseline.get("baseline_value", 0.0)

    # Compute drift score (relative change)
    if baseline_value != 0:
        drift_score = (current_value - baseline_value) / baseline_value
    else:
        drift_score = 0.0 if current_value == 0 else float('inf')

    # Determine direction
    if drift_score > 0.05:
        direction = "increasing"
    elif drift_score < -0.05:
        direction = "decreasing"
    else:
        direction = "stable"

    # Emit drift receipt
    receipt = emit_receipt("drift", {
        "tenant_id": tenant_id,
        "metric": metric_field,
        "baseline_value": baseline_value,
        "current_value": current_value,
        "drift_score": drift_score,
        "direction": direction,
        "window_size": len(receipts),
    })

    return receipt


def compute_baseline(
    receipts: list[dict],
    metric_field: str,
    percentile: int = 50
) -> dict:
    """Compute baseline from historical receipts.

    Pure function - extracts metric values and computes percentile.

    Args:
        receipts: List of historical receipt dicts
        metric_field: Field name to extract from receipts
        percentile: Percentile to use for baseline (default 50 = median)

    Returns:
        Baseline dict with metric, baseline_value, sample_size, computed_at
    """
    # Extract metric values
    values = []
    for receipt in receipts:
        value = receipt.get(metric_field)
        if value is not None:
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                pass

    # Compute baseline value
    if values:
        sorted_values = sorted(values)
        idx = int((percentile / 100) * (len(sorted_values) - 1))
        idx = max(0, min(idx, len(sorted_values) - 1))
        baseline_value = sorted_values[idx]
    else:
        baseline_value = 0.0

    return {
        "metric": metric_field,
        "baseline_value": baseline_value,
        "sample_size": len(values),
        "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def is_drifting(drift_receipt: dict, threshold: float = 0.1) -> bool:
    """Check if drift score exceeds threshold.

    Pure function.

    Args:
        drift_receipt: Drift receipt dict with drift_score
        threshold: Drift threshold (default 0.1 = 10%)

    Returns:
        True if abs(drift_score) > threshold
    """
    drift_score = drift_receipt.get("drift_score", 0.0)
    return abs(drift_score) > threshold
