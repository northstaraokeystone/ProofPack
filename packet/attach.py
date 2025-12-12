"""Claim-to-receipt mapping for decision fusion."""
from ledger.core import emit_receipt, dual_hash

ATTACH_SCHEMA = {
    "receipt_type": "attach",
    "mappings": "dict[claim_id: list[receipt_id]]",
    "attached_count": "int",
    "total_claims": "int",
    "orphan_claims": ["claim_id"],
    "unused_receipts": ["receipt_id"]
}


def attach(claims: list, receipts: list, tenant_id: str = "default") -> dict:
    """Map claims to their supporting receipts. SLO: <=500ms."""
    mappings = {}
    used_receipts = set()

    # Build receipt lookup by payload_hash
    receipt_by_hash = {r.get("payload_hash"): r for r in receipts}

    for claim in claims:
        claim_id = claim.get("claim_id")
        claim_text = claim.get("text", "")
        claim_hash = dual_hash(claim_text)

        matched = []
        for r in receipts:
            r_hash = r.get("payload_hash", "")
            # Match by explicit link or content hash overlap
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
        "mappings": mappings,
        "attached_count": sum(1 for rids in mappings.values() if rids),
        "total_claims": len(claims),
        "orphan_claims": orphan_claims,
        "unused_receipts": unused_receipts
    }, tenant_id)
