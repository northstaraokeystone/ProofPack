"""Offline mode module for disconnected receipt generation.

Designed for systems that can't call home:
- Off-planet systems (satellites, lunar missions)
- Autonomous vehicles (tunnels, remote areas)
- Defense systems (RF-denied environments)
- Edge devices (IoT, constrained power)

Receipts generate locally. Merkle roots compute locally.
Sync happens when connectivity allows.
Governance doesn't stop when WiFi does.

Usage:
    from offline import queue, sync

    # Generate receipt offline
    receipt = queue.enqueue_receipt({"receipt_type": "decision", ...})

    # Check queue status
    status = queue.get_sync_status()

    # Sync when connected
    if sync.is_connected():
        sync.sync_queue()
"""
from proofpack.offline.queue import (
    enqueue_receipt,
    get_queue_size,
    get_local_merkle_root,
    peek_queue,
    get_sync_status,
)
from proofpack.offline.sync import (
    is_connected,
    sync_queue,
    verify_sync,
    clear_synced,
)
from proofpack.offline.merkle_local import (
    build_local_merkle,
    get_proof_path,
    verify_local_inclusion,
)
from proofpack.offline.reconnect import (
    handle_reconnection,
    resolve_conflicts,
    get_conflict_status,
)

__all__ = [
    # Queue operations
    "enqueue_receipt",
    "get_queue_size",
    "get_local_merkle_root",
    "peek_queue",
    "get_sync_status",
    # Sync operations
    "is_connected",
    "sync_queue",
    "verify_sync",
    "clear_synced",
    # Merkle operations
    "build_local_merkle",
    "get_proof_path",
    "verify_local_inclusion",
    # Reconnection
    "handle_reconnection",
    "resolve_conflicts",
    "get_conflict_status",
]
