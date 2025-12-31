#!/usr/bin/env python3
"""Standalone receipt bundle verification.

Verifies the Merkle root of receipt bundle without requiring ProofPack install.
Self-contained implementation of dual_hash and merkle.

Usage:
    python verify_standalone.py
"""
import hashlib
import json
from pathlib import Path

# Try to import blake3, fall back to sha256
try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False
    print("Note: blake3 not installed, using sha256 for both hashes")


def dual_hash(data: bytes | str) -> str:
    """Compute dual hash in format 'sha256hex:blake3hex'."""
    if isinstance(data, str):
        data = data.encode("utf-8")

    sha256_hex = hashlib.sha256(data).hexdigest()

    if HAS_BLAKE3:
        blake3_hex = blake3.blake3(data).hexdigest()
    else:
        blake3_hex = sha256_hex

    return f"{sha256_hex}:{blake3_hex}"


def merkle(items: list) -> str:
    """Compute Merkle root from list of items."""
    if not items:
        return dual_hash(b"empty")

    # Hash each item
    hashes = [dual_hash(json.dumps(item, sort_keys=True).encode("utf-8"))
              for item in items]

    # Pair-and-hash until single root
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = (hashes[i] + hashes[i + 1]).encode("utf-8")
            new_hashes.append(dual_hash(combined))
        hashes = new_hashes

    return hashes[0]


def main():
    """Verify receipt bundle integrity."""
    print("=== ProofPack Receipt Bundle Standalone Verifier ===")
    print("")

    # Find receipt and manifest files
    script_dir = Path(__file__).parent
    receipts_file = script_dir / "fraud_detection_v1.receipts.jsonl"
    manifest_file = script_dir / "MANIFEST.anchor"

    if not receipts_file.exists():
        print(f"ERROR: {receipts_file} not found")
        return 1

    if not manifest_file.exists():
        print(f"ERROR: {manifest_file} not found")
        return 1

    # Load receipts
    print(f"Loading receipts from {receipts_file.name}...")
    with open(receipts_file) as f:
        receipts = [json.loads(line) for line in f if line.strip()]
    print(f"  Loaded {len(receipts)} receipts")

    # Compute Merkle root
    print("\nComputing Merkle root...")
    computed_root = merkle(receipts)
    print(f"  Computed: {computed_root}")

    # Load manifest
    print(f"\nLoading manifest from {manifest_file.name}...")
    with open(manifest_file) as f:
        manifest = json.load(f)
    published_root = manifest["merkle_root"]
    print(f"  Published: {published_root}")

    # Verify
    print("\n" + "=" * 50)
    if computed_root == published_root:
        print("✓ VERIFIED: Merkle root matches!")
        print("  Receipt chain is authentic and untampered.")
        print("=" * 50)

        # Show performance
        print("\nClaimed Performance (from manifest):")
        perf = manifest.get("performance", {})
        print(f"  Recall:          {perf.get('recall', 0):.2%}")
        print(f"  Precision:       {perf.get('precision', 0):.2%}")
        print(f"  False Positives: {perf.get('false_positives', 0)}")

        print(f"\nReceipt count: {manifest.get('receipt_count', 'unknown')}")
        print(f"Bundle version: {manifest.get('bundle_version', 'unknown')}")

        return 0
    else:
        print("✗ FAILED: Merkle root mismatch!")
        print("  Receipt chain may have been tampered.")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    exit(main())
