"""Receipt schema definitions and validation per CLAUDEME Section 4.

Constants:
    RECEIPT_SCHEMAS: Schema dicts keyed by receipt_type
    REQUIRED_FIELDS: Fields required in all receipts

Functions:
    validate_receipt: Validate receipt against schema
"""
from .receipt import StopRule


# Required fields for all receipt types
REQUIRED_FIELDS = ["receipt_type", "ts", "tenant_id", "payload_hash"]


# Schema definitions per CLAUDEME Section 4
RECEIPT_SCHEMAS = {
    "ingest": {
        "receipt_type": str,
        "ts": str,
        "tenant_id": str,
        "payload_hash": str,
        "redactions": list,
        "source_type": str,
    },
    "anchor": {
        "receipt_type": str,
        "ts": str,
        "tenant_id": str,
        "payload_hash": str,
        "merkle_root": str,
        "hash_algos": list,
        "batch_size": int,
        "proof_path": (str, type(None)),  # str or null
    },
    "compaction": {
        "receipt_type": str,
        "ts": str,
        "tenant_id": str,
        "payload_hash": str,
        "input_span": dict,  # {start, end}
        "output_span": dict,  # {start, end}
        "counts": dict,  # {before, after}
        "sums": dict,  # {before, after}
        "hash_continuity": bool,
    },
    "verify": {
        "receipt_type": str,
        "ts": str,
        "tenant_id": str,
        "payload_hash": str,
        "verified": bool,
        "proof_valid": bool,
    },
    "anomaly": {
        "receipt_type": str,
        "ts": str,
        "tenant_id": str,
        "payload_hash": str,
        "metric": str,
        "baseline": float,
        "delta": float,
        "classification": str,
        "action": str,
    },
}


def validate_receipt(receipt: dict) -> bool:
    """Validate receipt has required fields and matches schema.

    Args:
        receipt: Receipt dict to validate

    Returns:
        True if valid

    Raises:
        StopRule: If validation fails (missing field or unknown receipt_type)
    """
    if not isinstance(receipt, dict):
        raise StopRule("Receipt must be a dict")

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in receipt:
            raise StopRule(f"Missing required field: {field}")

    # Check receipt_type is known
    receipt_type = receipt["receipt_type"]
    if receipt_type not in RECEIPT_SCHEMAS:
        raise StopRule(f"Unknown receipt_type: {receipt_type}")

    return True
