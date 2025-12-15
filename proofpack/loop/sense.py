"""Sense Module - Query receipt stream for L0-L3 receipts.

The sense phase queries all receipt levels from the last interval,
categorizing them by level for downstream analysis.
"""

import time
from datetime import datetime, timezone
from typing import Callable

from proofpack.core.receipt import emit_receipt

# Receipt level mapping (imported from __init__ to avoid circular)
RECEIPT_LEVEL_MAP = {
    # L0 - Telemetry
    "qed_window": 0,
    "qed_manifest": 0,
    "qed_batch": 0,
    "ingest": 0,
    # L1 - Agents
    "anomaly": 1,
    "alert": 1,
    "remediation": 1,
    "pattern_match": 1,
    "analysis": 1,
    "actuation": 1,
    # L2 - Decisions
    "brief": 2,
    "packet": 2,
    "attach": 2,
    "consistency": 2,
    # L3 - Quality
    "health": 3,
    "effectiveness": 3,
    "wound": 3,
    "gap": 3,
    "harvest": 3,
    # L4 - Meta (not queried in sense, emitted by loop)
    "loop_cycle": 4,
    "completeness": 4,
    "helper_blueprint": 4,
    "approval": 4,
    "sense": 4,
}


def sense(
    ledger_query_fn: Callable,
    tenant_id: str,
    since_ms: int = 60000,
) -> dict:
    """Query all receipt levels from the last interval.

    Args:
        ledger_query_fn: Function to query receipts
            Signature: (tenant_id: str, since: str) -> list[dict]
        tenant_id: Tenant identifier
        since_ms: Time window in milliseconds (default 60000 = 60s)

    Returns:
        Dict with categorized receipts by level:
        {
            "L0": [...],  # Telemetry receipts
            "L1": [...],  # Agent receipts
            "L2": [...],  # Decision receipts
            "L3": [...],  # Quality receipts
            "window_start": "ISO8601",
            "window_end": "ISO8601",
            "duration_ms": int
        }
    """
    start_time = time.perf_counter()

    # Calculate time window
    now = datetime.now(timezone.utc)
    window_end = now.isoformat().replace("+00:00", "Z")

    # Calculate window start (now - since_ms)
    since_dt = datetime.fromtimestamp(
        now.timestamp() - (since_ms / 1000), timezone.utc
    )
    window_start = since_dt.isoformat().replace("+00:00", "Z")

    # Query receipts
    receipts = query_l0_l3(ledger_query_fn, window_start, tenant_id)

    # Categorize by level
    result = {
        "L0": query_by_level(receipts, 0),
        "L1": query_by_level(receipts, 1),
        "L2": query_by_level(receipts, 2),
        "L3": query_by_level(receipts, 3),
        "window_start": window_start,
        "window_end": window_end,
        "all_receipts": receipts,
    }

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    result["duration_ms"] = duration_ms

    # Emit sense receipt
    emit_receipt(
        "sense",
        {
            "tenant_id": tenant_id,
            "window_start": window_start,
            "window_end": window_end,
            "counts": {
                "L0": len(result["L0"]),
                "L1": len(result["L1"]),
                "L2": len(result["L2"]),
                "L3": len(result["L3"]),
            },
            "duration_ms": duration_ms,
        },
    )

    return result


def query_l0_l3(
    ledger_query_fn: Callable,
    since: str,
    tenant_id: str,
) -> list:
    """Query L0-L3 receipts since timestamp.

    Args:
        ledger_query_fn: Function to query receipts
        since: ISO8601 timestamp for window start
        tenant_id: Tenant identifier

    Returns:
        List of receipts from L0-L3 (excludes L4 meta receipts)
    """
    # Query all receipts since timestamp
    all_receipts = ledger_query_fn(tenant_id=tenant_id, since=since)

    # Filter to L0-L3 only (exclude L4 meta receipts)
    l0_l3_receipts = []
    for receipt in all_receipts:
        receipt_type = receipt.get("receipt_type", "unknown")
        level = RECEIPT_LEVEL_MAP.get(receipt_type, -1)
        if 0 <= level <= 3:
            l0_l3_receipts.append(receipt)

    return l0_l3_receipts


def query_by_level(receipts: list, level: int) -> list:
    """Filter receipts by level (0-3).

    Args:
        receipts: List of receipt dicts
        level: Level to filter by (0-3)

    Returns:
        List of receipts matching the specified level
    """
    result = []
    for receipt in receipts:
        receipt_type = receipt.get("receipt_type", "unknown")
        receipt_level = RECEIPT_LEVEL_MAP.get(receipt_type, -1)
        if receipt_level == level:
            result.append(receipt)
    return result


def get_level(receipt_type: str) -> int:
    """Get the level for a receipt type.

    Args:
        receipt_type: Type of receipt

    Returns:
        Level (0-4) or -1 if unknown
    """
    return RECEIPT_LEVEL_MAP.get(receipt_type, -1)
