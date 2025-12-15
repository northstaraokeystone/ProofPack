"""Receipt ingestion with tenant isolation per CLAUDEME Section 4.1.

SLO: Ingest <= 50ms p95. Stoprule if latency > 100ms.
"""
import time

from ..core.receipt import dual_hash, emit_receipt, StopRule
from .store import LedgerStore

# Default store instance (can be overridden)
_default_store: LedgerStore | None = None


def _get_store() -> LedgerStore:
    """Get or create default LedgerStore."""
    global _default_store
    if _default_store is None:
        _default_store = LedgerStore()
    return _default_store


def set_store(store: LedgerStore) -> None:
    """Set the default store instance (for testing)."""
    global _default_store
    _default_store = store


def ingest(
    payload: bytes,
    tenant_id: str,
    source_type: str = "unknown",
    store: LedgerStore | None = None,
) -> dict:
    """Ingest a payload and emit an ingest receipt.

    SLO: <= 50ms p95. Stoprule if latency > 100ms.

    Args:
        payload: Raw bytes to ingest
        tenant_id: Tenant identifier for isolation
        source_type: Source type (default: "unknown")
        store: Optional LedgerStore instance

    Returns:
        Ingest receipt dict

    Raises:
        StopRule: If latency exceeds 100ms
    """
    start_time = time.perf_counter()

    # Use provided store or default
    ledger = store if store is not None else _get_store()

    # Compute payload hash
    payload_hash = dual_hash(payload)

    # Build receipt data
    data = {
        "tenant_id": tenant_id,
        "payload_hash": payload_hash,
        "redactions": [],
        "source_type": source_type,
    }

    # Emit receipt
    receipt = emit_receipt("ingest", data)

    # Store receipt
    ledger.append(receipt)

    # Check SLO
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if elapsed_ms > 100:
        raise StopRule(f"Ingest latency {elapsed_ms:.2f}ms exceeds 100ms limit")

    return receipt


def batch_ingest(
    payloads: list[bytes],
    tenant_id: str,
    source_type: str = "unknown",
    store: LedgerStore | None = None,
) -> list[dict]:
    """Batch ingest multiple payloads.

    Args:
        payloads: List of raw bytes to ingest
        tenant_id: Tenant identifier for isolation
        source_type: Source type (default: "unknown")
        store: Optional LedgerStore instance

    Returns:
        List of ingest receipt dicts
    """
    return [
        ingest(payload, tenant_id, source_type, store)
        for payload in payloads
    ]
