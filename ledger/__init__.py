"""Ledger module: receipts backbone with Merkle anchoring."""
from .core import dual_hash, emit_receipt, merkle, StopRule
from .ingest import ingest, INGEST_SCHEMA
from .anchor import anchor, ANCHOR_SCHEMA
from .verify import verify, VERIFY_SCHEMA
from .compact import compact, COMPACT_SCHEMA

RECEIPT_SCHEMA = {
    "ingest_receipt": INGEST_SCHEMA,
    "anchor_receipt": ANCHOR_SCHEMA,
    "verify_receipt": VERIFY_SCHEMA,
    "compaction_receipt": COMPACT_SCHEMA
}

__all__ = [
    "dual_hash",
    "emit_receipt",
    "merkle",
    "StopRule",
    "ingest",
    "anchor",
    "verify",
    "compact",
    "INGEST_SCHEMA",
    "ANCHOR_SCHEMA",
    "VERIFY_SCHEMA",
    "COMPACT_SCHEMA",
    "RECEIPT_SCHEMA"
]
