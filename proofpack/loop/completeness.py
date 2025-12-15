"""Completeness Module - Measure L0-L4 receipt coverage.

Detect when the system achieves mathematical self-auditing:
when L4 receipts (loop_cycle, completeness) inform L0 processing.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

from proofpack.core.receipt import emit_receipt

# Receipt levels and expected types
RECEIPT_LEVELS = {
    0: "Telemetry",
    1: "Agents",
    2: "Decisions",
    3: "Quality",
    4: "Meta",
}

EXPECTED_TYPES_BY_LEVEL = {
    0: ["qed_window", "qed_manifest", "qed_batch", "ingest"],
    1: ["anomaly", "alert", "remediation", "pattern_match"],
    2: ["brief", "packet", "attach", "consistency"],
    3: ["health", "effectiveness", "wound", "gap"],
    4: ["loop_cycle", "completeness", "helper_blueprint", "approval"],
}

RECEIPT_LEVEL_MAP = {
    # L0 - Telemetry
    "qed_window": 0,
    "qed_manifest": 0,
    "qed_batch": 0,
    "ingest": 0,
    # L1 - Agents
    "anomaly": 1,
    "alert": 1,
    "remediation": 1,
    "pattern_match": 1,
    "analysis": 1,
    "actuation": 1,
    # L2 - Decisions
    "brief": 2,
    "packet": 2,
    "attach": 2,
    "consistency": 2,
    # L3 - Quality
    "health": 3,
    "effectiveness": 3,
    "wound": 3,
    "gap": 3,
    "harvest": 3,
    # L4 - Meta
    "loop_cycle": 4,
    "completeness": 4,
    "helper_blueprint": 4,
    "approval": 4,
    "sense": 4,
}

# Completeness target
COMPLETENESS_TARGET = 0.999

# Track L4 feedback events
_l4_feedback_events: list = []


def measure_completeness(
    ledger_query_fn: Callable,
    tenant_id: str,
    window_hours: int = 24,
) -> dict:
    """Calculate coverage for each receipt level (L0-L4).

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
        window_hours: Time window in hours (default 24)

    Returns:
        Dict with coverage per level and overall metrics
    """
    # Calculate time window
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=window_hours)).isoformat().replace("+00:00", "Z")

    # Query all receipts
    all_receipts = ledger_query_fn(tenant_id=tenant_id, since=since)

    # Calculate coverage per level
    levels = {}
    for level in range(5):
        level_key = f"L{level}"
        expected_types = EXPECTED_TYPES_BY_LEVEL.get(level, [])

        # Find receipts for this level
        level_receipts = [
            r for r in all_receipts
            if RECEIPT_LEVEL_MAP.get(r.get("receipt_type", ""), -1) == level
        ]

        # Calculate coverage
        types_seen = list(set(r.get("receipt_type") for r in level_receipts))
        coverage = calculate_level_coverage(level_receipts, level, expected_types)

        status = "complete" if coverage >= COMPLETENESS_TARGET else "partial"

        levels[level_key] = {
            "coverage": round(coverage, 4),
            "types_seen": types_seen,
            "status": status,
            "receipt_count": len(level_receipts),
        }

    # Check for L4 feedback (self-verification)
    feedback_active = check_l4_feedback(ledger_query_fn, tenant_id)

    # Overall coverage (average of all levels)
    overall_coverage = sum(
        levels[f"L{i}"]["coverage"] for i in range(5)
    ) / 5

    # Self-verifying: L4 coverage > 0 AND feedback active
    self_verifying = levels["L4"]["coverage"] > 0 and feedback_active

    result = {
        "levels": levels,
        "feedback_active": feedback_active,
        "self_verifying": self_verifying,
        "overall_coverage": round(overall_coverage, 4),
    }

    # Emit completeness receipt (L4)
    emit_receipt(
        "completeness",
        {
            "tenant_id": tenant_id,
            "levels": levels,
            "feedback_active": feedback_active,
            "self_verifying": self_verifying,
            "overall_coverage": result["overall_coverage"],
        },
    )

    return result


def check_l4_feedback(
    ledger_query_fn: Callable,
    tenant_id: str = "default",
) -> bool:
    """Check if L4 receipts have influenced L0 processing.

    Self-verification: When the system uses L4 insights (loop_cycle,
    completeness) to improve L0 processing (tune parameters, adjust
    thresholds), it achieves mathematical self-auditing.

    This is NOT AGI—it's a system that can verify its own correctness.

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier

    Returns:
        True if L4 feedback loop is active
    """
    # Check for feedback events
    if _l4_feedback_events:
        # Has explicit feedback been recorded
        return True

    # Check for implicit feedback: L0 receipts that reference L4 data
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat().replace("+00:00", "Z")

    try:
        receipts = ledger_query_fn(tenant_id=tenant_id, since=since)
    except Exception:
        return False

    # Look for L0 receipts that contain loop_cycle or completeness references
    l0_receipts = [
        r for r in receipts
        if RECEIPT_LEVEL_MAP.get(r.get("receipt_type", ""), -1) == 0
    ]

    for receipt in l0_receipts:
        # Check if receipt references L4 data
        receipt_str = str(receipt)
        if "loop_cycle" in receipt_str or "completeness" in receipt_str:
            return True
        # Check for tuning based on L4
        if receipt.get("tuned_from_l4") or receipt.get("feedback_source") == "L4":
            return True

    return False


def calculate_level_coverage(
    receipts: list,
    level: int,
    expected_types: list,
) -> float:
    """Calculate coverage for a receipt level.

    Coverage = unique_types_seen / expected_types

    Args:
        receipts: List of receipts for this level
        level: Level number (0-4)
        expected_types: List of expected receipt types for this level

    Returns:
        Coverage ratio 0-1
    """
    if not expected_types:
        return 1.0  # No expected types = complete

    # Get unique types seen
    types_seen = set(r.get("receipt_type") for r in receipts)

    # Calculate overlap with expected
    expected_set = set(expected_types)
    matched = types_seen.intersection(expected_set)

    return len(matched) / len(expected_set)


def record_l4_feedback(
    source: str,
    target: str,
    action: str,
    tenant_id: str = "default",
) -> None:
    """Record an L4 feedback event.

    Called when L4 insights are used to modify L0 processing.

    Args:
        source: L4 receipt type that triggered the feedback
        target: L0 component that was modified
        action: What modification was made
        tenant_id: Tenant identifier
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _l4_feedback_events.append({
        "ts": now,
        "source": source,
        "target": target,
        "action": action,
        "tenant_id": tenant_id,
    })

    # Emit feedback receipt
    emit_receipt(
        "l4_feedback",
        {
            "tenant_id": tenant_id,
            "source": source,
            "target": target,
            "action": action,
        },
    )


def get_completeness_history(
    ledger_query_fn: Callable,
    tenant_id: str,
    days: int = 7,
) -> list:
    """Get completeness measurements over time.

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
        days: Number of days to look back

    Returns:
        List of completeness measurements
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    receipts = ledger_query_fn(tenant_id=tenant_id, since=since)

    # Filter completeness receipts
    completeness_receipts = [
        r for r in receipts if r.get("receipt_type") == "completeness"
    ]

    return completeness_receipts


def check_slo_compliance(
    ledger_query_fn: Callable,
    tenant_id: str,
) -> dict:
    """Check if completeness SLO is being met.

    SLO: L0-L4 coverage ≥99.9%

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier

    Returns:
        Dict with compliance status
    """
    completeness = measure_completeness(ledger_query_fn, tenant_id)

    overall = completeness.get("overall_coverage", 0)
    compliant = overall >= COMPLETENESS_TARGET

    return {
        "compliant": compliant,
        "target": COMPLETENESS_TARGET,
        "actual": overall,
        "gap": max(0, COMPLETENESS_TARGET - overall),
        "levels_below_target": [
            level
            for level, data in completeness.get("levels", {}).items()
            if data.get("coverage", 0) < COMPLETENESS_TARGET
        ],
    }


def clear_feedback_events() -> None:
    """Clear L4 feedback events (for testing)."""
    global _l4_feedback_events
    _l4_feedback_events = []
