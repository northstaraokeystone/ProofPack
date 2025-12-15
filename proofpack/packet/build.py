"""Assemble final decision packet.

Classes: DecisionPacket (frozen dataclass)
Functions: build_packet, extract_decision_health
SLO: ≤2s p95
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import uuid

from ..core.receipt import emit_receipt, dual_hash, StopRule
from ..anchor import merkle_root


@dataclass(frozen=True)
class DecisionPacket:
    """Immutable decision packet per CLAUDEME §5 DECISION_GLYPH.

    Fields per DECISION_GLYPH specification.
    """
    packet_id: str
    ts: str
    tenant_id: str
    brief: dict
    brief_hash: str
    decision_health: dict
    dialectical_record: dict
    attached_receipts: list
    attach_map: dict
    consistency_score: float
    merkle_anchor: str

    def to_dict(self) -> dict:
        """Convert to dict representation."""
        return asdict(self)


def build_packet(
    brief: dict,
    attachments: dict,
    tenant_id: str = "default"
) -> dict:
    """Assemble final decision packet.

    Args:
        brief: Brief dict with executive_summary or synthesized_response
        attachments: attach_receipt dict from attach()
        tenant_id: Tenant identifier

    Returns:
        DecisionPacket as dict

    Raises:
        StopRule: If brief missing required fields
    """
    # Validate brief has executive_summary or synthesized_response
    if "executive_summary" not in brief and "synthesized_response" not in brief:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "brief_validation",
            "baseline": "required_field_present",
            "delta": "missing_executive_summary_or_synthesized_response",
            "classification": "violation",
            "action": "halt"
        })
        raise StopRule(
            "Brief missing required field: must have 'executive_summary' or 'synthesized_response'"
        )

    # Extract fields
    attach_map = attachments.get("attach_map", {})
    decision_health = extract_decision_health(brief)
    dialectical_record = brief.get("dialectical_record", {
        "pro": [],
        "con": [],
        "gaps": []
    })

    # Compute brief_hash
    import json
    brief_bytes = json.dumps(brief, sort_keys=True).encode("utf-8")
    brief_hash = dual_hash(brief_bytes)

    # Extract unique receipt hashes
    attached_receipts = []
    for receipt_list in attach_map.values():
        for receipt_hash in receipt_list:
            if receipt_hash not in attached_receipts:
                attached_receipts.append(receipt_hash)

    # Compute merkle_anchor from attached receipts
    # Convert receipt hashes to dict format for merkle_root
    receipt_items = [{"hash": rh} for rh in attached_receipts]
    merkle_anchor = merkle_root(receipt_items) if receipt_items else dual_hash(b"empty")

    # Generate packet_id
    packet_id = str(uuid.uuid4())

    # Generate timestamp
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Get consistency score from attachments
    consistency_score = attachments.get("match_score", 0.0)
    if "match_score" not in attachments:
        # If not in attachments, compute it
        claim_count = attachments.get("claim_count", 0)
        attached_count = attachments.get("attached_count", 0)
        consistency_score = attached_count / claim_count if claim_count > 0 else 1.0

    # Create DecisionPacket
    packet = DecisionPacket(
        packet_id=packet_id,
        ts=ts,
        tenant_id=tenant_id,
        brief=brief,
        brief_hash=brief_hash,
        decision_health=decision_health,
        dialectical_record=dialectical_record,
        attached_receipts=attached_receipts,
        attach_map=attach_map,
        consistency_score=consistency_score,
        merkle_anchor=merkle_anchor,
    )

    # Emit packet receipt
    packet_data = {
        "tenant_id": tenant_id,
        "packet_id": packet_id,
        "brief_hash": brief_hash,
        "attachment_count": len(attached_receipts),
        "consistency_score": consistency_score,
        "decision_health": decision_health,
    }
    emit_receipt("packet", packet_data)

    return packet.to_dict()


def extract_decision_health(brief: dict) -> dict:
    """Extract decision health metrics from brief.

    Args:
        brief: Brief dict

    Returns:
        Dict with strength, coverage, efficiency floats (0-1)
    """
    # Extract from brief["decision_health"] if present
    health = brief.get("decision_health", {})

    # Default values
    default_health = {
        "strength": 0.0,
        "coverage": 0.0,
        "efficiency": 0.0,
    }

    # Merge and validate
    result = {}
    for key in ["strength", "coverage", "efficiency"]:
        value = health.get(key, default_health[key])

        # Validate is float 0-1
        try:
            value = float(value)
            value = max(0.0, min(1.0, value))  # Clamp to 0-1
        except (TypeError, ValueError):
            value = default_health[key]

        result[key] = value

    return result
