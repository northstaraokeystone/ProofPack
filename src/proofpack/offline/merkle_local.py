"""Local Merkle tree operations for offline receipts.

Builds and maintains Merkle trees for offline receipt batches,
enabling proof of inclusion even before sync to main ledger.
"""
import json

from proofpack.core.receipt import dual_hash


def build_local_merkle(receipts: list[dict]) -> dict:
    """Build complete Merkle tree from receipts.

    Args:
        receipts: List of receipts to include

    Returns:
        Dict with root, leaf_hashes, and tree structure
    """
    if not receipts:
        return {
            "root": dual_hash(b"empty"),
            "leaf_count": 0,
            "leaf_hashes": [],
            "tree": [],
        }

    # Compute leaf hashes
    leaf_hashes = [
        dual_hash(json.dumps(r, sort_keys=True))
        for r in receipts
    ]

    # Build tree levels
    tree = [leaf_hashes]
    current_level = leaf_hashes

    while len(current_level) > 1:
        # Pad if odd
        if len(current_level) % 2:
            current_level = current_level + [current_level[-1]]

        # Compute next level
        next_level = []
        for i in range(0, len(current_level), 2):
            combined = current_level[i] + current_level[i + 1]
            next_level.append(dual_hash(combined))

        tree.append(next_level)
        current_level = next_level

    return {
        "root": current_level[0],
        "leaf_count": len(receipts),
        "leaf_hashes": leaf_hashes,
        "tree": tree,
    }


def get_proof_path(
    receipt_hash: str,
    merkle_tree: dict
) -> list[dict] | None:
    """Get Merkle proof path for a specific receipt.

    Args:
        receipt_hash: Dual-hash of receipt
        merkle_tree: Tree structure from build_local_merkle

    Returns:
        List of {hash, position} pairs forming proof path,
        or None if receipt not in tree
    """
    leaf_hashes = merkle_tree.get("leaf_hashes", [])
    tree = merkle_tree.get("tree", [])

    if not leaf_hashes or receipt_hash not in leaf_hashes:
        return None

    # Find leaf index
    index = leaf_hashes.index(receipt_hash)
    proof_path = []

    # Walk up the tree
    for level in tree[:-1]:  # Skip root level
        # Sibling index
        if index % 2 == 0:
            # We're left child, sibling is right
            sibling_index = index + 1
            position = "right"
        else:
            # We're right child, sibling is left
            sibling_index = index - 1
            position = "left"

        # Handle edge case (padded odd level)
        if sibling_index < len(level):
            proof_path.append({
                "hash": level[sibling_index],
                "position": position,
            })

        # Move to parent index
        index = index // 2

    return proof_path


def verify_local_inclusion(
    receipt_hash: str,
    proof_path: list[dict],
    expected_root: str
) -> bool:
    """Verify receipt is included in Merkle tree.

    Args:
        receipt_hash: Hash of receipt to verify
        proof_path: Proof path from get_proof_path
        expected_root: Expected Merkle root

    Returns:
        True if receipt verifiably included in tree
    """
    current = receipt_hash

    for step in proof_path:
        sibling = step["hash"]
        position = step["position"]

        if position == "right":
            # Sibling is on right, we're on left
            combined = current + sibling
        else:
            # Sibling is on left, we're on right
            combined = sibling + current

        current = dual_hash(combined)

    return current == expected_root


def compute_inclusion_proof(
    receipt: dict,
    all_receipts: list[dict]
) -> dict:
    """Compute complete inclusion proof for a receipt.

    Args:
        receipt: Receipt to prove inclusion for
        all_receipts: All receipts in batch

    Returns:
        Complete proof including receipt_hash, root, and path
    """
    tree = build_local_merkle(all_receipts)
    receipt_hash = dual_hash(json.dumps(receipt, sort_keys=True))
    proof_path = get_proof_path(receipt_hash, tree)

    return {
        "receipt_hash": receipt_hash,
        "merkle_root": tree["root"],
        "proof_path": proof_path,
        "leaf_count": tree["leaf_count"],
        "verified": verify_local_inclusion(
            receipt_hash,
            proof_path or [],
            tree["root"]
        ) if proof_path else False,
    }
