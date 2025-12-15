"""Map claims to supporting receipts.

Functions: attach, map_claims, find_supporting_receipts, extract_claim_id
SLO: ≤500ms p95
Stoprule: latency >1000ms → emit anomaly_receipt, raise StopRule
"""
import time
from ..core.receipt import emit_receipt, dual_hash, StopRule


def attach(claims: list[dict], receipts: list[dict], tenant_id: str = "default") -> dict:
    """Map claims to supporting receipts and emit attach_receipt.

    Args:
        claims: List of claim dicts
        receipts: List of receipt dicts
        tenant_id: Tenant identifier

    Returns:
        attach_receipt dict

    Raises:
        StopRule: If latency exceeds 1000ms
    """
    start_time = time.perf_counter()

    # Build mapping
    attach_map = map_claims(claims, receipts)

    # Count statistics
    claim_count = len(claims)
    receipt_count = len(receipts)
    attached_count = sum(1 for receipts_list in attach_map.values() if receipts_list)

    # Find unattached claims
    unattached_claims = [
        claim_id for claim_id, receipt_list in attach_map.items()
        if not receipt_list
    ]

    # Check latency stoprule
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if elapsed_ms > 1000:
        # Emit anomaly receipt before raising
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "attach_latency",
            "baseline": 500,
            "delta": elapsed_ms - 500,
            "classification": "violation",
            "action": "halt"
        })
        raise StopRule(f"attach latency {elapsed_ms:.0f}ms exceeds 1000ms threshold")

    # Emit attach receipt
    data = {
        "tenant_id": tenant_id,
        "claim_count": claim_count,
        "receipt_count": receipt_count,
        "attached_count": attached_count,
        "unattached_claims": unattached_claims,
        "attach_map": attach_map,
    }

    return emit_receipt("attach", data)


def map_claims(claims: list[dict], receipts: list[dict]) -> dict:
    """Map each claim to its supporting receipts.

    Pure function with no side effects.

    Args:
        claims: List of claim dicts
        receipts: List of receipt dicts

    Returns:
        Dict mapping claim_id → list of receipt_hash strings
    """
    result = {}

    for claim in claims:
        claim_id = extract_claim_id(claim)
        supporting_receipts = find_supporting_receipts(claim, receipts)
        result[claim_id] = supporting_receipts

    return result


def find_supporting_receipts(claim: dict, receipts: list[dict]) -> list[str]:
    """Find receipts that support this claim.

    Pure function with no side effects.

    Matching strategy (in order):
    1. If claim has evidence_ids field, match receipts by id
    2. If claim has source_hash field, match receipts by source
    3. If claim has chunk_id field, match receipts referencing same chunk

    Args:
        claim: Claim dict
        receipts: List of receipt dicts

    Returns:
        List of matching receipt payload_hash values
    """
    matches = []

    # Strategy 1: Match by evidence_ids
    if "evidence_ids" in claim:
        evidence_ids = claim["evidence_ids"]
        if not isinstance(evidence_ids, list):
            evidence_ids = [evidence_ids]

        for receipt in receipts:
            receipt_id = receipt.get("id")
            if receipt_id in evidence_ids:
                matches.append(receipt.get("payload_hash", ""))

    # Strategy 2: Match by source_hash
    elif "source_hash" in claim:
        source_hash = claim["source_hash"]
        for receipt in receipts:
            if receipt.get("source_hash") == source_hash:
                matches.append(receipt.get("payload_hash", ""))

    # Strategy 3: Match by chunk_id
    elif "chunk_id" in claim:
        chunk_id = claim["chunk_id"]
        for receipt in receipts:
            # Check if receipt references this chunk
            if receipt.get("chunk_id") == chunk_id:
                matches.append(receipt.get("payload_hash", ""))

    # Remove empty strings and duplicates
    matches = [m for m in matches if m]
    return list(dict.fromkeys(matches))  # Deduplicate while preserving order


def extract_claim_id(claim: dict) -> str:
    """Extract or generate claim identifier.

    Args:
        claim: Claim dict

    Returns:
        Claim ID string
    """
    if "id" in claim:
        return claim["id"]

    # Generate ID from claim content hash
    import json
    claim_bytes = json.dumps(claim, sort_keys=True).encode("utf-8")
    return dual_hash(claim_bytes)
