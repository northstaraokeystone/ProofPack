"""Proof verification for Merkle tree inclusion."""
import json

from .hash import dual_hash


def verify(item: dict, proof: dict, root: str) -> bool:
    """Verify item inclusion using proof path.

    Args:
        item: Receipt/data to verify
        proof: proof_receipt from prove()
        root: Expected merkle root

    Returns:
        True if valid, False otherwise
    """
    current = dual_hash(json.dumps(item, sort_keys=True))

    for step in proof.get("proof_path", []):
        sibling = step["hash"]
        if step["position"] == "right":
            current = dual_hash(current + sibling)
        else:
            current = dual_hash(sibling + current)

    return current == root
