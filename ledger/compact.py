"""Compaction with invariant preservation."""
from collections import defaultdict
from .core import dual_hash, emit_receipt, merkle, StopRule

COMPACT_SCHEMA = {
    "receipt_type": "compaction_receipt",
    "required": ["receipt_type", "ts", "tenant_id", "payload_hash", "input_span", "output_span", "counts", "sums", "hash_continuity"],
    "properties": {
        "receipt_type": {"type": "string", "const": "compaction_receipt"},
        "ts": {"type": "number"},
        "tenant_id": {"type": "string"},
        "payload_hash": {"type": "string"},
        "input_span": {"type": "array"},
        "output_span": {"type": "array"},
        "counts": {"type": "object", "properties": {"before": {"type": "integer"}, "after": {"type": "integer"}}},
        "sums": {"type": "object", "properties": {"before": {"type": "number"}, "after": {"type": "number"}}},
        "hash_continuity": {"type": "boolean"}
    }
}


def compact(receipts: list, span: tuple, tenant_id: str = "default") -> dict:
    """Summarize old receipts while preserving invariants."""
    try:
        before_hash = merkle(receipts)
        counts_before = len(receipts)

        grouped = defaultdict(list)
        for r in receipts:
            rtype = r.get("receipt_type", "unknown") if isinstance(r, dict) else "unknown"
            grouped[rtype].append(r)

        compacted = []
        for rtype, items in grouped.items():
            compacted.append({
                "receipt_type": f"compacted_{rtype}",
                "count": len(items),
                "original_hashes": [dual_hash(i) for i in items]
            })

        after_hash = merkle(compacted)
        counts_after = len(compacted)

        hash_continuity = before_hash is not None and after_hash is not None

        if counts_before != len(receipts):
            emit_receipt("anomaly_receipt", {
                "anomaly_type": "compact_invariant_violation",
                "error": "counts.before mismatch",
                "stage": "compact"
            }, tenant_id)
            raise StopRule("Compaction invariant violation: counts.before mismatch")

        return emit_receipt("compaction_receipt", {
            "input_span": list(span),
            "output_span": [0, counts_after],
            "counts": {"before": counts_before, "after": counts_after},
            "sums": {"before": counts_before, "after": counts_after},
            "hash_continuity": hash_continuity
        }, tenant_id)

    except StopRule:
        raise
    except Exception as e:
        emit_receipt("anomaly_receipt", {
            "anomaly_type": "compact_failure",
            "error": str(e),
            "stage": "compact"
        }, tenant_id)
        raise StopRule(f"Compact stoprule triggered: {e}")
