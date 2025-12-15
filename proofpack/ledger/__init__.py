"""Ledger subpackage for receipt storage and operations.

Provides ingestion, querying, compaction, and anchoring.
"""
from ..anchor import merkle_root
from ..core.receipt import emit_receipt
from .compact import compact, verify_invariants
from .ingest import batch_ingest, ingest
from .query import query_receipts, trace_lineage
from .store import LedgerStore


def anchor_batch(
    receipts: list[dict],
    tenant_id: str = "default",
) -> dict:
    """Compute Merkle root for batch of receipts and emit anchor receipt.

    Wrapper that calls anchor.merkle_root and emits anchor_receipt.

    Args:
        receipts: List of receipts to anchor
        tenant_id: Tenant identifier

    Returns:
        Anchor receipt dict
    """
    root = merkle_root(receipts)

    data = {
        "tenant_id": tenant_id,
        "merkle_root": root,
        "hash_algos": ["sha256", "blake3"],
        "batch_size": len(receipts),
        "proof_path": None,
    }

    return emit_receipt("anchor", data)


__all__ = [
    "ingest",
    "batch_ingest",
    "query_receipts",
    "trace_lineage",
    "compact",
    "verify_invariants",
    "anchor_batch",
    "LedgerStore",
]
