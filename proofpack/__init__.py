"""ProofPack: Receipt infrastructure for provable operations.

Public API:
- Core: dual_hash, emit_receipt, StopRule, merkle
- Ledger: ingest, query_receipts, anchor_batch
- Anchor: merkle_root, merkle_proof, verify_proof
"""
from .anchor import merkle_proof, merkle_root, verify_proof
from .core import StopRule, dual_hash, emit_receipt, merkle
from .ledger import anchor_batch, ingest, query_receipts

__all__ = [
    # Core
    "dual_hash",
    "emit_receipt",
    "StopRule",
    "merkle",
    # Ledger
    "ingest",
    "query_receipts",
    "anchor_batch",
    # Anchor
    "merkle_root",
    "merkle_proof",
    "verify_proof",
]
