"""Proof path generation for Merkle tree inclusion."""
import json

from .hash import dual_hash


def prove(item: dict, tree: dict) -> dict:
    """Generate proof path for item inclusion in tree.

    Args:
        item: Receipt/data to prove inclusion of
        tree: Output from build_tree() with root, levels, leaves

    Returns:
        proof_receipt with proof_path for verification
    """
    item_hash = dual_hash(json.dumps(item, sort_keys=True))
    leaves = tree.get("leaves", [])
    levels = tree.get("levels", [])

    if item_hash not in leaves:
        raise ValueError("Item not in tree")

    idx = leaves.index(item_hash)
    proof_path = []

    for level in levels[:-1]:
        level_copy = level[:]
        if len(level_copy) % 2:
            level_copy.append(level_copy[-1])

        sibling_idx = idx ^ 1
        position = "right" if idx % 2 == 0 else "left"
        proof_path.append({"hash": level_copy[sibling_idx], "position": position})
        idx //= 2

    return {
        "receipt_type": "proof",
        "item_hash": item_hash,
        "merkle_root": tree["root"],
        "proof_path": proof_path,
        "tree_depth": len(levels)
    }
