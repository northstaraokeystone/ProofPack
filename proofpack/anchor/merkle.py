"""Merkle tree operations per CLAUDEME Section 8.

Delegates to core.receipt.merkle() for root computation.
Provides merkle_proof for generating inclusion proofs.
"""
import json

from ..core.receipt import dual_hash, merkle


def merkle_root(items: list[dict]) -> str:
    """Compute Merkle root from list of items.

    Delegates to core.receipt.merkle().

    Args:
        items: List of dicts to compute root for

    Returns:
        Merkle root as dual-hash string
    """
    return merkle(items)


def _build_tree(items: list[dict]) -> dict:
    """Build full Merkle tree structure for proof generation.

    Args:
        items: List of dicts to build tree from

    Returns:
        dict with root, levels, and leaves
    """
    if not items:
        return {
            "root": dual_hash(b"empty"),
            "levels": [],
            "leaves": [],
        }

    # Hash each item
    leaves = [
        dual_hash(json.dumps(item, sort_keys=True).encode("utf-8"))
        for item in items
    ]

    levels = [leaves[:]]
    current = leaves[:]

    while len(current) > 1:
        # Duplicate last if odd
        if len(current) % 2 == 1:
            current.append(current[-1])

        # Combine pairs
        new_level = []
        for i in range(0, len(current), 2):
            combined = (current[i] + current[i + 1]).encode("utf-8")
            new_level.append(dual_hash(combined))
        current = new_level
        levels.append(current[:])

    return {
        "root": current[0],
        "levels": levels,
        "leaves": leaves,
    }


def merkle_proof(item: dict, items: list[dict]) -> dict:
    """Generate Merkle proof for item in tree.

    Args:
        item: The item to prove inclusion of
        items: All items in the tree

    Returns:
        dict with item_hash, path (sibling hashes), and indices (0=left, 1=right)

    Raises:
        ValueError: If item not found in tree
    """
    tree = _build_tree(items)
    item_hash = dual_hash(json.dumps(item, sort_keys=True).encode("utf-8"))
    leaves = tree["leaves"]
    levels = tree["levels"]

    if item_hash not in leaves:
        raise ValueError("Item not in tree")

    idx = leaves.index(item_hash)
    path = []
    indices = []

    for level in levels[:-1]:  # All levels except root
        # Handle odd-length levels
        level_copy = level[:]
        if len(level_copy) % 2 == 1:
            level_copy.append(level_copy[-1])

        # Get sibling
        sibling_idx = idx ^ 1  # XOR to get sibling index
        sibling_hash = level_copy[sibling_idx]
        path.append(sibling_hash)

        # Record position: 0 if we're on left (even), 1 if on right (odd)
        indices.append(idx % 2)

        # Move up tree
        idx //= 2

    return {
        "item_hash": item_hash,
        "path": path,
        "indices": indices,
        "root": tree["root"],
    }
