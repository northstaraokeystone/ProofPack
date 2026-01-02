"""Receipt-to-graph ingestion.

Convert receipts into graph nodes and edges. Automatically detects
relationships based on receipt content.

Relationship types:
    - CAUSED_BY: Receipt A was caused by receipt B
    - PRECEDED: Receipt A happened before receipt B (temporal)
    - SPAWNED: Agent A spawned agent B
    - GRADUATED_TO: Agent pattern was graduated to permanent pattern
"""
import time
from typing import Optional

from core.receipt import emit_receipt

from .backend import GraphNode, GraphEdge, get_backend


# Receipt fields that indicate parent relationships
PARENT_FIELDS = [
    "parent_receipt_id",
    "parent_agent_id",
    "source_receipt",
    "caused_by",
    "triggered_by",
]

# Edge type mapping based on receipt type
RECEIPT_TO_EDGE_TYPE = {
    "spawn": "SPAWNED",
    "graduation": "GRADUATED_TO",
    "agent_registered": "SPAWNED",
    "wound": "CAUSED_BY",
    "anomaly": "CAUSED_BY",
    "gate_decision": "CAUSED_BY",
    "block": "CAUSED_BY",
}


def add_node(receipt: dict, tenant_id: str = "default") -> Optional[str]:
    """Add a receipt as a node in the knowledge graph.

    Args:
        receipt: Receipt dictionary
        tenant_id: Tenant identifier

    Returns:
        Node ID if added, None if already exists
    """
    backend = get_backend()

    # Extract node ID (use payload_hash as unique ID)
    node_id = receipt.get("payload_hash", "")
    if not node_id:
        return None

    # Short form for node ID (first 16 chars)
    short_id = node_id[:16]

    # Check if already exists
    if backend.get_node(short_id) is not None:
        return None

    # Extract properties
    properties = {}
    for key, value in receipt.items():
        if key not in ("receipt_type", "ts", "tenant_id", "payload_hash"):
            # Only store serializable values
            if isinstance(value, (str, int, float, bool, type(None))):
                properties[key] = value
            elif isinstance(value, (list, dict)):
                properties[key] = value

    # Create node
    node = GraphNode(
        node_id=short_id,
        receipt_type=receipt.get("receipt_type", "unknown"),
        event_time=receipt.get("ts", ""),
        ingestion_time=time.time(),
        properties=properties,
    )

    if backend.add_node(node):
        # Try to add edges to parent receipts
        _add_parent_edges(receipt, short_id, tenant_id)

        emit_receipt("graph_ingest", {
            "node_id": short_id,
            "receipt_type": receipt.get("receipt_type"),
            "tenant_id": tenant_id,
        })

        return short_id

    return None


def _add_parent_edges(receipt: dict, node_id: str, tenant_id: str) -> None:
    """Add edges from this node to parent nodes."""
    backend = get_backend()
    receipt_type = receipt.get("receipt_type", "")

    # Determine edge type
    edge_type = RECEIPT_TO_EDGE_TYPE.get(receipt_type, "CAUSED_BY")

    # Look for parent references
    for field in PARENT_FIELDS:
        parent_id = receipt.get(field)
        if parent_id:
            # Use short form
            parent_short = parent_id[:16] if len(parent_id) > 16 else parent_id

            # Check if parent exists in graph
            if backend.get_node(parent_short):
                edge = GraphEdge(
                    source_id=node_id,
                    target_id=parent_short,
                    edge_type=edge_type,
                    properties={"field": field},
                )
                backend.add_edge(edge)

    # Handle special receipt types with multiple relationships
    if receipt_type == "spawn":
        # Child agents point to parent spawn receipt
        # Note: children are added later, edge will be created then
        pass

    if receipt_type == "attach":
        # Create edges to attached receipts
        mappings = receipt.get("mappings", {})
        for claim_id, receipt_ids in mappings.items():
            for rid in receipt_ids:
                rid_short = rid[:16] if len(rid) > 16 else rid
                if backend.get_node(rid_short):
                    edge = GraphEdge(
                        source_id=node_id,
                        target_id=rid_short,
                        edge_type="ATTACHED",
                        properties={"claim_id": claim_id},
                    )
                    backend.add_edge(edge)


def add_edge(
    source_id: str,
    target_id: str,
    edge_type: str,
    properties: dict = None,
    tenant_id: str = "default",
) -> bool:
    """Add an edge between two nodes.

    Args:
        source_id: Source node ID
        target_id: Target node ID
        edge_type: Type of relationship
        properties: Optional edge properties
        tenant_id: Tenant identifier

    Returns:
        True if edge added, False otherwise
    """
    backend = get_backend()

    edge = GraphEdge(
        source_id=source_id[:16],
        target_id=target_id[:16],
        edge_type=edge_type,
        properties=properties or {},
    )

    return backend.add_edge(edge)


def bulk_ingest(
    receipts: list[dict],
    tenant_id: str = "default",
    emit_progress: bool = True,
) -> dict:
    """Bulk ingest multiple receipts.

    Args:
        receipts: List of receipt dictionaries
        tenant_id: Tenant identifier
        emit_progress: Whether to emit progress receipts

    Returns:
        Summary dict with counts
    """
    start_time = time.time()

    # Sort by timestamp for proper temporal ordering
    sorted_receipts = sorted(receipts, key=lambda r: r.get("ts", ""))

    added = 0
    skipped = 0
    errors = 0

    for i, receipt in enumerate(sorted_receipts):
        try:
            node_id = add_node(receipt, tenant_id)
            if node_id:
                added += 1
            else:
                skipped += 1
        except Exception:
            errors += 1

        # Progress update every 1000 receipts
        if emit_progress and (i + 1) % 1000 == 0:
            emit_receipt("graph_ingest_progress", {
                "processed": i + 1,
                "total": len(receipts),
                "added": added,
                "skipped": skipped,
                "errors": errors,
                "tenant_id": tenant_id,
            })

    elapsed_ms = (time.time() - start_time) * 1000

    summary = {
        "total": len(receipts),
        "added": added,
        "skipped": skipped,
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    }

    emit_receipt("graph_bulk_ingest", {
        **summary,
        "tenant_id": tenant_id,
    })

    return summary


def ingest_from_ledger(
    ledger_path: str,
    tenant_id: str = "default",
) -> dict:
    """Ingest all receipts from a ledger file.

    Args:
        ledger_path: Path to JSONL ledger file
        tenant_id: Tenant identifier

    Returns:
        Summary dict with counts
    """
    import json
    from pathlib import Path

    ledger = Path(ledger_path)
    if not ledger.exists():
        return {"error": f"Ledger not found: {ledger_path}"}

    receipts = []
    with open(ledger) as f:
        for line in f:
            if line.strip():
                try:
                    receipts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return bulk_ingest(receipts, tenant_id)
