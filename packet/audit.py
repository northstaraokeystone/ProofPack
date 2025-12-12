"""Consistency auditing with 99.9% threshold gate."""
from datetime import datetime, timedelta
from ledger.core import emit_receipt, StopRule

CONSISTENCY_SCHEMA = {
    "receipt_type": "consistency",
    "match_rate": "float 0-1",
    "threshold": 0.999,
    "violations": [{"claim_id": "str", "reason": "str"}],
    "status": "pass|fail",
    "escalation_hours": "int|null"
}

HALT_SCHEMA = {
    "receipt_type": "halt",
    "reason": "str",
    "match_rate": "float",
    "threshold": "float",
    "escalation_deadline": "ISO8601"
}


def audit(attachments: dict, tenant_id: str = "default") -> dict:
    """Verify attachment consistency meets 99.9% threshold. SLO: <=1s."""
    attached_count = attachments.get("attached_count", 0)
    total_claims = attachments.get("total_claims", 0)
    orphan_claims = attachments.get("orphan_claims", [])

    # Compute match rate
    match_rate = attached_count / total_claims if total_claims > 0 else 0.0
    threshold = 0.999  # HARDCODED per CLAUDEME.txt:438

    # Build violations list
    violations = [
        {"claim_id": cid, "reason": "no_receipt_attached"}
        for cid in orphan_claims
    ]

    if match_rate < threshold:
        # Emit anomaly first
        emit_receipt("anomaly", {
            "metric": "fusion_match",
            "baseline": threshold,
            "delta": match_rate - threshold,
            "classification": "violation",
            "action": "halt"
        }, tenant_id)

        # Emit halt receipt with 4h escalation
        escalation_deadline = (
            datetime.utcnow() + timedelta(hours=4)
        ).isoformat() + "Z"

        emit_receipt("halt", {
            "reason": "consistency_below_threshold",
            "match_rate": match_rate,
            "threshold": threshold,
            "escalation_deadline": escalation_deadline
        }, tenant_id)

        raise StopRule(f"Fusion match {match_rate:.4f} < {threshold}")

    return emit_receipt("consistency", {
        "match_rate": match_rate,
        "threshold": threshold,
        "violations": violations,
        "status": "pass" if match_rate >= threshold else "fail",
        "escalation_hours": None
    }, tenant_id)
