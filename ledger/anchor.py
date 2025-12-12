"""Merkle batching for tamper-proof receipt anchoring."""
from .core import dual_hash, emit_receipt, merkle, StopRule

ANCHOR_SCHEMA = {
    "receipt_type": "anchor_receipt",
    "required": ["receipt_type", "ts", "tenant_id", "payload_hash", "merkle_root", "hash_algos", "batch_size", "leaf_hashes"],
    "properties": {
        "receipt_type": {"type": "string", "const": "anchor_receipt"},
        "ts": {"type": "number"},
        "tenant_id": {"type": "string"},
        "payload_hash": {"type": "string"},
        "merkle_root": {"type": "string"},
        "hash_algos": {"type": "array", "items": {"type": "string"}},
        "batch_size": {"type": "integer"},
        "leaf_hashes": {"type": "array", "items": {"type": "string"}}
    }
}


def stoprule_anchor_mismatch(expected: str, actual: str, tenant_id: str = "default") -> None:
    """Emit anomaly receipt then raise StopRule on merkle mismatch."""
    emit_receipt("anomaly_receipt", {
        "anomaly_type": "anchor_mismatch",
        "expected": expected,
        "actual": actual,
        "stage": "anchor"
    }, tenant_id)
    raise StopRule(f"Anchor mismatch: expected {expected}, got {actual}")


def anchor(receipts: list, tenant_id: str = "default") -> dict:
    """Group receipts into tamper-proof Merkle batch. SLO: ≤1s per 1000 receipts."""
    try:
        leaf_hashes = [dual_hash(r) for r in receipts]
        merkle_root = merkle(receipts)

        return emit_receipt("anchor_receipt", {
            "merkle_root": merkle_root,
            "hash_algos": ["SHA256", "BLAKE3"],
            "batch_size": len(receipts),
            "leaf_hashes": leaf_hashes
        }, tenant_id)

    except StopRule:
        raise
    except Exception as e:
        emit_receipt("anomaly_receipt", {
            "anomaly_type": "anchor_failure",
            "error": str(e),
            "stage": "anchor"
        }, tenant_id)
        raise StopRule(f"Anchor stoprule triggered: {e}")
