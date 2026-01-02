"""QED-to-ProofPack integration bridge.

Translates QED compression engine outputs into ProofPack receipt streams.
QED remains sacred - this bridge is read-only on QED outputs.

The bridge that watches itself: emits receipts ABOUT its own translations.
When manifest says "1000 windows" but ledger has 998, the qed_integrity_receipt
catches it before anyone else.

Exports:
    ingest_qed_output: Single window ingestion
    batch_windows: Batch window ingestion with Merkle anchoring
    parse_manifest: Parse QED run manifest
    link_to_receipts: Link manifest to stored receipts
    validate_hook: Validate hook name
    HOOK_TENANT_MAP: Hook to tenant ID mapping
    VALID_HOOKS: Set of valid hook names
"""
from .hooks import HOOK_TENANT_MAP, VALID_HOOKS, get_tenant_id, validate_hook
from .ingest import batch_windows, extract_window_metrics, ingest_qed_output
from .manifest import link_to_receipts, parse_manifest, validate_manifest_integrity

__all__ = [
    # Primary functions
    "ingest_qed_output",
    "batch_windows",
    "parse_manifest",
    "link_to_receipts",
    "validate_manifest_integrity",
    # Hook utilities
    "validate_hook",
    "get_tenant_id",
    "extract_window_metrics",
    # Constants
    "HOOK_TENANT_MAP",
    "VALID_HOOKS",
]
