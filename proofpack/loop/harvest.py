"""Harvest Module - Collect wounds and identify automation candidates.

"What bleeds, breeds." - Every manual intervention is the system saying
"I couldn't handle this." Harvest those wounds, rank by automation potential.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Callable

from proofpack.core.receipt import emit_receipt

# Import constants (avoid circular import by defining locally)
WOUND_THRESHOLD_COUNT = 5
WOUND_THRESHOLD_RESOLVE_MS = 1800000  # 30min
HARVEST_WINDOW_DAYS = 30


def harvest_wounds(
    ledger_query_fn: Callable,
    tenant_id: str,
    days: int = HARVEST_WINDOW_DAYS,
) -> list:
    """Query wound/gap receipts and identify automation candidates.

    Filters by threshold:
    - ≥5 occurrences
    - median resolve time >30min

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
        days: Number of days to look back (default 30)

    Returns:
        List of wound pattern dicts ranked by automation potential
    """
    # Calculate time window
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    # Query wound and gap receipts
    all_receipts = ledger_query_fn(tenant_id=tenant_id, since=since)
    wound_receipts = [
        r
        for r in all_receipts
        if r.get("receipt_type") in ("wound", "gap", "manual_intervention")
    ]

    # Group by problem type
    grouped = group_by_type(wound_receipts)

    # Filter by thresholds and calculate scores
    candidates = []
    for problem_type, wounds in grouped.items():
        if len(wounds) < WOUND_THRESHOLD_COUNT:
            continue

        resolve_times = [
            w.get("time_to_resolve_ms", 0) for w in wounds if w.get("time_to_resolve_ms")
        ]

        if not resolve_times:
            continue

        median_resolve = median(resolve_times)
        if median_resolve < WOUND_THRESHOLD_RESOLVE_MS:
            continue

        # Calculate automation score
        automation_score = calculate_automation_score(wounds)

        candidates.append({
            "problem_type": problem_type,
            "count": len(wounds),
            "median_resolve_ms": int(median_resolve),
            "automation_score": automation_score,
            "wound_receipt_ids": [
                w.get("payload_hash", "") for w in wounds[:20]  # Cap at 20
            ],
        })

    # Rank by score (frequency × resolve_time weighted)
    ranked = rank_patterns(candidates)

    # Emit harvest receipt (L3)
    emit_receipt(
        "harvest",
        {
            "tenant_id": tenant_id,
            "window_days": days,
            "wounds_total": len(wound_receipts),
            "wounds_qualified": len(candidates),
            "candidates": [
                {
                    "problem_type": c["problem_type"],
                    "count": c["count"],
                    "median_resolve_ms": c["median_resolve_ms"],
                    "automation_score": c["automation_score"],
                }
                for c in ranked
            ],
        },
    )

    return ranked


def rank_patterns(wounds: list) -> list:
    """Sort wounds by frequency × resolution_time.

    Higher score = more valuable to automate.

    Args:
        wounds: List of wound pattern dicts with count and median_resolve_ms

    Returns:
        Sorted list (highest score first)
    """
    def score(w):
        count = w.get("count", 0)
        resolve_ms = w.get("median_resolve_ms", 0)
        # Normalize: count weight + time weight (in hours)
        return count * (resolve_ms / 3600000)  # Convert ms to hours

    return sorted(wounds, key=score, reverse=True)


def group_by_type(wounds: list) -> dict:
    """Group wounds by problem_type.

    Args:
        wounds: List of wound receipt dicts

    Returns:
        Dict mapping problem_type to list of wounds
    """
    grouped = defaultdict(list)
    for wound in wounds:
        problem_type = wound.get("problem_type", "unknown")
        grouped[problem_type].append(wound)
    return dict(grouped)


def calculate_automation_score(wound_group: list) -> float:
    """Calculate automation potential score (0-1).

    Higher score = more automatable.
    Factors:
    - Consistency of resolution (same steps = higher)
    - Time saved potential (longer resolve = higher)
    - Risk (could_automate confidence)

    Args:
        wound_group: List of wounds of the same problem_type

    Returns:
        Score 0-1, higher = more automatable
    """
    if not wound_group:
        return 0.0

    # Factor 1: Resolution consistency (0-0.4)
    consistency_score = _resolution_consistency(wound_group) * 0.4

    # Factor 2: Time saved potential (0-0.3)
    resolve_times = [
        w.get("time_to_resolve_ms", 0) for w in wound_group if w.get("time_to_resolve_ms")
    ]
    if resolve_times:
        avg_resolve_hours = sum(resolve_times) / len(resolve_times) / 3600000
        # Cap at 4 hours = max score
        time_score = min(avg_resolve_hours / 4.0, 1.0) * 0.3
    else:
        time_score = 0.0

    # Factor 3: Explicit automation confidence (0-0.3)
    confidence_values = [
        w.get("automation_confidence", 0.5)
        for w in wound_group
        if "automation_confidence" in w
    ]
    if confidence_values:
        confidence_score = sum(confidence_values) / len(confidence_values) * 0.3
    else:
        # Default to 0.5 if not specified
        confidence_score = 0.15

    return consistency_score + time_score + confidence_score


def _resolution_consistency(wounds: list) -> float:
    """Calculate how consistent the resolution steps are.

    Args:
        wounds: List of wound receipts

    Returns:
        Consistency score 0-1
    """
    # Get all resolution actions
    actions = [w.get("resolution_action", "") for w in wounds if w.get("resolution_action")]

    if not actions:
        return 0.5  # Unknown consistency

    # Check how many unique actions
    unique_actions = set(actions)
    if len(unique_actions) == 1:
        return 1.0  # Perfectly consistent
    elif len(unique_actions) <= 3:
        return 0.7  # Mostly consistent
    else:
        return 0.3  # Varied resolutions


def emit_wound_receipt(
    tenant_id: str,
    problem_type: str,
    time_to_resolve_ms: int,
    resolution_action: str,
    resolution_steps: list = None,
    could_automate: bool = False,
    automation_confidence: float = 0.5,
) -> dict:
    """Emit a wound receipt for manual intervention.

    Args:
        tenant_id: Tenant identifier
        problem_type: Type of problem that required manual intervention
        time_to_resolve_ms: Time taken to resolve (milliseconds)
        resolution_action: What action resolved the problem
        resolution_steps: Optional list of steps taken
        could_automate: Whether this could be automated
        automation_confidence: Confidence in automation potential (0-1)

    Returns:
        Emitted receipt
    """
    return emit_receipt(
        "wound",
        {
            "tenant_id": tenant_id,
            "problem_type": problem_type,
            "time_to_resolve_ms": time_to_resolve_ms,
            "resolution_steps": resolution_steps or [],
            "resolution_action": resolution_action,
            "could_automate": could_automate,
            "automation_confidence": automation_confidence,
        },
    )
