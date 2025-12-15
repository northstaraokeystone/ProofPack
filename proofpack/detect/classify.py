"""Anomaly classification from matches.

Functions:
    classify_anomaly: Pure function returning classification string
    classify_with_receipt: Classify and emit classify_receipt
    batch_classify: Classify multiple matches, return list of classifications
"""
from proofpack.core.receipt import emit_receipt


# Valid classification types per CLAUDEME §4.7
CLASSIFICATIONS = {"drift", "degradation", "violation", "deviation", "anti_pattern"}

# Pattern type to classification mapping
PATTERN_TYPE_MAP = {
    "threshold_breach": "violation",
    "trend_change": "drift",
    "performance_drop": "degradation",
    "unexpected_value": "deviation",
    "code_smell": "anti_pattern",
}


def classify_anomaly(match: dict) -> str:
    """Classify anomaly from match dict.

    Pure function - returns classification string only.
    Classification logic based on pattern type and match characteristics.

    Args:
        match: Match dict from scan with pattern_id, etc.

    Returns:
        One of: "drift", "degradation", "violation", "deviation", "anti_pattern"
    """
    # Extract pattern type from match
    pattern_id = match.get("pattern_id", "")

    # Check if pattern_id contains a known pattern type
    for pattern_type, classification in PATTERN_TYPE_MAP.items():
        if pattern_type in pattern_id:
            return classification

    # Check matched_conditions for pattern type hints
    matched_conditions = match.get("matched_conditions", [])
    for condition in matched_conditions:
        field = condition.get("field", "")
        if "threshold" in field.lower():
            return "violation"
        if "trend" in field.lower():
            return "drift"
        if "performance" in field.lower() or "latency" in field.lower():
            return "degradation"

    # Check if match has explicit pattern_type
    pattern_type = match.get("pattern_type", "")
    if pattern_type in PATTERN_TYPE_MAP:
        return PATTERN_TYPE_MAP[pattern_type]

    # Default classification
    return "deviation"


def classify_with_receipt(match: dict, tenant_id: str = "default") -> dict:
    """Classify anomaly and emit classify_receipt.

    Args:
        match: Match dict from scan
        tenant_id: Tenant identifier

    Returns:
        classify_receipt dict
    """
    classification = classify_anomaly(match)

    # Build evidence from match data
    evidence = []
    if "pattern_id" in match:
        evidence.append(f"pattern: {match['pattern_id']}")
    if "matched_conditions" in match:
        for cond in match.get("matched_conditions", []):
            evidence.append(f"{cond.get('field')} {cond.get('operator')} {cond.get('value')}")

    # Use match_id from match or generate from pattern_id and receipt_hash
    match_id = match.get("match_id")
    if not match_id:
        match_id = f"{match.get('pattern_id', 'unknown')}:{match.get('receipt_hash', 'unknown')[:16]}"

    receipt = emit_receipt("classify", {
        "tenant_id": tenant_id,
        "match_id": match_id,
        "classification": classification,
        "confidence": match.get("confidence", 0.5),
        "evidence": evidence,
    })

    return receipt


def batch_classify(matches: list[dict], tenant_id: str = "default") -> list[str]:
    """Classify multiple matches.

    Calls classify_anomaly() for each match. No receipts emitted for batch
    (use classify_with_receipt for individual tracking).

    Args:
        matches: List of match dicts from scan
        tenant_id: Tenant identifier (unused in batch, for API consistency)

    Returns:
        List of classification strings
    """
    return [classify_anomaly(match) for match in matches]
