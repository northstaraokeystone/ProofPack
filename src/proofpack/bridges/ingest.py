"""Transform QED window output to ProofPack receipts.

Ingests QED compressed windows and batches into the ledger with anchor support.
SLO: Single window ingest <= 50ms p95, Batch of 100 windows <= 1s p95.
"""
import json

from ..core.receipt import StopRule, dual_hash, emit_receipt
from ..ledger import anchor_batch as ledger_anchor_batch
from ..ledger import ingest as ledger_ingest
from .hooks import get_tenant_id, validate_hook

# QED version constant
QED_VERSION = "7.0"

# Safety recall threshold - non-negotiable per QED Build Strategy v7
SAFETY_RECALL_THRESHOLD = 0.999


def stoprule_ingest_failure(e: Exception) -> None:
    """Emit anomaly receipt and raise StopRule for ingest failure.

    Args:
        e: The exception that caused the failure

    Raises:
        StopRule: Always raised after emitting anomaly receipt
    """
    emit_receipt("anomaly", {
        "tenant_id": "system",
        "metric": "qed_ingest",
        "baseline": None,
        "delta": None,
        "classification": "degradation",
        "action": "halt",
        "error": str(e),
    })
    raise StopRule(f"QED ingest failure: {e}")


def stoprule_recall_violation(score: float, tenant_id: str, window_hash: str) -> None:
    """Emit anomaly receipt and raise StopRule for recall violation.

    Triggered when recall_score < 0.999 for safety-critical window.

    Args:
        score: The actual recall score
        tenant_id: Tenant ID for the receipt
        window_hash: Hash of the window with the violation

    Raises:
        StopRule: Always raised after emitting anomaly receipt
    """
    emit_receipt("anomaly", {
        "tenant_id": tenant_id,
        "metric": "recall_score",
        "baseline": SAFETY_RECALL_THRESHOLD,
        "delta": SAFETY_RECALL_THRESHOLD - score,
        "classification": "violation",
        "action": "escalate",
        "window_hash": window_hash,
        "actual_score": score,
    })
    raise StopRule(
        f"Recall score {score} below safety threshold {SAFETY_RECALL_THRESHOLD}"
    )


def extract_window_metrics(window: dict) -> dict:
    """Extract and normalize metrics from raw QED window.

    Pure function with no side effects.

    Args:
        window: Raw QED window dict

    Returns:
        Normalized metrics dict with compression_ratio, recall_score,
        safety_events, classification
    """
    return {
        "compression_ratio": window.get("compression_ratio", 1.0),
        "recall_score": window.get("score", window.get("recall_score", 0.999)),
        "safety_events": window.get("safety_events", 0),
        "classification": window.get("classification", "normal"),
    }


def ingest_qed_output(window: dict, hook: str) -> dict:
    """Transform single QED window to ProofPack receipt and ingest to ledger.

    1. Validate hook via validate_hook()
    2. Get tenant_id via get_tenant_id()
    3. Compute window_hash = dual_hash(json.dumps(window, sort_keys=True))
    4. Extract metrics from window
    5. Emit qed_window_receipt
    6. Call ledger_ingest() with receipt payload and tenant_id
    7. Return receipt

    SLO: <= 50ms p95

    Args:
        window: QED compressed window dict
        hook: Hook name (tesla, spacex, etc.)

    Returns:
        qed_window_receipt dict

    Raises:
        StopRule: If hook invalid, ingest fails, or recall < 0.999 for safety
    """
    try:
        # 1. Validate hook (raises StopRule if invalid)
        validate_hook(hook)

        # 2. Get tenant_id
        tenant_id = get_tenant_id(hook)

        # 3. Compute window hash
        window_json = json.dumps(window, sort_keys=True)
        window_hash = dual_hash(window_json)

        # 4. Extract metrics
        metrics = extract_window_metrics(window)

        # 5. Check recall threshold for safety-critical windows
        if metrics["safety_events"] > 0 and metrics["recall_score"] < SAFETY_RECALL_THRESHOLD:
            stoprule_recall_violation(
                metrics["recall_score"], tenant_id, window_hash
            )

        # 6. Emit qed_window_receipt
        receipt = emit_receipt("qed_window", {
            "tenant_id": tenant_id,
            "hook": hook,
            "window_hash": window_hash,
            "compression_ratio": metrics["compression_ratio"],
            "recall_score": metrics["recall_score"],
            "safety_events": metrics["safety_events"],
            "qed_version": QED_VERSION,
        })

        # 7. Ingest to ledger
        ledger_ingest(
            payload=window_json.encode("utf-8"),
            tenant_id=tenant_id,
            source_type="qed_window",
        )

        return receipt

    except StopRule:
        # Re-raise StopRule without wrapping
        raise
    except Exception as e:
        stoprule_ingest_failure(e)
        # Never reached, but satisfies type checker
        raise


def batch_windows(windows: list[dict], hook: str) -> dict:
    """Batch ingest QED windows with Merkle anchoring.

    1. Validate hook once
    2. For each window: call ingest_qed_output(), collect receipts
    3. Call anchor_batch(receipts) to get merkle anchor
    4. Emit qed_batch_receipt with batch_size, merkle_root, hook
    5. Return qed_batch_receipt

    SLO: Batch of 100 windows <= 1s p95

    Args:
        windows: List of QED window dicts
        hook: Hook name for all windows in batch

    Returns:
        qed_batch_receipt dict

    Raises:
        StopRule: If hook invalid, any window fails, or anchor fails
    """
    try:
        # 1. Validate hook once (raises StopRule if invalid)
        validate_hook(hook)
        tenant_id = get_tenant_id(hook)

        # 2. Ingest each window and collect receipts
        receipts = []
        window_hashes = []
        total_safety_events = 0
        total_compression = 0.0

        for window in windows:
            receipt = ingest_qed_output(window, hook)
            receipts.append(receipt)
            window_hashes.append(receipt["window_hash"])
            total_safety_events += receipt.get("safety_events", 0)
            total_compression += receipt.get("compression_ratio", 1.0)

        # 3. Anchor the batch
        anchor_receipt = ledger_anchor_batch(receipts, tenant_id)
        merkle_root = anchor_receipt["merkle_root"]

        # 4. Compute average compression
        avg_compression = total_compression / len(windows) if windows else 1.0

        # 5. Emit qed_batch_receipt
        batch_receipt = emit_receipt("qed_batch", {
            "tenant_id": tenant_id,
            "hook": hook,
            "batch_size": len(windows),
            "merkle_root": merkle_root,
            "window_hashes": window_hashes,
            "total_safety_events": total_safety_events,
            "avg_compression_ratio": avg_compression,
        })

        return batch_receipt

    except StopRule:
        # Re-raise StopRule without wrapping
        raise
    except Exception as e:
        stoprule_ingest_failure(e)
        # Never reached, but satisfies type checker
        raise
