"""Shared primitives for ledger operations."""
import hashlib
import json
import time

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False


class StopRule(Exception):
    """Exception raised when a stoprule is triggered."""
    pass


def dual_hash(data: bytes | str | dict) -> str:
    """Compute SHA256:BLAKE3 hash, fallback to SHA256:SHA256 if blake3 unavailable."""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True, separators=(",", ":"))
    if isinstance(data, str):
        data = data.encode("utf-8")

    sha256_hash = hashlib.sha256(data).hexdigest()

    if HAS_BLAKE3:
        blake3_hash = blake3.blake3(data).hexdigest()
    else:
        blake3_hash = hashlib.sha256(data).hexdigest()

    return f"{sha256_hash}:{blake3_hash}"


def emit_receipt(receipt_type: str, data: dict, tenant_id: str = "default") -> dict:
    """Emit a receipt with standard fields, print to stdout."""
    receipt = {
        "receipt_type": receipt_type,
        "ts": time.time(),
        "tenant_id": tenant_id,
        "payload_hash": dual_hash(data),
        **data
    }
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return receipt


def merkle(items: list) -> str:
    """Compute Merkle root using dual-hash. Handle empty list and odd counts."""
    if not items:
        return dual_hash(b"")

    hashes = [dual_hash(item) for item in items]

    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            new_hashes.append(dual_hash(combined))
        hashes = new_hashes

    return hashes[0]
