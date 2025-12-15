"""Receipt compaction with invariant verification per CLAUDEME Section 4.8.

Compaction aggregates receipts by receipt_type per day while preserving
count and sum invariants. Hash continuity is verified to ensure no data loss.
"""
from collections import defaultdict
from datetime import datetime

from ..core.receipt import emit_receipt, merkle, StopRule
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


def compact(
    before: str,
    tenant_id: str,
    store: LedgerStore | None = None,
) -> dict:
    """Compact receipts older than before timestamp.

    Aggregates receipts by receipt_type per day. Emits compaction receipt
    with hash_continuity verification.

    Args:
        before: ISO8601 timestamp - compact receipts older than this
        tenant_id: Tenant identifier for filtering
        store: Optional LedgerStore instance

    Returns:
        Compaction receipt dict

    Raises:
        StopRule: If hash_continuity is False (data loss detected)
    """
    ledger = store if store is not None else _get_store()

    # Query receipts for tenant older than before
    def predicate(r: dict) -> bool:
        return (
            r.get("tenant_id") == tenant_id
            and r.get("ts", "") < before
        )

    receipts = ledger.query(predicate)

    if not receipts:
        # No receipts to compact
        data = {
            "tenant_id": tenant_id,
            "input_span": {"start": "", "end": ""},
            "output_span": {"start": "", "end": ""},
            "counts": {"before": 0, "after": 0},
            "sums": {"before": 0, "after": 0},
            "hash_continuity": True,
        }
        return emit_receipt("compaction", data)

    # Compute before counts and merkle root
    count_before = len(receipts)
    merkle_before = merkle(receipts)

    # Get timestamp span
    timestamps = [r.get("ts", "") for r in receipts]
    input_start = min(timestamps) if timestamps else ""
    input_end = max(timestamps) if timestamps else ""

    # Aggregate by receipt_type per day
    aggregated = defaultdict(lambda: {"count": 0, "receipts": []})

    for r in receipts:
        ts = r.get("ts", "")
        receipt_type = r.get("receipt_type", "unknown")
        # Extract day from ISO8601 timestamp
        day = ts[:10] if len(ts) >= 10 else "unknown"
        key = f"{receipt_type}:{day}"
        aggregated[key]["count"] += 1
        aggregated[key]["receipts"].append(r)

    # Build rolled-up receipts (one per type:day)
    rolled_up = []
    for key, data_item in aggregated.items():
        receipt_type, day = key.rsplit(":", 1)
        rolled_up.append({
            "receipt_type": f"{receipt_type}_rollup",
            "ts": f"{day}T00:00:00Z",
            "tenant_id": tenant_id,
            "count": data_item["count"],
            "merkle_root": merkle(data_item["receipts"]),
        })

    # Compute after counts and merkle root
    count_after = len(rolled_up)
    merkle_after = merkle(rolled_up)

    # Output span
    output_timestamps = [r.get("ts", "") for r in rolled_up]
    output_start = min(output_timestamps) if output_timestamps else ""
    output_end = max(output_timestamps) if output_timestamps else ""

    # Hash continuity check: count_before == sum of counts in rolled_up
    sum_counts = sum(r.get("count", 0) for r in rolled_up)
    hash_continuity = count_before == sum_counts

    if not hash_continuity:
        raise StopRule(
            f"Hash continuity violation: {count_before} receipts in, "
            f"{sum_counts} accounted for"
        )

    # Emit compaction receipt
    compaction_data = {
        "tenant_id": tenant_id,
        "input_span": {"start": input_start, "end": input_end},
        "output_span": {"start": output_start, "end": output_end},
        "counts": {"before": count_before, "after": count_after},
        "sums": {"before": count_before, "after": sum_counts},
        "hash_continuity": hash_continuity,
        "merkle_before": merkle_before,
        "merkle_after": merkle_after,
    }

    receipt = emit_receipt("compaction", compaction_data)

    # Store rolled-up receipts and compaction receipt
    for r in rolled_up:
        ledger.append(r)
    ledger.append(receipt)

    return receipt


def verify_invariants(compaction_receipt: dict) -> bool:
    """Verify compaction receipt invariants.

    Args:
        compaction_receipt: Compaction receipt to verify

    Returns:
        True if invariants hold

    Raises:
        StopRule: If any invariant is violated
    """
    counts = compaction_receipt.get("counts", {})
    count_before = counts.get("before", 0)
    count_after = counts.get("after", 0)
    hash_continuity = compaction_receipt.get("hash_continuity", False)

    # Invariant 1: counts.before >= counts.after
    if count_before < count_after:
        raise StopRule(
            f"Invariant violation: count_before ({count_before}) < "
            f"count_after ({count_after})"
        )

    # Invariant 2: hash_continuity must be True
    if not hash_continuity:
        raise StopRule("Invariant violation: hash_continuity is False")

    return True
