"""Cryptographic immutability via dual-hash Merkle proofs.

Standalone crypto primitives for ProofPack.
"""
from .hash import dual_hash
from .merkle import merkle, build_tree
from .prove import prove
from .verify import verify

PROOF_SCHEMA = {
    "receipt_type": "proof",
    "item_hash": "str",
    "merkle_root": "str",
    "proof_path": [{"hash": "str", "position": "str"}],
    "tree_depth": "int"
}

__all__ = ["dual_hash", "merkle", "build_tree", "prove", "verify", "PROOF_SCHEMA"]
