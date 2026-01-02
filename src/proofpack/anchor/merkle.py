"""Merkle tree computation with dual-hash."""
import json

from .hash import dual_hash


def merkle(items: list) -> str:
    """Compute Merkle root from list of items.

    - Empty list: return dual_hash(b"empty")
    - Hash each item: dual_hash(json.dumps(item, sort_keys=True))
    - Odd count: duplicate last hash
    - Pairwise combine until single root
    """
    if not items:
        return dual_hash(b"empty")

    hashes = [dual_hash(json.dumps(i, sort_keys=True)) for i in items]

    while len(hashes) > 1:
        if len(hashes) % 2:
            hashes.append(hashes[-1])
        hashes = [dual_hash(hashes[i] + hashes[i + 1])
                  for i in range(0, len(hashes), 2)]

    return hashes[0]


def build_tree(items: list) -> dict:
    """Build full Merkle tree structure for proof generation.

    Returns: {"root": str, "levels": list[list[str]], "leaves": list[str]}
    """
    if not items:
        return {"root": dual_hash(b"empty"), "levels": [], "leaves": []}

    leaves = [dual_hash(json.dumps(i, sort_keys=True)) for i in items]
    levels = [leaves[:]]
    current = leaves[:]

    while len(current) > 1:
        if len(current) % 2:
            current.append(current[-1])
        current = [dual_hash(current[i] + current[i + 1])
                   for i in range(0, len(current), 2)]
        levels.append(current[:])

    return {"root": current[0], "levels": levels, "leaves": leaves}
