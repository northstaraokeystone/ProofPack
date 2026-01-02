"""Reconnection handling and conflict resolution.

Manages the transition from offline to online state,
detecting and resolving conflicts when local receipts
may conflict with main ledger state.
"""

from proofpack.core.receipt import emit_receipt
from proofpack.offline.queue import get_all_queued, get_sync_status
from proofpack.offline.sync import full_sync, is_connected


class ConflictType:
    """Types of conflicts that can occur during reconnection."""
    SEQUENCE_GAP = "sequence_gap"  # Missing sequence IDs
    DUPLICATE = "duplicate"  # Receipt already in ledger
    MERKLE_MISMATCH = "merkle_mismatch"  # Local vs remote Merkle differs
    TIMESTAMP_CONFLICT = "timestamp_conflict"  # Ordering issues


def handle_reconnection(
    tenant_id: str = "default",
    auto_resolve: bool = False
) -> dict:
    """Handle transition from offline to online.

    Args:
        tenant_id: Tenant reconnecting
        auto_resolve: Whether to auto-resolve conflicts

    Returns:
        Reconnection status including conflicts if any
    """
    # Check if we're actually connected now
    if not is_connected():
        return {
            "status": "still_offline",
            "connected": False,
        }

    status = get_sync_status()
    pending = status.get("pending_count", 0)

    if pending == 0:
        emit_receipt("reconnection", {
            "tenant_id": tenant_id,
            "status": "clean_reconnect",
            "pending_count": 0,
        })
        return {
            "status": "clean_reconnect",
            "connected": True,
            "pending_count": 0,
        }

    # Check for conflicts before sync
    conflicts = detect_conflicts(tenant_id)

    if conflicts:
        if auto_resolve:
            resolve_conflicts(conflicts, tenant_id)
        else:
            emit_receipt("reconnection", {
                "tenant_id": tenant_id,
                "status": "conflicts_detected",
                "conflict_count": len(conflicts),
                "conflicts": [c["type"] for c in conflicts],
            })
            return {
                "status": "conflicts_detected",
                "connected": True,
                "conflicts": conflicts,
                "requires_resolution": True,
            }

    # Perform sync
    sync_result = full_sync(tenant_id)

    emit_receipt("reconnection", {
        "tenant_id": tenant_id,
        "status": "synced",
        "synced_count": sync_result.get("synced_count", 0),
        "batch_id": sync_result.get("batch_id"),
    })

    return {
        "status": "synced",
        "connected": True,
        **sync_result,
    }


def detect_conflicts(tenant_id: str = "default") -> list[dict]:
    """Detect conflicts between local queue and main ledger.

    Args:
        tenant_id: Tenant to check

    Returns:
        List of conflict descriptors
    """
    conflicts = []
    receipts = get_all_queued()

    if not receipts:
        return []

    # Check for sequence gaps
    sequences = [
        r.get("offline_metadata", {}).get("local_sequence_id", 0)
        for r in receipts
    ]
    if sequences:
        sequences.sort()
        for i in range(1, len(sequences)):
            if sequences[i] - sequences[i-1] > 1:
                conflicts.append({
                    "type": ConflictType.SEQUENCE_GAP,
                    "expected": sequences[i-1] + 1,
                    "actual": sequences[i],
                    "severity": "warning",
                })

    # In production, would check against ledger for duplicates
    # For scaffold, we just detect structural issues

    # Check for timestamp ordering issues
    timestamps = []
    for r in receipts:
        ts = r.get("ts")
        if ts:
            timestamps.append((ts, r.get("offline_metadata", {}).get("local_sequence_id", 0)))

    timestamps.sort(key=lambda x: x[0])
    for i in range(1, len(timestamps)):
        if timestamps[i][1] < timestamps[i-1][1]:
            # Timestamp order doesn't match sequence order
            conflicts.append({
                "type": ConflictType.TIMESTAMP_CONFLICT,
                "ts1": timestamps[i-1][0],
                "seq1": timestamps[i-1][1],
                "ts2": timestamps[i][0],
                "seq2": timestamps[i][1],
                "severity": "info",
            })

    return conflicts


def resolve_conflicts(
    conflicts: list[dict],
    tenant_id: str = "default"
) -> dict:
    """Resolve detected conflicts.

    Args:
        conflicts: List of conflict descriptors
        tenant_id: Tenant resolving conflicts

    Returns:
        Resolution status
    """
    resolutions = []

    for conflict in conflicts:
        conflict_type = conflict.get("type")

        if conflict_type == ConflictType.SEQUENCE_GAP:
            # Sequence gaps are usually benign - just note them
            resolutions.append({
                "conflict": conflict_type,
                "action": "noted",
                "reason": "sequence gaps acceptable for offline mode",
            })

        elif conflict_type == ConflictType.DUPLICATE:
            # Skip duplicates during sync
            resolutions.append({
                "conflict": conflict_type,
                "action": "skip_duplicates",
                "reason": "receipt already in ledger",
            })

        elif conflict_type == ConflictType.MERKLE_MISMATCH:
            # Merkle mismatch requires investigation
            resolutions.append({
                "conflict": conflict_type,
                "action": "flagged_for_review",
                "reason": "merkle integrity check failed",
            })

        elif conflict_type == ConflictType.TIMESTAMP_CONFLICT:
            # Timestamp conflicts are informational
            resolutions.append({
                "conflict": conflict_type,
                "action": "noted",
                "reason": "timestamp ordering differs from sequence",
            })

    emit_receipt("conflict_resolution", {
        "tenant_id": tenant_id,
        "conflict_count": len(conflicts),
        "resolution_count": len(resolutions),
        "resolutions": resolutions,
    })

    return {
        "resolved": True,
        "conflict_count": len(conflicts),
        "resolutions": resolutions,
    }


def get_conflict_status(tenant_id: str = "default") -> dict:
    """Get current conflict status.

    Args:
        tenant_id: Tenant to check

    Returns:
        Status dict with any pending conflicts
    """
    conflicts = detect_conflicts(tenant_id)

    return {
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "pending_count": get_sync_status().get("pending_count", 0),
    }
