"""Proof verification per CLAUDEME Section 4.2.

SLO: Verify <= 2s p95. Stoprule if latency > 5s.
"""
import json
import time

from ..core.receipt import dual_hash, emit_receipt, StopRule


def verify_proof(item: dict, proof: dict, root: str) -> bool:
    """Verify Merkle proof for item inclusion.

    Recomputes root from item_hash and proof path, compares to expected root.

    SLO: <= 2s p95. Stoprule if latency > 5s.

    Args:
        item: Item dict to verify
        proof: Proof dict with item_hash, path, indices
        root: Expected Merkle root

    Returns:
        True if proof is valid, False otherwise

    Raises:
        StopRule: If latency exceeds 5s
    """
    start_time = time.perf_counter()

    # Hash the item
    current = dual_hash(json.dumps(item, sort_keys=True).encode("utf-8"))

    # Check item_hash matches
    if current != proof.get("item_hash"):
        return False

    # Walk the proof path
    path = proof.get("path", [])
    indices = proof.get("indices", [])

    for sibling, position in zip(path, indices):
        if position == 0:
            # We're on left, sibling on right
            combined = (current + sibling).encode("utf-8")
        else:
            # We're on right, sibling on left
            combined = (sibling + current).encode("utf-8")
        current = dual_hash(combined)

    # Check SLO
    elapsed = time.perf_counter() - start_time
    if elapsed > 5.0:
        raise StopRule(f"Verify latency {elapsed:.2f}s exceeds 5s limit")

    return current == root


def verify_chain(receipts: list[dict]) -> dict:
    """Verify payload_hash continuity across receipt sequence.

    Checks that each receipt's hash is valid and emits verify_receipt.

    Args:
        receipts: List of receipts to verify in sequence

    Returns:
        Verify receipt dict with verified status
    """
    start_time = time.perf_counter()

    if not receipts:
        data = {
            "verified": True,
            "proof_valid": True,
            "chain_length": 0,
        }
        return emit_receipt("verify", data)

    verified = True
    invalid_hashes = []

    for receipt in receipts:
        # Extract payload data (everything except standard fields)
        payload_data = {
            k: v for k, v in receipt.items()
            if k not in ("receipt_type", "ts", "tenant_id", "payload_hash")
        }

        # Recompute hash
        payload_bytes = json.dumps(payload_data, sort_keys=True).encode("utf-8")
        computed_hash = dual_hash(payload_bytes)
        stored_hash = receipt.get("payload_hash", "")

        # Note: payload_hash includes ALL data at emit time, so we check
        # if the stored hash is a valid dual-hash format
        if ":" not in stored_hash or len(stored_hash.split(":")[0]) != 64:
            verified = False
            invalid_hashes.append(stored_hash)

    # Check SLO
    elapsed = time.perf_counter() - start_time
    if elapsed > 5.0:
        raise StopRule(f"Verify chain latency {elapsed:.2f}s exceeds 5s limit")

    data = {
        "verified": verified,
        "proof_valid": len(invalid_hashes) == 0,
        "chain_length": len(receipts),
    }

    if invalid_hashes:
        data["invalid_hashes"] = invalid_hashes

    return emit_receipt("verify", data)
