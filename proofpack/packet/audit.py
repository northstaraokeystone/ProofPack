"""Verify claim-receipt links meet consistency threshold.

Functions: audit_consistency, compute_match_score, halt_on_mismatch
Threshold: 0.999 per CLAUDEME §6 Fusion Match
SLO: ≤1s p95
"""
from datetime import datetime, timezone, timedelta
from ..core.receipt import emit_receipt, StopRule


def audit_consistency(
    attachments: dict,
    tenant_id: str = "default",
    threshold: float = 0.999
) -> dict:
    """Verify claim-receipt attachment consistency.

    Args:
        attachments: attach_receipt dict from attach()
        tenant_id: Tenant identifier
        threshold: Minimum required match score (default 0.999)

    Returns:
        consistency_receipt dict

    Raises:
        StopRule: If match_score < threshold
    """
    # Compute match score and mismatches
    match_score, mismatches = compute_match_score(attachments)

    # Determine if passed
    passed = match_score >= threshold

    # Build consistency receipt
    data = {
        "tenant_id": tenant_id,
        "match_score": match_score,
        "threshold": threshold,
        "passed": passed,
        "mismatches": mismatches,
        "escalation_hours": None if passed else 4,
    }

    # Emit consistency receipt
    consistency_receipt = emit_receipt("consistency", data)

    # CRITICAL: Halt on mismatch
    if not passed:
        halt_on_mismatch(match_score, threshold, tenant_id)

    return consistency_receipt


def compute_match_score(attachments: dict) -> tuple[float, list[dict]]:
    """Compute consistency match score from attachments.

    Pure function with no side effects.

    Args:
        attachments: attach_receipt dict with claim_count, attached_count

    Returns:
        Tuple of (score, mismatches_list)
        - score: float 0-1 (attached_count / claim_count)
        - mismatches: list of {claim_id, reason} dicts
    """
    claim_count = attachments.get("claim_count", 0)
    attached_count = attachments.get("attached_count", 0)
    unattached_claims = attachments.get("unattached_claims", [])

    # Avoid division by zero
    if claim_count == 0:
        return 1.0, []

    # Compute score
    score = attached_count / claim_count

    # Build mismatches list
    mismatches = [
        {"claim_id": claim_id, "reason": "no_supporting_receipts"}
        for claim_id in unattached_claims
    ]

    return score, mismatches


def halt_on_mismatch(match_score: float, threshold: float, tenant_id: str) -> dict:
    """Halt processing on consistency mismatch.

    Emits halt_receipt and anomaly_receipt, then raises StopRule.

    Args:
        match_score: Actual match score
        threshold: Required threshold
        tenant_id: Tenant identifier

    Raises:
        StopRule: Always raised after emitting receipts
    """
    # Compute escalation deadline (now + 4 hours)
    now = datetime.now(timezone.utc)
    escalation_deadline = (now + timedelta(hours=4)).isoformat().replace("+00:00", "Z")

    # Emit halt receipt
    halt_data = {
        "tenant_id": tenant_id,
        "reason": f"Consistency match score {match_score:.4f} below threshold {threshold}",
        "match_score": match_score,
        "threshold": threshold,
        "escalation_deadline": escalation_deadline,
        "requires_human": True,
    }
    emit_receipt("halt", halt_data)

    # Emit anomaly receipt
    anomaly_data = {
        "tenant_id": tenant_id,
        "metric": "consistency_match",
        "baseline": threshold,
        "delta": match_score - threshold,  # Negative value
        "classification": "violation",
        "action": "halt",
    }
    emit_receipt("anomaly", anomaly_data)

    # Raise StopRule
    raise StopRule(
        f"Consistency violation: match score {match_score:.4f} < threshold {threshold}. "
        f"Human review required by {escalation_deadline}."
    )
