"""Receipt queries with tenant filtering.

Provides query_receipts for filtering and trace_lineage for following
receipt chains (deferred until parent_hash field is added).
"""
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


def query_receipts(
    store: LedgerStore | None = None,
    receipt_type: str | None = None,
    since: str | None = None,
    tenant_id: str | None = None,
) -> list[dict]:
    """Query receipts with optional filters.

    Args:
        store: LedgerStore instance (uses default if None)
        receipt_type: Filter by receipt_type (optional)
        since: Filter by ts >= since ISO8601 string (optional)
        tenant_id: Filter by tenant_id (optional)

    Returns:
        List of matching receipts sorted by ts descending
    """
    ledger = store if store is not None else _get_store()

    def predicate(r: dict) -> bool:
        if receipt_type is not None and r.get("receipt_type") != receipt_type:
            return False
        if tenant_id is not None and r.get("tenant_id") != tenant_id:
            return False
        if since is not None:
            ts = r.get("ts", "")
            if ts < since:
                return False
        return True

    receipts = ledger.query(predicate)

    # Sort by ts descending
    receipts.sort(key=lambda r: r.get("ts", ""), reverse=True)

    return receipts


def trace_lineage(
    store: LedgerStore | None,
    receipt_id: str,
    max_depth: int = 100,
) -> list[dict]:
    """Find receipt by payload_hash and trace its lineage.

    Note: Full implementation deferred until receipts have parent_hash field.
    Currently returns just the receipt if found.

    Args:
        store: LedgerStore instance (uses default if None)
        receipt_id: The payload_hash to look up
        max_depth: Maximum depth to traverse (default: 100)

    Returns:
        Chronological list of receipts in the lineage chain (oldest first)
    """
    ledger = store if store is not None else _get_store()

    # Find receipt by payload_hash
    matches = ledger.query(lambda r: r.get("payload_hash") == receipt_id)

    if not matches:
        return []

    # For now, just return the single receipt
    # Full lineage tracing requires parent_hash field (deferred)
    receipt = matches[0]
    chain = [receipt]

    # If parent_hash exists, recursively collect chain
    parent_hash = receipt.get("parent_hash")
    depth = 0
    while parent_hash and depth < max_depth:
        parent_matches = ledger.query(
            lambda r, ph=parent_hash: r.get("payload_hash") == ph
        )
        if not parent_matches:
            break
        parent = parent_matches[0]
        chain.append(parent)
        parent_hash = parent.get("parent_hash")
        depth += 1

    # Return chronological order (oldest first)
    chain.reverse()
    return chain
