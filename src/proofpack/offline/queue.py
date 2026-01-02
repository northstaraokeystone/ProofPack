"""Local receipt queue for offline operation.

Uses file-based storage (no database required) to queue receipts
when connectivity is unavailable. Receipts are synced to main
ledger when connection is restored.

Design constraints:
- File-based only (no external dependencies)
- Append-only for crash safety
- Merkle-anchored for integrity
- Works on constrained devices
"""
import json
from datetime import datetime
from pathlib import Path

from proofpack.core.receipt import dual_hash, emit_receipt, merkle

# Default queue location
DEFAULT_QUEUE_PATH = Path.home() / ".proofpack" / "offline_queue.jsonl"
DEFAULT_STATE_PATH = Path.home() / ".proofpack" / "offline_state.json"


def _ensure_queue_dir():
    """Ensure queue directory exists."""
    DEFAULT_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    """Load queue state from disk."""
    if DEFAULT_STATE_PATH.exists():
        with open(DEFAULT_STATE_PATH) as f:
            return json.load(f)
    return {
        "local_sequence_id": 0,
        "last_sync_time": None,
        "pending_count": 0,
        "local_merkle_root": None,
    }


def _save_state(state: dict):
    """Save queue state to disk."""
    _ensure_queue_dir()
    with open(DEFAULT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def enqueue_receipt(
    receipt_data: dict,
    tenant_id: str = "default"
) -> dict:
    """Add receipt to local queue for later sync.

    Args:
        receipt_data: Receipt fields (will be enriched with offline metadata)
        tenant_id: Tenant generating receipt

    Returns:
        Complete receipt with offline_metadata attached
    """
    _ensure_queue_dir()
    state = _load_state()

    # Assign local sequence ID
    state["local_sequence_id"] += 1
    local_seq = state["local_sequence_id"]

    # Build receipt with offline metadata
    receipt = {
        **receipt_data,
        "ts": datetime.utcnow().isoformat() + "Z",
        "tenant_id": tenant_id,
        "offline_metadata": {
            "generated_offline": True,
            "local_sequence_id": local_seq,
            "local_merkle_root": state.get("local_merkle_root"),
            "sync_timestamp": None,
            "sync_batch_id": None,
        }
    }

    # Compute payload hash
    receipt["payload_hash"] = dual_hash(json.dumps(receipt_data, sort_keys=True))

    # Append to queue file
    with open(DEFAULT_QUEUE_PATH, "a") as f:
        f.write(json.dumps(receipt) + "\n")

    # Update state
    state["pending_count"] += 1
    state["local_merkle_root"] = get_local_merkle_root()
    _save_state(state)

    # Emit queue receipt (stored locally)
    emit_receipt("offline_enqueue", {
        "tenant_id": tenant_id,
        "local_sequence_id": local_seq,
        "receipt_type": receipt_data.get("receipt_type", "unknown"),
        "queue_size": state["pending_count"],
    })

    return receipt


def get_queue_size() -> int:
    """Count pending receipts in queue.

    Returns:
        Number of unsynced receipts
    """
    if not DEFAULT_QUEUE_PATH.exists():
        return 0

    count = 0
    with open(DEFAULT_QUEUE_PATH) as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def get_local_merkle_root() -> str | None:
    """Compute Merkle root of all queued receipts.

    Returns:
        Dual-hash Merkle root or None if queue empty
    """
    if not DEFAULT_QUEUE_PATH.exists():
        return None

    receipts = []
    with open(DEFAULT_QUEUE_PATH) as f:
        for line in f:
            if line.strip():
                receipts.append(json.loads(line))

    if not receipts:
        return None

    return merkle(receipts)


def peek_queue(n: int = 10) -> list[dict]:
    """View oldest N receipts without removing.

    Args:
        n: Number of receipts to peek

    Returns:
        List of oldest receipts (up to n)
    """
    if not DEFAULT_QUEUE_PATH.exists():
        return []

    receipts = []
    with open(DEFAULT_QUEUE_PATH) as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            if line.strip():
                receipts.append(json.loads(line))

    return receipts


def get_sync_status() -> dict:
    """Get current sync status.

    Returns:
        Dict with pending_count, last_sync_time, local_merkle_root
    """
    state = _load_state()
    return {
        "pending_count": get_queue_size(),
        "last_sync_time": state.get("last_sync_time"),
        "local_merkle_root": get_local_merkle_root(),
        "local_sequence_id": state.get("local_sequence_id", 0),
        "connected": False,  # Will be updated by sync module
    }


def clear_queue():
    """Clear all queued receipts (use after successful sync)."""
    if DEFAULT_QUEUE_PATH.exists():
        DEFAULT_QUEUE_PATH.unlink()

    state = _load_state()
    state["pending_count"] = 0
    state["local_merkle_root"] = None
    _save_state(state)


def get_all_queued() -> list[dict]:
    """Get all queued receipts.

    Returns:
        List of all pending receipts
    """
    if not DEFAULT_QUEUE_PATH.exists():
        return []

    receipts = []
    with open(DEFAULT_QUEUE_PATH) as f:
        for line in f:
            if line.strip():
                receipts.append(json.loads(line))

    return receipts


def mark_synced(batch_id: str):
    """Mark queue as synced with batch ID.

    Args:
        batch_id: ID of sync batch
    """
    state = _load_state()
    state["last_sync_time"] = datetime.utcnow().isoformat() + "Z"
    state["last_sync_batch_id"] = batch_id
    _save_state(state)
