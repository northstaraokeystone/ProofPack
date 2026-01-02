"""Keep graph in sync with receipt ledger.

Synchronization strategies:
    - Live sync: Add to graph on every emit_receipt()
    - Batch sync: Periodic backfill from ledger
    - Backfill: One-time historical ingestion
"""
import json
import time
from pathlib import Path
from typing import Callable, Optional

from proofpack.core.receipt import emit_receipt

from .backend import get_backend
from .ingest import add_node, bulk_ingest
from .index import rebuild_index


class GraphSyncer:
    """Keeps the knowledge graph in sync with the receipt ledger."""

    def __init__(
        self,
        ledger_path: str = "receipts.jsonl",
        sync_interval_seconds: int = 60,
    ):
        self.ledger_path = Path(ledger_path)
        self.sync_interval_seconds = sync_interval_seconds
        self._last_sync_time: float = 0
        self._last_sync_position: int = 0
        self._running: bool = False

    def backfill(self, tenant_id: str = "default") -> dict:
        """One-time historical ingestion from ledger.

        Reads entire ledger and ingests all receipts to graph.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Summary statistics
        """
        if not self.ledger_path.exists():
            return {"error": f"Ledger not found: {self.ledger_path}"}

        start_time = time.perf_counter()

        # Read all receipts
        receipts = []
        with open(self.ledger_path) as f:
            for line in f:
                if line.strip():
                    try:
                        receipts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        # Bulk ingest
        result = bulk_ingest(receipts, tenant_id, emit_progress=True)

        # Rebuild indexes
        rebuild_index(tenant_id)

        # Update sync position
        self._last_sync_position = self.ledger_path.stat().st_size
        self._last_sync_time = time.time()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        emit_receipt("graph_backfill", {
            "ledger_path": str(self.ledger_path),
            "receipts_processed": result["total"],
            "nodes_added": result["added"],
            "elapsed_ms": elapsed_ms,
            "tenant_id": tenant_id,
        })

        return {
            **result,
            "elapsed_ms": elapsed_ms,
            "sync_position": self._last_sync_position,
        }

    def incremental_sync(self, tenant_id: str = "default") -> dict:
        """Sync new receipts since last sync.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Summary statistics
        """
        if not self.ledger_path.exists():
            return {"error": f"Ledger not found: {self.ledger_path}"}

        start_time = time.perf_counter()

        current_size = self.ledger_path.stat().st_size

        if current_size <= self._last_sync_position:
            return {
                "receipts_processed": 0,
                "nodes_added": 0,
                "no_changes": True,
            }

        # Read new receipts
        receipts = []
        with open(self.ledger_path) as f:
            f.seek(self._last_sync_position)
            for line in f:
                if line.strip():
                    try:
                        receipts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        # Ingest new receipts
        added = 0
        for receipt in receipts:
            node_id = add_node(receipt, tenant_id)
            if node_id:
                added += 1

        # Update sync position
        self._last_sync_position = current_size
        self._last_sync_time = time.time()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        emit_receipt("graph_incremental_sync", {
            "receipts_processed": len(receipts),
            "nodes_added": added,
            "elapsed_ms": elapsed_ms,
            "tenant_id": tenant_id,
        })

        return {
            "receipts_processed": len(receipts),
            "nodes_added": added,
            "elapsed_ms": elapsed_ms,
            "sync_position": self._last_sync_position,
        }

    def should_sync(self) -> bool:
        """Check if sync is needed based on interval.

        Returns:
            True if sync interval has elapsed
        """
        return time.time() - self._last_sync_time >= self.sync_interval_seconds

    def start_background_sync(
        self,
        callback: Optional[Callable[[dict], None]] = None,
        tenant_id: str = "default",
    ) -> None:
        """Start background sync loop.

        Args:
            callback: Optional callback for sync results
            tenant_id: Tenant identifier
        """
        import threading

        def sync_loop():
            while self._running:
                if self.should_sync():
                    result = self.incremental_sync(tenant_id)
                    if callback:
                        callback(result)
                time.sleep(1)

        self._running = True
        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()

    def stop_background_sync(self) -> None:
        """Stop background sync loop."""
        self._running = False

    def get_sync_status(self) -> dict:
        """Get current sync status.

        Returns:
            Status dictionary
        """
        backend = get_backend()

        return {
            "ledger_path": str(self.ledger_path),
            "ledger_exists": self.ledger_path.exists(),
            "last_sync_time": self._last_sync_time,
            "last_sync_position": self._last_sync_position,
            "sync_interval_seconds": self.sync_interval_seconds,
            "is_running": self._running,
            "node_count": backend.node_count(),
            "edge_count": backend.edge_count(),
        }


# Global syncer instance
_syncer: Optional[GraphSyncer] = None


def get_syncer(ledger_path: str = "receipts.jsonl") -> GraphSyncer:
    """Get or create the global syncer instance.

    Args:
        ledger_path: Path to ledger file

    Returns:
        GraphSyncer instance
    """
    global _syncer

    if _syncer is None:
        _syncer = GraphSyncer(ledger_path)

    return _syncer


def backfill(ledger_path: str = "receipts.jsonl", tenant_id: str = "default") -> dict:
    """Convenience function for one-time backfill.

    Args:
        ledger_path: Path to ledger file
        tenant_id: Tenant identifier

    Returns:
        Summary statistics
    """
    syncer = get_syncer(ledger_path)
    return syncer.backfill(tenant_id)


def sync_status() -> dict:
    """Get current sync status.

    Returns:
        Status dictionary
    """
    if _syncer:
        return _syncer.get_sync_status()
    return {"initialized": False}
