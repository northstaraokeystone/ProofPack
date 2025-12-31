"""Analyze Module - Pattern detection on sensed receipts.

Run HUNTER logic to detect anomalies, patterns, and drift signals.
Detection taxonomy from QED v7:
- drift: Gradual change from baseline
- degradation: Performance declining over time
- constraint_violation: SLO or policy breach
- pattern_deviation: Expected pattern not matching
- emergent_anti_pattern: New problematic behavior
"""

from collections import Counter

from proofpack.core.receipt import emit_receipt

from .entropy import system_entropy


def analyze(sensed: dict, tenant_id: str) -> dict:
    """Run pattern detection on sensed receipts.

    Args:
        sensed: Output from sense() with L0-L3 categorized receipts
        tenant_id: Tenant identifier

    Returns:
        Dict with:
            - anomalies: List of detected anomalies
            - patterns: List of recurring patterns
            - drift_signals: List of drift detections
            - entropy_before: Entropy at start
            - entropy_after: Entropy at end
    """
    all_receipts = sensed.get("all_receipts", [])

    # Calculate entropy before analysis
    entropy_before = system_entropy(all_receipts)

    # Run HUNTER pattern detection
    anomalies = run_hunter(all_receipts)
    patterns = detect_patterns(all_receipts)
    drift_signals = detect_drift_from_receipts(all_receipts)

    # Calculate entropy after (same for now, changes if we filter)
    entropy_after = system_entropy(all_receipts)

    result = {
        "anomalies": anomalies,
        "patterns": patterns,
        "drift_signals": drift_signals,
        "entropy_before": entropy_before,
        "entropy_after": entropy_after,
    }

    # Emit analysis receipt (L1)
    emit_receipt(
        "analysis",
        {
            "tenant_id": tenant_id,
            "anomalies": [
                {
                    "type": a["type"],
                    "severity": a.get("severity", "medium"),
                    "receipt_ids": a.get("receipt_ids", []),
                }
                for a in anomalies
            ],
            "patterns": [
                {
                    "type": p["type"],
                    "count": p["count"],
                    "confidence": p.get("confidence", 0.0),
                }
                for p in patterns
            ],
            "drift_signals": drift_signals,
            "entropy_before": entropy_before,
            "entropy_after": entropy_after,
        },
    )

    return result


def run_hunter(receipts: list) -> list:
    """HUNTER agent logic - scan for various anomaly types.

    Detects:
    - drift: Gradual change from baseline
    - degradation: Performance declining over time
    - constraint_violation: SLO or policy breach
    - pattern_deviation: Expected pattern not matching
    - emergent_anti_pattern: New problematic behavior

    Args:
        receipts: List of receipt dicts

    Returns:
        List of anomaly dicts with type, severity, receipt_ids
    """
    anomalies = []

    # Detect constraint violations (anomaly receipts already flagged)
    violations = [
        r for r in receipts if r.get("receipt_type") == "anomaly"
    ]
    if violations:
        anomalies.append({
            "type": "constraint_violation",
            "severity": "high",
            "receipt_ids": [r.get("payload_hash", "") for r in violations],
            "count": len(violations),
        })

    # Detect degradation (multiple failures in sequence)
    failures = [
        r
        for r in receipts
        if r.get("status") in ("failed", "error")
        or r.get("classification") == "violation"
    ]
    if len(failures) >= 3:
        anomalies.append({
            "type": "degradation",
            "severity": "medium",
            "receipt_ids": [r.get("payload_hash", "") for r in failures[:10]],
            "count": len(failures),
        })

    # Detect emergent anti-patterns (unusual type distributions)
    type_counts = Counter(r.get("receipt_type", "unknown") for r in receipts)
    total = len(receipts) if receipts else 1
    for rtype, count in type_counts.items():
        ratio = count / total
        # Anti-pattern: single type dominates (>80%)
        if ratio > 0.8 and count > 5:
            anomalies.append({
                "type": "emergent_anti_pattern",
                "severity": "low",
                "receipt_ids": [],
                "pattern": f"{rtype} dominates ({ratio:.1%})",
            })

    return anomalies


def detect_patterns(receipts: list, min_occurrences: int = 3) -> list:
    """Group receipts by type+outcome and find recurring patterns.

    Args:
        receipts: List of receipt dicts
        min_occurrences: Minimum occurrences to qualify as pattern

    Returns:
        List of pattern dicts with type, count, confidence
    """
    patterns = []

    # Group by receipt_type
    type_counts = Counter(r.get("receipt_type", "unknown") for r in receipts)

    for rtype, count in type_counts.items():
        if count >= min_occurrences:
            # Calculate confidence based on consistency
            type_receipts = [
                r for r in receipts if r.get("receipt_type") == rtype
            ]
            confidence = _calculate_pattern_confidence(type_receipts)

            patterns.append({
                "type": rtype,
                "count": count,
                "confidence": confidence,
            })

    # Sort by count descending
    patterns.sort(key=lambda p: p["count"], reverse=True)

    return patterns


def _calculate_pattern_confidence(receipts: list) -> float:
    """Calculate confidence score for a pattern.

    Higher confidence if receipts have consistent structure.

    Args:
        receipts: List of receipts of the same type

    Returns:
        Confidence score 0-1
    """
    if not receipts:
        return 0.0

    # Check field consistency
    all_fields = [set(r.keys()) for r in receipts]
    if not all_fields:
        return 0.0

    # Confidence based on field overlap
    common_fields = set.intersection(*all_fields)
    all_possible = set.union(*all_fields)

    if not all_possible:
        return 0.0

    return len(common_fields) / len(all_possible)


def detect_drift(receipts: list, baseline: dict) -> dict:
    """Compare current distribution to baseline.

    Args:
        receipts: List of current receipts
        baseline: Dict mapping metric names to baseline values

    Returns:
        Dict with drift_score (0-1) and direction (up/down/stable)
    """
    if not receipts or not baseline:
        return {"drift_score": 0.0, "direction": "stable", "metrics": []}

    metrics = []
    total_drift = 0.0

    # Check each baseline metric
    for metric_name, baseline_value in baseline.items():
        current_values = [
            r.get(metric_name)
            for r in receipts
            if r.get(metric_name) is not None
        ]

        if current_values and baseline_value:
            current_avg = sum(current_values) / len(current_values)
            try:
                drift_ratio = abs(current_avg - baseline_value) / baseline_value
            except (ZeroDivisionError, TypeError):
                drift_ratio = 0.0

            direction = "stable"
            if current_avg > baseline_value * 1.1:
                direction = "up"
            elif current_avg < baseline_value * 0.9:
                direction = "down"

            metrics.append({
                "metric": metric_name,
                "baseline": baseline_value,
                "current": current_avg,
                "drift_ratio": drift_ratio,
                "direction": direction,
            })
            total_drift += drift_ratio

    # Overall drift score (capped at 1.0)
    drift_score = min(total_drift / max(len(metrics), 1), 1.0)

    # Overall direction based on majority
    directions = [m["direction"] for m in metrics]
    if directions:
        direction = max(set(directions), key=directions.count)
    else:
        direction = "stable"

    return {
        "drift_score": drift_score,
        "direction": direction,
        "metrics": metrics,
    }


def detect_drift_from_receipts(receipts: list) -> list:
    """Detect drift signals from receipt stream itself.

    Looks for changes in receipt rates, latencies, error rates.

    Args:
        receipts: List of receipts

    Returns:
        List of drift signal dicts
    """
    drift_signals = []

    if len(receipts) < 2:
        return drift_signals

    # Split receipts into early and late halves
    mid = len(receipts) // 2
    early = receipts[:mid]
    late = receipts[mid:]

    # Check for type distribution drift
    early_types = Counter(r.get("receipt_type") for r in early)
    late_types = Counter(r.get("receipt_type") for r in late)

    all_types = set(early_types.keys()) | set(late_types.keys())
    for rtype in all_types:
        early_ratio = early_types.get(rtype, 0) / max(len(early), 1)
        late_ratio = late_types.get(rtype, 0) / max(len(late), 1)

        if early_ratio > 0:
            change = (late_ratio - early_ratio) / early_ratio
            if abs(change) > 0.5:  # >50% change
                drift_signals.append({
                    "metric": f"type_ratio_{rtype}",
                    "direction": "up" if change > 0 else "down",
                    "magnitude": abs(change),
                })

    # Check for latency drift
    early_latencies = [
        r.get("duration_ms", r.get("latency_ms"))
        for r in early
        if r.get("duration_ms") or r.get("latency_ms")
    ]
    late_latencies = [
        r.get("duration_ms", r.get("latency_ms"))
        for r in late
        if r.get("duration_ms") or r.get("latency_ms")
    ]

    if early_latencies and late_latencies:
        early_avg = sum(early_latencies) / len(early_latencies)
        late_avg = sum(late_latencies) / len(late_latencies)

        if early_avg > 0:
            latency_change = (late_avg - early_avg) / early_avg
            if abs(latency_change) > 0.2:  # >20% change
                drift_signals.append({
                    "metric": "latency",
                    "direction": "up" if latency_change > 0 else "down",
                    "magnitude": abs(latency_change),
                })

    return drift_signals
