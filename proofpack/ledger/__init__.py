"""Ledger subpackage for receipt storage and operations.

Provides ingestion, querying, compaction, and anchoring.
"""
from .anchor import anchor_batch, generate_proof, verify_proof
from .compact import compact, verify_invariants
from .ingest import batch_ingest, ingest
from .query import query_receipts, trace_lineage
from .store import LedgerStore

__all__ = [
    "LedgerStore",
    "ingest",
    "batch_ingest",
    "query_receipts",
    "trace_lineage",
    "compact",
    "verify_invariants",
    "anchor_batch",
    "generate_proof",
    "verify_proof",
]
