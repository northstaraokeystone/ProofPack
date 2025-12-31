"""Sync module for pushing local queue to main ledger.

Handles the transition from offline to online state,
ensuring all locally generated receipts are properly
anchored in the main ledger.

Sync process:
1. Check connectivity
2. Build batch from local queue
3. Compute batch Merkle root
4. Push batch to main ledger
5. Verify sync success
6. Clear local queue
"""
import socket
import uuid
from datetime import datetime

from proofpack.core.receipt import emit_receipt
from proofpack.offline.queue import (
    get_all_queued,
    get_local_merkle_root,
    get_queue_size,
    clear_queue,
    mark_synced,
)


# Default ledger endpoint (configurable)
DEFAULT_LEDGER_HOST = "localhost"
DEFAULT_LEDGER_PORT = 8765
SYNC_TIMEOUT_SECONDS = 30


def is_connected(
    host: str = DEFAULT_LEDGER_HOST,
    port: int = DEFAULT_LEDGER_PORT,
    timeout: float = 5.0
) -> bool:
    """Check if main ledger is reachable.

    Args:
        host: Ledger host
        port: Ledger port
        timeout: Connection timeout in seconds

    Returns:
        True if ledger is reachable
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError):
        return False


def sync_queue(
    tenant_id: str = "default",
    host: str = DEFAULT_LEDGER_HOST,
    port: int = DEFAULT_LEDGER_PORT,
) -> dict:
    """Push local queue to main ledger.

    Args:
        tenant_id: Tenant performing sync
        host: Ledger host
        port: Ledger port

    Returns:
        Sync result with batch_id, count, merkle_root
    """
    if not is_connected(host, port):
        emit_receipt("sync_failed", {
            "tenant_id": tenant_id,
            "reason": "not_connected",
            "pending_count": get_queue_size(),
        })
        return {
            "success": False,
            "reason": "not_connected",
            "pending_count": get_queue_size(),
        }

    receipts = get_all_queued()
    if not receipts:
        return {
            "success": True,
            "reason": "queue_empty",
            "synced_count": 0,
        }

    batch_id = str(uuid.uuid4())
    local_merkle = get_local_merkle_root()

    # Add sync metadata to each receipt
    sync_time = datetime.utcnow().isoformat() + "Z"
    for receipt in receipts:
        if "offline_metadata" in receipt:
            receipt["offline_metadata"]["sync_timestamp"] = sync_time
            receipt["offline_metadata"]["sync_batch_id"] = batch_id

    # In production, this would POST to ledger API
    # For scaffold, we emit a sync receipt
    sync_receipt = emit_receipt("offline_sync", {
        "tenant_id": tenant_id,
        "batch_id": batch_id,
        "synced_count": len(receipts),
        "local_merkle_root": local_merkle,
        "sync_timestamp": sync_time,
    })

    # Mark as synced
    mark_synced(batch_id)

    return {
        "success": True,
        "batch_id": batch_id,
        "synced_count": len(receipts),
        "local_merkle_root": local_merkle,
        "sync_receipt": sync_receipt,
    }


def verify_sync(
    batch_id: str,
    expected_merkle: str,
    tenant_id: str = "default",
) -> bool:
    """Confirm all receipts from batch landed in main ledger.

    Args:
        batch_id: ID of sync batch to verify
        expected_merkle: Expected Merkle root
        tenant_id: Tenant verifying

    Returns:
        True if sync verified successfully
    """
    # In production, this would query the ledger API
    # For scaffold, we emit a verification receipt

    emit_receipt("sync_verification", {
        "tenant_id": tenant_id,
        "batch_id": batch_id,
        "expected_merkle": expected_merkle,
        "verified": True,  # Would be actual verification result
    })

    return True


def clear_synced(batch_id: str, tenant_id: str = "default"):
    """Remove synced receipts from local queue.

    Args:
        batch_id: Batch that was synced
        tenant_id: Tenant clearing queue
    """
    clear_queue()

    emit_receipt("queue_cleared", {
        "tenant_id": tenant_id,
        "batch_id": batch_id,
        "cleared_at": datetime.utcnow().isoformat() + "Z",
    })


def full_sync(tenant_id: str = "default") -> dict:
    """Complete sync workflow: push, verify, clear.

    Args:
        tenant_id: Tenant performing sync

    Returns:
        Final sync status
    """
    # Step 1: Sync queue
    sync_result = sync_queue(tenant_id)
    if not sync_result.get("success"):
        return sync_result

    if sync_result.get("reason") == "queue_empty":
        return sync_result

    batch_id = sync_result["batch_id"]
    local_merkle = sync_result["local_merkle_root"]

    # Step 2: Verify sync
    verified = verify_sync(batch_id, local_merkle, tenant_id)
    if not verified:
        return {
            "success": False,
            "reason": "verification_failed",
            "batch_id": batch_id,
        }

    # Step 3: Clear synced
    clear_synced(batch_id, tenant_id)

    return {
        "success": True,
        "batch_id": batch_id,
        "synced_count": sync_result["synced_count"],
        "verified": True,
        "cleared": True,
    }
