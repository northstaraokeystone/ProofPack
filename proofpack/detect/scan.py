"""Pattern matching on receipt streams.

Functions:
    scan: Iterate receipts applying patterns, emit scan_receipt
    match_pattern: Pure function matching single receipt against pattern
    build_pattern: Factory for creating valid pattern dicts
"""
import re
import time

from proofpack.core.receipt import emit_receipt, dual_hash, StopRule


# Valid operators for pattern conditions
VALID_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "contains", "regex"}


def scan(receipts: list[dict], patterns: list[dict], tenant_id: str = "default") -> list[dict]:
    """Scan receipts against patterns and return matches.

    Iterates through receipts applying each pattern, collects all matches
    with scores, and emits scan_receipt with match summary.

    Args:
        receipts: List of receipt dicts to scan
        patterns: List of pattern dicts to match against
        tenant_id: Tenant identifier

    Returns:
        List of match dicts

    Raises:
        StopRule: If scan latency exceeds 200ms
    """
    start_time = time.time()
    matches = []

    for receipt in receipts:
        for pattern in patterns:
            match = match_pattern(receipt, pattern)
            if match is not None:
                matches.append(match)

    elapsed_ms = int((time.time() - start_time) * 1000)

    # SLO check: latency > 200ms triggers StopRule
    if elapsed_ms > 200:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "scan_latency",
            "baseline": 100.0,
            "delta": float(elapsed_ms - 100),
            "classification": "violation",
            "action": "alert",
        })
        raise StopRule(f"Scan latency {elapsed_ms}ms exceeds 200ms threshold")

    # Emit scan receipt
    emit_receipt("scan", {
        "tenant_id": tenant_id,
        "receipts_scanned": len(receipts),
        "patterns_checked": len(patterns),
        "matches_found": len(matches),
        "matches": matches,
        "elapsed_ms": elapsed_ms,
    })

    return matches


def match_pattern(receipt: dict, pattern: dict) -> dict | None:
    """Match single receipt against pattern.

    Pure function. Pattern has fields: id, type, conditions (list of condition dicts).
    Condition has: field, operator, value.

    Args:
        receipt: Receipt dict to check
        pattern: Pattern dict with id, type, conditions

    Returns:
        Match dict if all conditions pass, None otherwise.
        Match dict contains: pattern_id, receipt_hash, score, confidence, matched_conditions
    """
    conditions = pattern.get("conditions", [])
    if not conditions:
        return None

    matched_conditions = []

    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        expected_value = condition.get("value")

        if field is None or operator is None:
            return None

        actual_value = receipt.get(field)

        if not _evaluate_condition(actual_value, operator, expected_value):
            return None

        matched_conditions.append(condition)

    # All conditions passed - compute receipt hash for match
    import json
    receipt_hash = dual_hash(json.dumps(receipt, sort_keys=True).encode("utf-8"))

    # Score based on number of conditions matched
    score = len(matched_conditions) / max(len(conditions), 1)
    confidence = min(1.0, 0.5 + (score * 0.5))

    return {
        "pattern_id": pattern.get("id", "unknown"),
        "receipt_hash": receipt_hash,
        "score": score,
        "confidence": confidence,
        "matched_conditions": matched_conditions,
    }


def _evaluate_condition(actual, operator: str, expected) -> bool:
    """Evaluate a single condition.

    Args:
        actual: Actual value from receipt
        operator: Comparison operator
        expected: Expected value from condition

    Returns:
        True if condition passes
    """
    if actual is None:
        return False

    if operator == "eq":
        return actual == expected
    elif operator == "ne":
        return actual != expected
    elif operator == "gt":
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "lt":
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "gte":
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "lte":
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "contains":
        try:
            return expected in str(actual)
        except TypeError:
            return False
    elif operator == "regex":
        try:
            return re.search(expected, str(actual)) is not None
        except (TypeError, re.error):
            return False

    return False


def build_pattern(pattern_id: str, pattern_type: str, conditions: list[dict]) -> dict:
    """Factory for creating valid pattern dicts.

    Args:
        pattern_id: Unique identifier for the pattern
        pattern_type: Type of pattern (threshold_breach, trend_change, etc.)
        conditions: List of condition dicts with field, operator, value

    Returns:
        Valid pattern dict

    Raises:
        ValueError: If any condition has invalid operator
    """
    for condition in conditions:
        operator = condition.get("operator")
        if operator not in VALID_OPERATORS:
            raise ValueError(f"Invalid operator: {operator}. Valid: {VALID_OPERATORS}")

    return {
        "id": pattern_id,
        "type": pattern_type,
        "conditions": conditions,
    }
