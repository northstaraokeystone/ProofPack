"""Decision packet assembly for sign-off."""
import uuid
from ledger.core import emit_receipt, dual_hash, merkle

PACKET_SCHEMA = {
    "receipt_type": "packet",
    "packet_id": "uuid",
    "brief": "str",
    "decision_health": {"strength": "float", "coverage": "float", "efficiency": "float"},
    "dialectical_record": {"pro": ["str"], "con": ["str"], "gaps": ["str"]} or None,
    "attached_receipts": ["receipt_hash"],
    "receipt_count": "int",
    "merkle_anchor": "hex",
    "signature": "hex|null"
}


def build(brief: dict, receipts: list, tenant_id: str = "default") -> dict:
    """Assemble final decision packet for sign-off. SLO: <=2s."""
    packet_id = str(uuid.uuid4())

    # Extract executive summary from brief receipt
    executive_summary = brief.get("executive_summary", "")

    # Extract decision_health (may come from health_receipt or brief)
    decision_health = brief.get("decision_health", {
        "strength": brief.get("strength", 0.0),
        "coverage": brief.get("coverage", 0.0),
        "efficiency": brief.get("efficiency", 0.0)
    })

    # Extract dialectical_record if present
    dialectical_record = brief.get("dialectical_record", None)
    if dialectical_record is None and "pro" in brief:
        dialectical_record = {
            "pro": brief.get("pro", []),
            "con": brief.get("con", []),
            "gaps": brief.get("gaps", [])
        }

    # Collect receipt hashes for merkle anchoring
    attached_receipts = [
        r.get("payload_hash", dual_hash(r)) for r in receipts
    ]

    # Compute merkle anchor of all attached receipts
    merkle_anchor = merkle(receipts)

    return emit_receipt("packet", {
        "packet_id": packet_id,
        "brief": executive_summary,
        "decision_health": decision_health,
        "dialectical_record": dialectical_record,
        "attached_receipts": attached_receipts,
        "receipt_count": len(attached_receipts),
        "merkle_anchor": merkle_anchor,
        "signature": None  # To be filled by approver
    }, tenant_id)
