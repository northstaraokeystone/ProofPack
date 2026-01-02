"""Parse QED run manifests and link to stored receipts.

Validates manifest integrity and detects discrepancies during bridging.
The bridge acts as first-line anomaly detector - proving data consistency
before downstream processing.
"""
import json
from collections.abc import Callable
from pathlib import Path

from ..core.receipt import StopRule, dual_hash, emit_receipt
from .hooks import get_tenant_id, validate_hook

# Required fields in QED manifest
REQUIRED_MANIFEST_FIELDS = {
    "window_counts",
    "avg_compression",
    "estimated_savings",
    "dataset_checksum",
    "hook",
    "run_id",
    "ts",
}

# Critical discrepancy threshold for window count mismatch (1%)
WINDOW_COUNT_MISMATCH_THRESHOLD = 0.01


def stoprule_manifest_parse_failure(e: Exception, path: str) -> None:
    """Emit anomaly receipt and raise StopRule for manifest parse failure.

    Args:
        e: The exception that caused the failure
        path: Path to the manifest file

    Raises:
        StopRule: Always raised after emitting anomaly receipt
    """
    emit_receipt("anomaly", {
        "tenant_id": "system",
        "metric": "manifest_parse",
        "baseline": None,
        "delta": None,
        "classification": "degradation",
        "action": "halt",
        "error": str(e),
        "path": path,
    })
    raise StopRule(f"Manifest parse failure at {path}: {e}")


def stoprule_integrity_violation(
    discrepancies: list[dict], tenant_id: str, manifest_hash: str
) -> None:
    """Emit anomaly receipt and raise StopRule for critical integrity violation.

    Args:
        discrepancies: List of discrepancy dicts
        tenant_id: Tenant ID for the receipt
        manifest_hash: Hash of the manifest with the violation

    Raises:
        StopRule: Always raised after emitting anomaly receipt
    """
    emit_receipt("anomaly", {
        "tenant_id": tenant_id,
        "metric": "manifest_integrity",
        "baseline": None,
        "delta": None,
        "classification": "violation",
        "action": "halt",
        "manifest_hash": manifest_hash,
        "discrepancies": discrepancies,
    })
    raise StopRule(
        f"Critical integrity violation in manifest {manifest_hash}: {discrepancies}"
    )


def parse_manifest(manifest_path: str) -> dict:
    """Parse QED run manifest and emit receipt.

    1. Read and parse JSON file
    2. Validate required fields
    3. Compute manifest_hash = dual_hash(file_contents)
    4. Emit qed_manifest_receipt
    5. Return parsed manifest with manifest_hash added

    Args:
        manifest_path: Path to qed_run_manifest.json

    Returns:
        Parsed manifest dict with manifest_hash added

    Raises:
        StopRule: If manifest cannot be parsed or missing required fields
    """
    path = Path(manifest_path)

    try:
        # Read raw file contents for hashing
        file_contents = path.read_text(encoding="utf-8")

        # Parse JSON
        manifest = json.loads(file_contents)

        # Validate required fields
        missing_fields = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {sorted(missing_fields)}")

        # Validate hook
        hook = manifest["hook"]
        validate_hook(hook)
        tenant_id = get_tenant_id(hook)

        # Compute manifest hash
        manifest_hash = dual_hash(file_contents)

        # Add manifest_hash to manifest
        manifest["manifest_hash"] = manifest_hash

        # Emit qed_manifest_receipt
        emit_receipt("qed_manifest", {
            "tenant_id": tenant_id,
            "hook": hook,
            "run_id": manifest["run_id"],
            "manifest_hash": manifest_hash,
            "window_counts": manifest["window_counts"],
            "avg_compression": manifest["avg_compression"],
            "estimated_savings": manifest["estimated_savings"],
            "dataset_checksum": manifest["dataset_checksum"],
        })

        return manifest

    except StopRule:
        # Re-raise StopRule without wrapping
        raise
    except Exception as e:
        stoprule_manifest_parse_failure(e, manifest_path)
        # Never reached, but satisfies type checker
        raise


def link_to_receipts(
    manifest: dict, ledger_query_fn: Callable[[str, str | None], list[dict]]
) -> list[dict]:
    """Link manifest to stored receipts via ledger query.

    1. Extract hook and time range from manifest
    2. Query ledger for qed_window_receipts matching hook and time range
    3. Build linkage map: [{manifest_entry, receipt_id, match_confidence}]
    4. Emit qed_linkage_receipt with coverage stats
    5. Return linkage list

    Args:
        manifest: Parsed manifest dict (from parse_manifest)
        ledger_query_fn: Function to query ledger receipts
            Signature: (receipt_type, tenant_id) -> list[dict]

    Returns:
        List of linkage dicts with manifest_entry, receipt_id, match_confidence
    """
    hook = manifest["hook"]
    tenant_id = get_tenant_id(hook)
    manifest_hash = manifest["manifest_hash"]
    expected_count = manifest["window_counts"]

    # Query ledger for qed_window receipts with matching tenant
    receipts = ledger_query_fn("qed_window", tenant_id)

    # Build linkage map
    linkages = []
    for i, receipt in enumerate(receipts):
        linkages.append({
            "manifest_entry": i,
            "receipt_id": receipt.get("payload_hash", ""),
            "match_confidence": 1.0,  # Direct match
        })

    # Compute coverage
    receipts_linked = len(linkages)
    coverage_ratio = receipts_linked / expected_count if expected_count > 0 else 0.0

    # Identify gaps (if fewer receipts than expected)
    gaps = []
    if receipts_linked < expected_count:
        gaps.append(f"Missing {expected_count - receipts_linked} receipts")

    # Emit qed_linkage_receipt
    emit_receipt("qed_linkage", {
        "tenant_id": tenant_id,
        "manifest_hash": manifest_hash,
        "receipts_linked": receipts_linked,
        "receipts_expected": expected_count,
        "coverage_ratio": coverage_ratio,
        "gaps": gaps,
    })

    return linkages


def validate_manifest_integrity(manifest: dict, receipts: list[dict]) -> dict:
    """Validate manifest claims against actual receipts.

    1. Compare manifest.window_counts with len(receipts)
    2. Recompute avg_compression from receipts
    3. Flag discrepancies
    4. Emit qed_integrity_receipt with pass/fail and discrepancies
    5. If critical discrepancy, call stoprule
    6. Return integrity dict

    Args:
        manifest: Parsed manifest dict
        receipts: List of linked receipts

    Returns:
        Integrity check result dict with status, discrepancies

    Raises:
        StopRule: If critical discrepancy detected (> 1% count mismatch)
    """
    hook = manifest["hook"]
    tenant_id = get_tenant_id(hook)
    manifest_hash = manifest["manifest_hash"]

    discrepancies = []

    # Check window counts
    manifest_count = manifest["window_counts"]
    actual_count = len(receipts)
    if manifest_count != actual_count:
        discrepancies.append({
            "field": "window_counts",
            "manifest_value": manifest_count,
            "computed_value": actual_count,
        })

    # Check average compression
    manifest_avg_compression = manifest["avg_compression"]
    if receipts:
        actual_avg_compression = sum(
            r.get("compression_ratio", 1.0) for r in receipts
        ) / len(receipts)
    else:
        actual_avg_compression = 0.0

    # Allow 1% tolerance for compression average
    if abs(manifest_avg_compression - actual_avg_compression) > manifest_avg_compression * 0.01:
        discrepancies.append({
            "field": "avg_compression",
            "manifest_value": manifest_avg_compression,
            "computed_value": actual_avg_compression,
        })

    # Determine status
    status = "pass" if not discrepancies else "fail"

    # Emit qed_integrity_receipt
    emit_receipt("qed_integrity", {
        "tenant_id": tenant_id,
        "manifest_hash": manifest_hash,
        "status": status,
        "discrepancies": discrepancies,
    })

    # Check for critical discrepancy (window count mismatch > 1%)
    if manifest_count > 0:
        count_mismatch_ratio = abs(manifest_count - actual_count) / manifest_count
        if count_mismatch_ratio > WINDOW_COUNT_MISMATCH_THRESHOLD:
            stoprule_integrity_violation(discrepancies, tenant_id, manifest_hash)

    return {
        "status": status,
        "discrepancies": discrepancies,
        "manifest_hash": manifest_hash,
        "tenant_id": tenant_id,
    }
