"""Core receipt primitives required in every ProofPack module per CLAUDEME Section 8.

Functions:
    dual_hash: SHA256:BLAKE3 dual-hash format
    emit_receipt: Emit receipt with required fields to stdout
    merkle: Compute Merkle root from item list
    StopRule: Exception for stoprule triggers
"""
import hashlib
import json
from datetime import datetime, timezone

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False


class StopRule(Exception):
    """Raised when stoprule triggers. Never catch silently."""
    pass


def dual_hash(data: bytes | str | dict) -> str:
    """Compute dual hash in format 'sha256hex:blake3hex'.

    If blake3 unavailable, returns 'sha256hex:sha256hex'.
    Pure function with no side effects.

    Args:
        data: Bytes, string, or dict to hash

    Returns:
        String in format 'sha256hex:blake3hex' (both 64 hex chars)
    """
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True, separators=(",", ":"))
    if isinstance(data, str):
        data = data.encode("utf-8")

    sha256_hex = hashlib.sha256(data).hexdigest()

    if HAS_BLAKE3:
        blake3_hex = blake3.blake3(data).hexdigest()
    else:
        blake3_hex = sha256_hex

    return f"{sha256_hex}:{blake3_hex}"


def emit_receipt(receipt_type: str, data: dict, tenant_id: str = "default") -> dict:
    """Emit a receipt with standard required fields.

    Prints JSON to stdout with flush=True.

    Args:
        receipt_type: Type of receipt (ingest, anchor, compaction, verify, anomaly)
        data: Receipt payload data
        tenant_id: Tenant identifier (default: "default")

    Returns:
        Complete receipt dict with receipt_type, ts, tenant_id, payload_hash
    """
    # Get tenant_id from data or use parameter
    tenant_id = data.get("tenant_id", tenant_id)

    # Compute payload_hash from JSON-serialized data with sorted keys
    payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    payload_hash = dual_hash(payload_bytes)

    # Build receipt with required fields
    receipt = {
        "receipt_type": receipt_type,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant_id": tenant_id,
        "payload_hash": payload_hash,
        **data
    }

    # Print to stdout with flush
    print(json.dumps(receipt, sort_keys=True), flush=True)

    return receipt


def merkle(items: list) -> str:
    """Compute Merkle root from list of items.

    - Empty list: return dual_hash(b"empty")
    - Hash each item: dual_hash(json.dumps(item, sort_keys=True))
    - Odd count: duplicate last hash
    - Pairwise combine until single root

    Args:
        items: List of items (dicts) to compute root for

    Returns:
        Merkle root as dual-hash string
    """
    if not items:
        return dual_hash(b"empty")

    # Hash each item
    hashes = [dual_hash(json.dumps(item, sort_keys=True).encode("utf-8"))
              for item in items]

    # Pair-and-hash until single root
    while len(hashes) > 1:
        # Duplicate last if odd count
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        # Combine pairs
        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = (hashes[i] + hashes[i + 1]).encode("utf-8")
            new_hashes.append(dual_hash(combined))
        hashes = new_hashes

    return hashes[0]
