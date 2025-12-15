"""Effectiveness Module - Measure helper effectiveness.

Track, promote, or retire helpers based on entropy reduction.
Lifecycle rules:
- Positive effectiveness → continue
- Zero effectiveness for 30 days → dormant
- Negative effectiveness → retire (unless protected)
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

from proofpack.core.receipt import emit_receipt

from .entropy import system_entropy, agent_fitness
from .actuate import get_helper, get_active_helpers

# Constants
FITNESS_WEIGHTS = {
    "roi": 0.4,
    "diversity": 0.3,
    "stability": 0.2,
    "recency": 0.1,
}
EFFECTIVENESS_DORMANT_DAYS = 30

# Protected helpers that cannot be retired
PROTECTED_HELPERS = [
    "loop.cycle",
    "loop.gate",
    "loop.completeness",
]

# Effectiveness tracking (in production, this would be in ledger)
_effectiveness_history: dict = {}


def measure_effectiveness(
    helper_id: str,
    ledger_query_fn: Callable,
    tenant_id: str = "default",
    window: str = "24h",
) -> dict:
    """Calculate effectiveness score for a helper.

    Effectiveness = entropy reduction per action.
    Positive = good, negative = bad.

    Args:
        helper_id: Helper identifier
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
        window: Time window ("24h", "7d", "30d")

    Returns:
        Effectiveness measurement dict
    """
    helper = get_helper(helper_id)
    if not helper:
        return {
            "error": f"Helper {helper_id} not found",
            "effectiveness_score": 0.0,
        }

    # Parse window
    window_ms = _parse_window(window)
    now = datetime.now(timezone.utc)
    since = (now - timedelta(milliseconds=window_ms)).isoformat().replace("+00:00", "Z")

    # Query receipts
    all_receipts = ledger_query_fn(tenant_id=tenant_id, since=since)

    # Get helper's actuation receipts
    helper_actions = [
        r
        for r in all_receipts
        if r.get("receipt_type") == "actuation"
        and r.get("blueprint_id") == helper_id
    ]

    # Calculate entropy before/after helper actions
    # (simplified: compare receipts before first action to after last action)
    actions_taken = len(helper_actions)
    actions_successful = sum(1 for a in helper_actions if a.get("status") == "success")

    # Calculate entropy reduction
    if actions_taken > 0:
        # Split receipts into before and after first action
        first_action_ts = min(a.get("ts", "") for a in helper_actions)
        receipts_before = [r for r in all_receipts if r.get("ts", "") < first_action_ts]
        receipts_after = [r for r in all_receipts if r.get("ts", "") >= first_action_ts]

        h_before = system_entropy(receipts_before)
        h_after = system_entropy(receipts_after)
        entropy_reduction = h_before - h_after

        # Per-action effectiveness
        effectiveness_score = entropy_reduction / actions_taken
    else:
        entropy_reduction = 0.0
        effectiveness_score = 0.0

    # Calculate multi-dimensional fitness
    fitness = calculate_multi_dimensional_fitness(helper_id, {
        "actions_taken": actions_taken,
        "actions_successful": actions_successful,
        "entropy_reduction": entropy_reduction,
        "window": window,
    })

    # Determine trend
    trend = _calculate_trend(helper_id, effectiveness_score)

    # Determine status
    status = _determine_status(helper_id, effectiveness_score, tenant_id)

    # Store in history
    _record_effectiveness(helper_id, effectiveness_score, fitness)

    result = {
        "helper_id": helper_id,
        "measurement_window": window,
        "actions_taken": actions_taken,
        "actions_successful": actions_successful,
        "effectiveness_score": round(effectiveness_score, 4),
        "entropy_reduction": round(entropy_reduction, 4),
        "fitness": fitness,
        "trend": trend,
        "status": status,
    }

    # Emit effectiveness receipt (L3)
    emit_receipt(
        "effectiveness",
        {
            "tenant_id": tenant_id,
            "helper_id": helper_id,
            "measurement_window": window,
            "actions_taken": actions_taken,
            "actions_successful": actions_successful,
            "effectiveness_score": result["effectiveness_score"],
            "entropy_reduction": result["entropy_reduction"],
            "fitness": fitness,
            "trend": trend,
            "status": status,
        },
    )

    return result


def track_helper(
    helper_id: str,
    ledger_query_fn: Callable,
    tenant_id: str = "default",
) -> dict:
    """Track helper status over time.

    Args:
        helper_id: Helper identifier
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier

    Returns:
        Status dict with trend information
    """
    helper = get_helper(helper_id)
    if not helper:
        return {
            "helper_id": helper_id,
            "status": "not_found",
            "trend": "unknown",
        }

    # Get recent effectiveness measurements
    history = _effectiveness_history.get(helper_id, [])

    if len(history) < 2:
        trend = "insufficient_data"
    else:
        recent = history[-5:]  # Last 5 measurements
        scores = [h["effectiveness_score"] for h in recent]

        # Calculate trend
        if all(s >= scores[0] for s in scores[1:]):
            trend = "improving"
        elif all(s <= scores[0] for s in scores[1:]):
            trend = "degrading"
        else:
            trend = "stable"

    return {
        "helper_id": helper_id,
        "status": helper.get("status", "unknown"),
        "trend": trend,
        "measurements": len(history),
        "last_score": history[-1]["effectiveness_score"] if history else None,
    }


def retire_helper(
    helper_id: str,
    reason: str,
    tenant_id: str = "default",
) -> dict:
    """Retire a helper (mark as retired, don't delete).

    Args:
        helper_id: Helper identifier
        reason: Reason for retirement
        tenant_id: Tenant identifier

    Returns:
        Retirement result dict
    """
    helper = get_helper(helper_id)
    if not helper:
        return {
            "status": "failed",
            "reason": f"Helper {helper_id} not found",
        }

    # Check if protected
    name = helper.get("name", "")
    if any(p in name for p in PROTECTED_HELPERS):
        return {
            "status": "failed",
            "reason": f"Helper {helper_id} is protected and cannot be retired",
        }

    # Mark as retired
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    helper["status"] = "retired"
    helper["retired_at"] = now
    helper["retirement_reason"] = reason

    # Emit effectiveness receipt with retired status
    emit_receipt(
        "effectiveness",
        {
            "tenant_id": tenant_id,
            "helper_id": helper_id,
            "measurement_window": "final",
            "actions_taken": helper.get("actions_taken", 0),
            "actions_successful": helper.get("actions_successful", 0),
            "effectiveness_score": 0.0,
            "entropy_reduction": 0.0,
            "fitness": {"combined": 0.0},
            "trend": "retired",
            "status": "retired",
        },
    )

    return {
        "status": "success",
        "helper_id": helper_id,
        "retired_at": now,
        "reason": reason,
    }


def calculate_multi_dimensional_fitness(
    helper_id: str,
    metrics: dict,
) -> dict:
    """Calculate weighted fitness score.

    Prevents single-metric optimization death spiral.
    Weights: ROI 0.4, diversity 0.3, stability 0.2, recency 0.1

    Args:
        helper_id: Helper identifier
        metrics: Dict with actions_taken, actions_successful, entropy_reduction

    Returns:
        Fitness dict with individual scores and combined
    """
    # ROI: successful actions / total actions
    actions_taken = metrics.get("actions_taken", 0)
    actions_successful = metrics.get("actions_successful", 0)
    if actions_taken > 0:
        roi = actions_successful / actions_taken
    else:
        roi = 0.5  # Neutral if no actions

    # Diversity: variety of action types (simplified)
    # Higher diversity = more flexible helper
    diversity = 0.5  # Default neutral, would analyze action types in full impl

    # Stability: consistency of effectiveness over time
    history = _effectiveness_history.get(helper_id, [])
    if len(history) >= 3:
        recent_scores = [h["effectiveness_score"] for h in history[-5:]]
        if recent_scores:
            avg = sum(recent_scores) / len(recent_scores)
            variance = sum((s - avg) ** 2 for s in recent_scores) / len(recent_scores)
            # Lower variance = higher stability
            stability = max(0, 1 - (variance * 10))  # Scale variance
        else:
            stability = 0.5
    else:
        stability = 0.5  # Neutral with insufficient data

    # Recency: more recent activity = higher score
    helper = get_helper(helper_id)
    if helper:
        deployed_at = helper.get("deployed_at", "")
        if deployed_at:
            try:
                deployed_dt = datetime.fromisoformat(deployed_at.replace("Z", "+00:00"))
                days_active = (datetime.now(timezone.utc) - deployed_dt).days
                # Newer helpers get higher recency, caps at 30 days
                recency = max(0, 1 - (days_active / 30))
            except ValueError:
                recency = 0.5
        else:
            recency = 0.5
    else:
        recency = 0.5

    # Combined weighted score
    combined = (
        FITNESS_WEIGHTS["roi"] * roi
        + FITNESS_WEIGHTS["diversity"] * diversity
        + FITNESS_WEIGHTS["stability"] * stability
        + FITNESS_WEIGHTS["recency"] * recency
    )

    return {
        "roi": round(roi, 3),
        "diversity": round(diversity, 3),
        "stability": round(stability, 3),
        "recency": round(recency, 3),
        "combined": round(combined, 3),
    }


def _parse_window(window: str) -> int:
    """Parse window string to milliseconds.

    Args:
        window: Window string ("24h", "7d", "30d")

    Returns:
        Window in milliseconds
    """
    if window.endswith("h"):
        hours = int(window[:-1])
        return hours * 3600 * 1000
    elif window.endswith("d"):
        days = int(window[:-1])
        return days * 24 * 3600 * 1000
    else:
        return 24 * 3600 * 1000  # Default 24h


def _calculate_trend(helper_id: str, current_score: float) -> str:
    """Calculate trend based on historical scores.

    Args:
        helper_id: Helper identifier
        current_score: Current effectiveness score

    Returns:
        "improving", "stable", or "degrading"
    """
    history = _effectiveness_history.get(helper_id, [])

    if len(history) < 2:
        return "stable"

    # Compare to recent average
    recent = history[-5:]
    avg_score = sum(h["effectiveness_score"] for h in recent) / len(recent)

    if current_score > avg_score * 1.1:
        return "improving"
    elif current_score < avg_score * 0.9:
        return "degrading"
    else:
        return "stable"


def _determine_status(
    helper_id: str,
    effectiveness_score: float,
    tenant_id: str,
) -> str:
    """Determine helper status based on effectiveness.

    Args:
        helper_id: Helper identifier
        effectiveness_score: Current effectiveness score
        tenant_id: Tenant identifier

    Returns:
        "active", "dormant", or "retired"
    """
    helper = get_helper(helper_id)
    if not helper:
        return "not_found"

    current_status = helper.get("status", "deployed")
    if current_status in ("retired", "rolled_back"):
        return current_status

    # Check for negative effectiveness
    if effectiveness_score < -0.1:
        # Candidate for retirement
        return "degrading"

    # Check for dormancy (zero effectiveness for EFFECTIVENESS_DORMANT_DAYS)
    history = _effectiveness_history.get(helper_id, [])
    if len(history) >= EFFECTIVENESS_DORMANT_DAYS:
        recent = history[-EFFECTIVENESS_DORMANT_DAYS:]
        all_zero = all(abs(h["effectiveness_score"]) < 0.001 for h in recent)
        if all_zero:
            return "dormant"

    return "active"


def _record_effectiveness(
    helper_id: str,
    effectiveness_score: float,
    fitness: dict,
) -> None:
    """Record effectiveness measurement in history.

    Args:
        helper_id: Helper identifier
        effectiveness_score: Calculated score
        fitness: Fitness metrics dict
    """
    if helper_id not in _effectiveness_history:
        _effectiveness_history[helper_id] = []

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _effectiveness_history[helper_id].append({
        "ts": now,
        "effectiveness_score": effectiveness_score,
        "fitness": fitness,
    })

    # Keep only last 100 measurements
    if len(_effectiveness_history[helper_id]) > 100:
        _effectiveness_history[helper_id] = _effectiveness_history[helper_id][-100:]


def clear_effectiveness_history() -> None:
    """Clear effectiveness history (for testing)."""
    global _effectiveness_history
    _effectiveness_history = {}
