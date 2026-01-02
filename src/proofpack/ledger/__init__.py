"""Ledger module: receipts backbone with Merkle anchoring."""
from .anchor import ANCHOR_SCHEMA, anchor
from .compact import COMPACT_SCHEMA, compact
from .core import StopRule, dual_hash, emit_receipt, merkle
from .ingest import INGEST_SCHEMA, ingest
from .verify import VERIFY_SCHEMA, verify

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
