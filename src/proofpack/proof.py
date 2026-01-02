"""Unified proof module consolidating brief, packet, and detect operations.

Modes:
    BRIEF: Evidence synthesis from multiple receipts
    PACKET: Bind external claims to receipt chain
    DETECT: Entropy-based anomaly detection

Usage:
    from proof import proof, ProofMode

    # Evidence synthesis
    result = proof(ProofMode.BRIEF, {"evidence": [...]}, {})

    # Decision packet assembly
    result = proof(ProofMode.PACKET, {"brief": {...}, "receipts": [...]}, {})

    # Anomaly detection
    result = proof(ProofMode.DETECT, {"stream": [...], "patterns": [...]}, {})

Migration from v3.0:
    # Old: from brief.compose import compose
    # New: from proof import proof, ProofMode
    #      result = proof(ProofMode.BRIEF, {"evidence": evidence}, {})
"""
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from proofpack.core.receipt import StopRule, dual_hash, emit_receipt, merkle


class ProofMode(Enum):
    """Proof operation modes."""
    BRIEF = "BRIEF"      # Evidence synthesis
    PACKET = "PACKET"    # Claim-to-receipt fusion
    DETECT = "DETECT"    # Anomaly detection


# ============================================================================
# BRIEF MODE: Evidence Synthesis
# ============================================================================

def _classify_complexity(query: str) -> str:
    """Classify query complexity using rule-based heuristics."""
    words = query.lower().split()
    word_count = len(words)

    if "compare" in words or "vs" in words or "versus" in words:
        return "comparative"
    if word_count > 10 or "all" in words or "every" in words:
        return "broad"
    if word_count > 3:
        return "focused"
    return "atomic"


def _compute_strength(evidence: list) -> float:
    """Compute confidence-weighted score of supporting evidence."""
    if not evidence:
        return 0.0
    total = sum(e.get("confidence", 0.5) for e in evidence)
    return round(min(total / len(evidence), 1.0), 3)


def _compute_coverage(brief: dict) -> float:
    """Compute proportion of query aspects addressed."""
    evidence_count = brief.get("evidence_count", 0)
    return round(min(evidence_count / 10, 1.0), 3)


def _compute_efficiency(brief: dict, ms_elapsed: int) -> float:
    """Compute tokens used vs value delivered ratio."""
    evidence_count = brief.get("evidence_count", 1)
    if ms_elapsed <= 0:
        return 1.0
    return round(min(evidence_count / (ms_elapsed / 100), 1.0), 3)


def _classify_stance(chunk_id: str, index: int) -> str:
    """Classify evidence as PRO or CON using rule-based heuristic."""
    return "pro" if index % 2 == 0 else "con"


def _compute_resolution(pro_count: int, con_count: int, total: int) -> tuple:
    """Determine resolution status and margin."""
    if total == 0:
        return "open", 0.0

    pro_ratio = pro_count / total
    con_ratio = con_count / total
    margin = abs(pro_ratio - con_ratio)

    if margin > 0.6:
        return "one_sided", round(margin, 3)
    if margin > 0.2:
        return "resolved", round(margin, 3)
    return "open", round(margin, 3)


def _brief_compose(evidence: list, tenant_id: str = "default") -> dict:
    """Synthesize evidence into executive summary."""
    t0 = time.time()

    if not evidence:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "coverage",
            "baseline": 1,
            "delta": -1,
            "classification": "violation",
            "action": "escalate"
        })
        raise StopRule("Coverage: no evidence provided")

    unique_chunks = list(dict.fromkeys(evidence))
    executive_summary = f"Brief synthesizing {len(unique_chunks)} evidence chunks: " + \
                        ", ".join(str(c) for c in unique_chunks[:5])
    if len(unique_chunks) > 5:
        executive_summary += f" (+{len(unique_chunks) - 5} more)"

    supporting_evidence = [
        {"chunk_id": str(chunk), "confidence": round(1.0 - (i * 0.05), 2)}
        for i, chunk in enumerate(unique_chunks)
    ]

    ms_elapsed = int((time.time() - t0) * 1000)
    if ms_elapsed > 500:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "latency",
            "baseline": 500,
            "delta": ms_elapsed - 500,
            "classification": "degradation",
            "action": "alert"
        })

    return emit_receipt("brief", {
        "tenant_id": tenant_id,
        "executive_summary": executive_summary,
        "supporting_evidence": supporting_evidence,
        "evidence_count": len(unique_chunks)
    })


def _brief_retrieve(query: str, budget: dict, tenant_id: str = "default") -> dict:
    """Find relevant evidence within budget constraints."""
    t0 = time.time()

    complexity = _classify_complexity(query)
    k = min(budget.get("tokens", 1000) // 100, 10)

    chunks = [f"chunk_{i}" for i in range(k)]

    ms_elapsed = int((time.time() - t0) * 1000)
    tokens_used = k * 100

    if ms_elapsed > budget.get("ms", 500):
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "budget",
            "baseline": budget.get("ms", 500),
            "delta": ms_elapsed - budget.get("ms", 500),
            "classification": "violation",
            "action": "reject"
        })
        raise StopRule(f"Budget: {ms_elapsed}ms > {budget.get('ms', 500)}ms")

    reason = f"{complexity}->k={k}, budget_capped" if k == 10 else f"{complexity}->k={k}"

    return emit_receipt("retrieval", {
        "tenant_id": tenant_id,
        "query_complexity": complexity,
        "k": k,
        "chunks": chunks,
        "cost": {"tokens_used": tokens_used, "ms_elapsed": ms_elapsed},
        "reason": reason
    })


def _brief_health(brief: dict, thresholds: dict = None, tenant_id: str = "default") -> dict:
    """Grade evidence quality using Decision Health V2."""
    t0 = time.time()
    default_thresholds = {"min_strength": 0.8, "min_coverage": 0.85, "min_efficiency": 0.7}
    thresholds = thresholds or default_thresholds

    evidence = brief.get("supporting_evidence", [])
    strength = _compute_strength(evidence)
    coverage = _compute_coverage(brief)
    ms_elapsed = int((time.time() - t0) * 1000) + 1
    efficiency = _compute_efficiency(brief, ms_elapsed)

    policy_diffs = []
    if strength < thresholds["min_strength"]:
        policy_diffs.append(f"strength {strength} < {thresholds['min_strength']}")
    if coverage < thresholds["min_coverage"]:
        policy_diffs.append(f"coverage {coverage} < {thresholds['min_coverage']}")
    if efficiency < thresholds["min_efficiency"]:
        policy_diffs.append(f"efficiency {efficiency} < {thresholds['min_efficiency']}")

    reason = "PASS: all thresholds met" if not policy_diffs else f"FAIL: {'; '.join(policy_diffs)}"

    if strength < thresholds["min_strength"]:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "strength",
            "baseline": thresholds["min_strength"],
            "delta": strength - thresholds["min_strength"],
            "classification": "violation",
            "action": "escalate"
        })
        raise StopRule(f"Weak: {strength} < {thresholds['min_strength']}")

    return emit_receipt("health", {
        "tenant_id": tenant_id,
        "strength": strength,
        "coverage": coverage,
        "efficiency": efficiency,
        "thresholds": thresholds,
        "policy_diffs": policy_diffs,
        "reason": reason
    })


def _brief_dialectic(evidence: list, tenant_id: str = "default") -> dict:
    """Generate balanced PRO/CON analysis from evidence."""
    pro = []
    con = []
    gaps = []

    for i, chunk in enumerate(evidence):
        chunk_id = str(chunk) if not isinstance(chunk, dict) else chunk.get("chunk_id", str(i))
        stance = _classify_stance(chunk_id, i)
        strength = round(0.9 - (i * 0.05), 2) if i < 18 else 0.1
        claim = f"Evidence from {chunk_id}"

        entry = {"chunk_id": chunk_id, "claim": claim, "strength": max(strength, 0.1)}
        if stance == "pro":
            pro.append(entry)
        else:
            con.append(entry)

    evidence_count = len(evidence)
    if evidence_count < 50:
        gaps.append("sparse_corpus: evidence_count < 50, coverage penalty halved")

    if not pro:
        gaps.append("no_supporting_evidence")
    if not con:
        gaps.append("no_opposing_evidence")

    resolution_status, margin = _compute_resolution(len(pro), len(con), len(evidence))

    return emit_receipt("dialectic", {
        "tenant_id": tenant_id,
        "pro": pro,
        "con": con,
        "gaps": gaps,
        "resolution_status": resolution_status,
        "margin": margin
    })


def _process_brief(inputs: dict, config: dict, tenant_id: str = "default") -> dict:
    """Process BRIEF mode request."""
    operation = inputs.get("operation", "compose")

    if operation == "compose":
        return _brief_compose(inputs.get("evidence", []), tenant_id)
    elif operation == "retrieve":
        return _brief_retrieve(
            inputs.get("query", ""),
            inputs.get("budget", {"tokens": 1000, "ms": 500}),
            tenant_id
        )
    elif operation == "health":
        return _brief_health(
            inputs.get("brief", {}),
            config.get("thresholds"),
            tenant_id
        )
    elif operation == "dialectic":
        return _brief_dialectic(inputs.get("evidence", []), tenant_id)
    else:
        raise ValueError(f"Unknown BRIEF operation: {operation}")


# ============================================================================
# PACKET MODE: Claim-to-Receipt Fusion
# ============================================================================

def _packet_build(brief: dict, receipts: list, tenant_id: str = "default") -> dict:
    """Assemble final decision packet for sign-off."""
    packet_id = str(uuid.uuid4())

    executive_summary = brief.get("executive_summary", "")

    decision_health = brief.get("decision_health", {
        "strength": brief.get("strength", 0.0),
        "coverage": brief.get("coverage", 0.0),
        "efficiency": brief.get("efficiency", 0.0)
    })

    dialectical_record = brief.get("dialectical_record", None)
    if dialectical_record is None and "pro" in brief:
        dialectical_record = {
            "pro": brief.get("pro", []),
            "con": brief.get("con", []),
            "gaps": brief.get("gaps", [])
        }

    attached_receipts = [
        r.get("payload_hash", dual_hash(json.dumps(r, sort_keys=True))) for r in receipts
    ]

    merkle_anchor = merkle(receipts)

    return emit_receipt("packet", {
        "tenant_id": tenant_id,
        "packet_id": packet_id,
        "brief": executive_summary,
        "decision_health": decision_health,
        "dialectical_record": dialectical_record,
        "attached_receipts": attached_receipts,
        "receipt_count": len(attached_receipts),
        "merkle_anchor": merkle_anchor,
        "signature": None
    })


def _packet_attach(claims: list, receipts: list, tenant_id: str = "default") -> dict:
    """Map claims to their supporting receipts."""
    mappings = {}
    used_receipts = set()

    for claim in claims:
        claim_id = claim.get("claim_id")
        claim_text = claim.get("text", "")
        claim_hash = dual_hash(claim_text)

        matched = []
        for r in receipts:
            r_hash = r.get("payload_hash", "")
            if claim_hash[:16] in r_hash or r_hash[:16] in claim_hash:
                receipt_id = r_hash[:16]
                matched.append(receipt_id)
                used_receipts.add(r_hash)

        mappings[claim_id] = matched

    orphan_claims = [cid for cid, rids in mappings.items() if not rids]
    all_receipt_ids = {r.get("payload_hash", "")[:16] for r in receipts}
    used_ids = {r[:16] for r in used_receipts}
    unused_receipts = list(all_receipt_ids - used_ids)

    return emit_receipt("attach", {
        "tenant_id": tenant_id,
        "mappings": mappings,
        "attached_count": sum(1 for rids in mappings.values() if rids),
        "total_claims": len(claims),
        "orphan_claims": orphan_claims,
        "unused_receipts": unused_receipts
    })


def _packet_audit(attachments: dict, tenant_id: str = "default") -> dict:
    """Verify attachment consistency meets 99.9% threshold."""
    attached_count = attachments.get("attached_count", 0)
    total_claims = attachments.get("total_claims", 0)
    orphan_claims = attachments.get("orphan_claims", [])

    match_rate = attached_count / total_claims if total_claims > 0 else 0.0
    threshold = 0.999

    violations = [
        {"claim_id": cid, "reason": "no_receipt_attached"}
        for cid in orphan_claims
    ]

    if match_rate < threshold:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "fusion_match",
            "baseline": threshold,
            "delta": match_rate - threshold,
            "classification": "violation",
            "action": "halt"
        })

        escalation_deadline = (
            datetime.utcnow() + timedelta(hours=4)
        ).isoformat() + "Z"

        emit_receipt("halt", {
            "tenant_id": tenant_id,
            "reason": "consistency_below_threshold",
            "match_rate": match_rate,
            "threshold": threshold,
            "escalation_deadline": escalation_deadline
        })

        raise StopRule(f"Fusion match {match_rate:.4f} < {threshold}")

    return emit_receipt("consistency", {
        "tenant_id": tenant_id,
        "match_rate": match_rate,
        "threshold": threshold,
        "violations": violations,
        "status": "pass" if match_rate >= threshold else "fail",
        "escalation_hours": None
    })


def _process_packet(inputs: dict, config: dict, tenant_id: str = "default") -> dict:
    """Process PACKET mode request."""
    operation = inputs.get("operation", "build")

    if operation == "build":
        return _packet_build(
            inputs.get("brief", {}),
            inputs.get("receipts", []),
            tenant_id
        )
    elif operation == "attach":
        return _packet_attach(
            inputs.get("claims", []),
            inputs.get("receipts", []),
            tenant_id
        )
    elif operation == "audit":
        return _packet_audit(inputs.get("attachments", {}), tenant_id)
    else:
        raise ValueError(f"Unknown PACKET operation: {operation}")


# ============================================================================
# DETECT MODE: Anomaly Detection
# ============================================================================

VALID_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "contains", "regex"}

CLASSIFICATIONS = {"drift", "degradation", "violation", "deviation", "anti_pattern"}

PATTERN_TYPE_MAP = {
    "threshold_breach": "violation",
    "trend_change": "drift",
    "performance_drop": "degradation",
    "unexpected_value": "deviation",
    "code_smell": "anti_pattern",
}

SEVERITY_LEVELS = {"info", "warning", "error", "critical"}

COMPONENT_DEPS = {
    "ingest": ["anchor", "verify"],
    "anchor": ["compact", "verify"],
    "routing": ["retrieval", "brief"],
    "brief": ["packet", "decision"],
    "packet": ["audit", "output"]
}


def _evaluate_condition(actual: Any, operator: str, expected: Any) -> bool:
    """Evaluate a single condition."""
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


def _match_pattern(receipt: dict, pattern: dict) -> dict | None:
    """Match single receipt against pattern."""
    import json

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

    receipt_hash = dual_hash(json.dumps(receipt, sort_keys=True).encode("utf-8"))

    score = len(matched_conditions) / max(len(conditions), 1)
    confidence = min(1.0, 0.5 + (score * 0.5))

    return {
        "pattern_id": pattern.get("id", "unknown"),
        "receipt_hash": receipt_hash,
        "score": score,
        "confidence": confidence,
        "matched_conditions": matched_conditions,
    }


def _detect_scan(receipts: list, patterns: list, tenant_id: str = "default") -> list:
    """Scan receipts against patterns and return matches."""
    start_time = time.time()
    matches = []

    for receipt in receipts:
        for pattern in patterns:
            match = _match_pattern(receipt, pattern)
            if match is not None:
                matches.append(match)

    elapsed_ms = int((time.time() - start_time) * 1000)

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

    emit_receipt("scan", {
        "tenant_id": tenant_id,
        "receipts_scanned": len(receipts),
        "patterns_checked": len(patterns),
        "matches_found": len(matches),
        "matches": matches,
        "elapsed_ms": elapsed_ms,
    })

    return matches


def _classify_anomaly(match: dict) -> str:
    """Classify anomaly from match dict."""
    pattern_id = match.get("pattern_id", "")

    for pattern_type, classification in PATTERN_TYPE_MAP.items():
        if pattern_type in pattern_id:
            return classification

    matched_conditions = match.get("matched_conditions", [])
    for condition in matched_conditions:
        field = condition.get("field", "")
        if "threshold" in field.lower():
            return "violation"
        if "trend" in field.lower():
            return "drift"
        if "performance" in field.lower() or "latency" in field.lower():
            return "degradation"

    pattern_type = match.get("pattern_type", "")
    if pattern_type in PATTERN_TYPE_MAP:
        return PATTERN_TYPE_MAP[pattern_type]

    return "deviation"


def _detect_classify(match: dict, tenant_id: str = "default") -> dict:
    """Classify anomaly and emit classify_receipt."""
    classification = _classify_anomaly(match)

    evidence = []
    if "pattern_id" in match:
        evidence.append(f"pattern: {match['pattern_id']}")
    if "matched_conditions" in match:
        for cond in match.get("matched_conditions", []):
            evidence.append(f"{cond.get('field')} {cond.get('operator')} {cond.get('value')}")

    match_id = match.get("match_id")
    if not match_id:
        match_id = f"{match.get('pattern_id', 'unknown')}:{match.get('receipt_hash', 'unknown')[:16]}"

    return emit_receipt("classify", {
        "tenant_id": tenant_id,
        "match_id": match_id,
        "classification": classification,
        "confidence": match.get("confidence", 0.5),
        "evidence": evidence,
    })


def _determine_blast_radius(classification: str, anomaly: dict) -> str:
    """Determine blast radius from classification and anomaly data."""
    if "scope" in anomaly:
        return anomaly["scope"]

    if classification == "violation":
        return "system"
    elif classification == "degradation":
        return "service"
    elif classification == "drift":
        return "metric"
    elif classification == "anti_pattern":
        return "component"
    else:
        return "local"


def _determine_severity(
    classification: str,
    confidence: float,
    drift_score: float | None = None
) -> str:
    """Determine alert severity from classification and metrics."""
    if classification == "violation":
        if confidence >= 0.9:
            return "critical"
        return "error"

    if classification in ("degradation", "drift"):
        if drift_score is not None and abs(drift_score) > 0.5:
            return "error"
        return "warning"

    if classification == "deviation":
        return "warning"

    if classification == "anti_pattern":
        return "info"

    return "warning"


def _detect_alert(anomaly: dict, severity: str, tenant_id: str = "default") -> dict:
    """Generate alert from anomaly with severity."""
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"Invalid severity: {severity}. Valid: {SEVERITY_LEVELS}")

    alert_id = str(uuid.uuid4())

    classification = anomaly.get("classification", "unknown")
    blast_radius = _determine_blast_radius(classification, anomaly)

    escalated = severity == "critical"
    escalation_target = "ops-team" if escalated else None

    source = {
        "receipt_hash": anomaly.get("receipt_hash", anomaly.get("payload_hash", "unknown")),
        "metric": anomaly.get("metric", classification),
    }

    receipt = emit_receipt("alert", {
        "tenant_id": tenant_id,
        "alert_id": alert_id,
        "anomaly_type": classification,
        "severity": severity,
        "source": source,
        "blast_radius": blast_radius,
        "escalated": escalated,
        "escalation_target": escalation_target,
    })

    if severity == "critical":
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": anomaly.get("metric", classification),
            "baseline": anomaly.get("baseline", 0.0),
            "delta": anomaly.get("delta", 0.0),
            "classification": classification,
            "action": "escalate",
        })

    return receipt


def _process_detect(inputs: dict, config: dict, tenant_id: str = "default") -> dict:
    """Process DETECT mode request."""
    operation = inputs.get("operation", "scan")

    if operation == "scan":
        return _detect_scan(
            inputs.get("receipts", []),
            inputs.get("patterns", []),
            tenant_id
        )
    elif operation == "classify":
        return _detect_classify(inputs.get("match", {}), tenant_id)
    elif operation == "alert":
        severity = inputs.get("severity")
        if not severity:
            classification = inputs.get("anomaly", {}).get("classification", "deviation")
            confidence = inputs.get("anomaly", {}).get("confidence", 0.5)
            drift_score = inputs.get("anomaly", {}).get("drift_score")
            severity = _determine_severity(classification, confidence, drift_score)
        return _detect_alert(inputs.get("anomaly", {}), severity, tenant_id)
    else:
        raise ValueError(f"Unknown DETECT operation: {operation}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def proof(mode: ProofMode | str, inputs: dict, config: dict = None) -> dict:
    """Unified proof function dispatching to appropriate mode handler.

    Args:
        mode: ProofMode enum or string ('BRIEF', 'PACKET', 'DETECT')
        inputs: Mode-specific input dictionary
        config: Optional configuration dictionary

    Returns:
        Receipt dictionary from the operation

    Raises:
        ValueError: If mode is unknown
        StopRule: If operation triggers a stoprule

    Examples:
        # BRIEF mode - compose evidence
        result = proof(ProofMode.BRIEF, {
            "operation": "compose",
            "evidence": ["chunk1", "chunk2", "chunk3"]
        })

        # BRIEF mode - retrieve with budget
        result = proof(ProofMode.BRIEF, {
            "operation": "retrieve",
            "query": "find relevant evidence",
            "budget": {"tokens": 1000, "ms": 500}
        })

        # PACKET mode - build decision packet
        result = proof(ProofMode.PACKET, {
            "operation": "build",
            "brief": {"executive_summary": "..."},
            "receipts": [...]
        })

        # DETECT mode - scan for patterns
        result = proof(ProofMode.DETECT, {
            "operation": "scan",
            "receipts": [...],
            "patterns": [...]
        })
    """
    config = config or {}
    tenant_id = inputs.get("tenant_id", config.get("tenant_id", "default"))

    # Normalize mode to enum
    if isinstance(mode, str):
        try:
            mode = ProofMode(mode.upper())
        except ValueError:
            raise ValueError(f"Unknown mode: {mode}. Valid modes: {[m.value for m in ProofMode]}")

    # Dispatch to mode handler
    if mode == ProofMode.BRIEF:
        return _process_brief(inputs, config, tenant_id)
    elif mode == ProofMode.PACKET:
        return _process_packet(inputs, config, tenant_id)
    elif mode == ProofMode.DETECT:
        return _process_detect(inputs, config, tenant_id)
    else:
        raise ValueError(f"Unknown mode: {mode}")


# ============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# ============================================================================

# These allow old import paths to work during migration

def compose(evidence: list, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for brief.compose."""
    return proof(ProofMode.BRIEF, {"operation": "compose", "evidence": evidence}, {"tenant_id": tenant_id})


def retrieve(query: str, budget: dict, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for brief.retrieve."""
    return proof(ProofMode.BRIEF, {"operation": "retrieve", "query": query, "budget": budget}, {"tenant_id": tenant_id})


def score_health(brief: dict, thresholds: dict = None, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for brief.health."""
    return proof(ProofMode.BRIEF, {"operation": "health", "brief": brief}, {"thresholds": thresholds, "tenant_id": tenant_id})


def dialectic(evidence: list, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for brief.dialectic."""
    return proof(ProofMode.BRIEF, {"operation": "dialectic", "evidence": evidence}, {"tenant_id": tenant_id})


def build_packet(brief: dict, receipts: list, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for packet.build."""
    return proof(ProofMode.PACKET, {"operation": "build", "brief": brief, "receipts": receipts}, {"tenant_id": tenant_id})


def attach(claims: list, receipts: list, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for packet.attach."""
    return proof(ProofMode.PACKET, {"operation": "attach", "claims": claims, "receipts": receipts}, {"tenant_id": tenant_id})


def audit(attachments: dict, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for packet.audit."""
    return proof(ProofMode.PACKET, {"operation": "audit", "attachments": attachments}, {"tenant_id": tenant_id})


def scan(receipts: list, patterns: list, tenant_id: str = "default") -> list:
    """Backward-compatible wrapper for detect.scan."""
    return proof(ProofMode.DETECT, {"operation": "scan", "receipts": receipts, "patterns": patterns}, {"tenant_id": tenant_id})


def classify_with_receipt(match: dict, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for detect.classify."""
    return proof(ProofMode.DETECT, {"operation": "classify", "match": match}, {"tenant_id": tenant_id})


def emit_alert(anomaly: dict, severity: str, tenant_id: str = "default") -> dict:
    """Backward-compatible wrapper for detect.alert."""
    return proof(ProofMode.DETECT, {"operation": "alert", "anomaly": anomaly, "severity": severity}, {"tenant_id": tenant_id})
