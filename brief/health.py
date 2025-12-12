"""Decision health scoring using Decision Health V2 formula."""
import time
from ledger.core import emit_receipt, StopRule

HEALTH_SCHEMA = {
    "receipt_type": "health",
    "strength": "float 0-1",
    "coverage": "float 0-1",
    "efficiency": "float 0-1",
    "thresholds": {"min_strength": "float", "min_coverage": "float", "min_efficiency": "float"},
    "policy_diffs": ["str"],
    "reason": "str"
}

DEFAULT_THRESHOLDS = {"min_strength": 0.8, "min_coverage": 0.85, "min_efficiency": 0.7}
LAMBDA_DECAY = 0.10  # Time decay factor for evidence age


def _compute_strength(evidence: list) -> float:
    """Compute confidence-weighted score of supporting evidence."""
    if not evidence:
        return 0.0
    total = sum(e.get("confidence", 0.5) for e in evidence)
    return round(min(total / len(evidence), 1.0), 3)


def _compute_coverage(brief: dict) -> float:
    """Compute proportion of query aspects addressed."""
    evidence_count = brief.get("evidence_count", 0)
    # v1 heuristic: coverage scales with evidence count, max at 10
    return round(min(evidence_count / 10, 1.0), 3)


def _compute_efficiency(brief: dict, ms_elapsed: int) -> float:
    """Compute tokens used vs value delivered ratio."""
    evidence_count = brief.get("evidence_count", 1)
    # v1 heuristic: efficiency = evidence per 100ms, capped at 1.0
    if ms_elapsed <= 0:
        return 1.0
    return round(min(evidence_count / (ms_elapsed / 100), 1.0), 3)


def score_health(brief: dict, thresholds: dict = None, tenant_id: str = "default") -> dict:
    """Grade evidence quality using Decision Health V2."""
    t0 = time.time()
    thresholds = thresholds or DEFAULT_THRESHOLDS

    evidence = brief.get("supporting_evidence", [])
    strength = _compute_strength(evidence)
    coverage = _compute_coverage(brief)
    ms_elapsed = int((time.time() - t0) * 1000) + 1  # Avoid division by zero
    efficiency = _compute_efficiency(brief, ms_elapsed)

    # Check policy violations
    policy_diffs = []
    if strength < thresholds["min_strength"]:
        policy_diffs.append(f"strength {strength} < {thresholds['min_strength']}")
    if coverage < thresholds["min_coverage"]:
        policy_diffs.append(f"coverage {coverage} < {thresholds['min_coverage']}")
    if efficiency < thresholds["min_efficiency"]:
        policy_diffs.append(f"efficiency {efficiency} < {thresholds['min_efficiency']}")

    reason = "PASS: all thresholds met" if not policy_diffs else f"FAIL: {'; '.join(policy_diffs)}"

    # Stoprule: weak strength
    if strength < thresholds["min_strength"]:
        emit_receipt("anomaly", {
            "metric": "strength",
            "baseline": thresholds["min_strength"],
            "delta": strength - thresholds["min_strength"],
            "classification": "violation",
            "action": "escalate"
        }, tenant_id)
        raise StopRule(f"Weak: {strength} < {thresholds['min_strength']}")

    return emit_receipt("health", {
        "strength": strength,
        "coverage": coverage,
        "efficiency": efficiency,
        "thresholds": thresholds,
        "policy_diffs": policy_diffs,
        "reason": reason
    }, tenant_id)
