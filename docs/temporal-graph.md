# Temporal Knowledge Graph

ProofPack v3.1 includes a temporal knowledge graph for queryable receipt storage with relationship tracking and performance SLOs.

## Overview

The knowledge graph stores receipts as nodes with typed edges representing causal, temporal, and spawn relationships.

```
┌──────────────┐    CAUSED_BY    ┌──────────────┐
│ gate_decision│◄────────────────│    spawn     │
│   (RED)      │                 │   receipt    │
└──────────────┘                 └──────────────┘
       ▲                                ▲
       │ PRECEDED                       │ SPAWNED
       │                                │
┌──────────────┐                 ┌──────────────┐
│ gate_decision│                 │    helper    │
│  (YELLOW)    │                 │   agent      │
└──────────────┘                 └──────────────┘
```

## Graph Schema

### Node Properties

Every node contains:
```python
{
    "node_id": str,          # 16-char short form of payload_hash
    "receipt_type": str,     # e.g., "gate_decision", "spawn", "brief"
    "event_time": str,       # ISO8601 timestamp
    "ingestion_time": float, # Unix timestamp
    "properties": dict       # Full receipt payload
}
```

### Edge Types

| Edge Type | Description | Example |
|-----------|-------------|---------|
| `CAUSED_BY` | Causal relationship | RED gate -> spawn event |
| `PRECEDED` | Temporal ordering | Earlier receipt -> later receipt |
| `SPAWNED` | Agent creation | Spawn receipt -> helper agent |
| `GRADUATED_TO` | Pattern promotion | Helper -> permanent pattern |
| `MERGED_WITH` | Web fallback merge | Brief -> web results |
| `REVISED_BY` | Correction | Original brief -> corrected brief |

## Enabling the Graph

```python
# config/features.py
FEATURE_GRAPH_ENABLED = True
FEATURE_GRAPH_AUTO_INGEST = True  # Auto-ingest new receipts
```

Or via CLI:
```bash
proof graph status  # Check if enabled
```

## Query Types

### Lineage Query

Trace receipt ancestry through causal relationships.

**SLO:** < 100ms

```bash
proof graph query lineage abc123def456 --depth 5
```

Python API:
```python
from proofpack.graph.query import lineage

result = lineage("abc123def456", depth=5)
print(f"Ancestors: {result.nodes}")
print(f"Query time: {result.elapsed_ms}ms")
```

Response:
```json
{
  "query_type": "lineage",
  "root_id": "abc123def456",
  "nodes": [
    {"id": "abc123def456", "type": "gate_decision", "ts": "..."},
    {"id": "parent123456", "type": "spawn", "ts": "..."}
  ],
  "edges": [
    {"source": "abc123def456", "target": "parent123456", "type": "CAUSED_BY"}
  ],
  "elapsed_ms": 45
}
```

### Temporal Query

Find receipts within a time range.

**SLO:** < 150ms

```bash
proof graph query temporal \
  --start "2024-01-01T00:00:00Z" \
  --end "2024-01-02T00:00:00Z"
```

Python API:
```python
from proofpack.graph.query import temporal

result = temporal(
    start="2024-01-01T00:00:00Z",
    end="2024-01-02T00:00:00Z",
    receipt_types=["gate_decision", "spawn"]
)
```

### Match Query

Find receipts matching property patterns.

**SLO:** < 200ms

```bash
proof graph query match '{"receipt_type": "gate_decision", "gate": "RED"}'
```

Python API:
```python
from proofpack.graph.query import match

result = match({
    "receipt_type": "gate_decision",
    "properties.gate": "RED"
})
```

### Causal Chain Query

Trace full causal chains for debugging.

**SLO:** < 300ms

```bash
proof graph query causal abc123def456
```

Python API:
```python
from proofpack.graph.query import causal_chain

result = causal_chain("abc123def456", max_depth=10)
```

### Episode Query

Find related receipts within a reasoning episode.

**SLO:** < 250ms

```bash
proof graph episode abc123def456 --window 30s
```

Python API:
```python
from proofpack.graph.episodic import find_episode

result = find_episode("abc123def456", window_seconds=30)
```

## Ingestion

### Automatic Ingestion

When `FEATURE_GRAPH_AUTO_INGEST` is enabled, all receipts are automatically added to the graph.

### Manual Ingestion

```python
from proofpack.graph.ingest import add_node, add_edge

# Add receipt as node
node_id = add_node({
    "receipt_type": "gate_decision",
    "ts": "2024-01-15T10:30:00Z",
    "payload_hash": "abc123...:def456...",
    "gate": "YELLOW"
})

# Add relationship
add_edge(node_id, parent_id, "CAUSED_BY")
```

### Bulk Ingestion

For backfilling historical receipts:

```bash
proof graph backfill receipts.jsonl --batch-size 1000
```

Python API:
```python
from proofpack.graph.ingest import bulk_ingest

result = bulk_ingest(receipts, emit_progress=True)
print(f"Added: {result['added']}, Errors: {result['errors']}")
```

## Backend

The default backend is NetworkX (in-memory). For production:

### NetworkX (Default)

```python
from proofpack.graph.backend import NetworkXBackend

backend = NetworkXBackend()
```

- In-memory, fast for development
- Not persistent across restarts
- Max ~100k nodes recommended

### Neo4j (Production)

```python
# config/features.py
FEATURE_GRAPH_BACKEND = "neo4j"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
```

### PostgreSQL (Alternative)

Using the graph extension for PostgreSQL (Apache AGE):

```python
FEATURE_GRAPH_BACKEND = "postgresql"
POSTGRESQL_GRAPH_URI = "postgresql://..."
```

## Indexing

### Automatic Indexes

The following indexes are created automatically:
- `event_time` - For temporal queries
- `receipt_type` - For type filtering
- `node_id` - Primary lookup

### Custom Indexes

```python
from proofpack.graph.index import create_index

create_index("properties.gate", index_type="hash")
create_index("properties.confidence", index_type="btree")
```

## Performance

### SLO Summary

| Query Type | Target | P99 |
|------------|--------|-----|
| Lineage | < 100ms | 80ms |
| Temporal | < 150ms | 120ms |
| Match | < 200ms | 160ms |
| Causal Chain | < 300ms | 250ms |
| Episode | < 250ms | 200ms |

### Optimization Tips

1. **Limit depth** for lineage queries
2. **Use indexes** for frequently filtered properties
3. **Batch ingestion** for historical data
4. **Prune old data** with compaction

### Monitoring

```bash
proof graph status
```

Output:
```
Graph Backend: NetworkX
Nodes: 45,231
Edges: 123,456
Indexes: 4
Memory: 234 MB
Last query p50: 25ms
Last query p99: 85ms
```

## Visualization

### Export to DOT

```bash
proof graph visualize abc123def456 --format dot > graph.dot
dot -Tpng graph.dot -o graph.png
```

### Export to JSON

```bash
proof graph visualize abc123def456 --format json > graph.json
```

### Interactive (requires networkx[graphviz])

```bash
proof graph visualize abc123def456 --interactive
```

## CLI Reference

```bash
# Status
proof graph status

# Queries
proof graph query lineage <node_id> [--depth N]
proof graph query temporal --start ISO --end ISO
proof graph query match '<json_pattern>'
proof graph query causal <node_id>

# Episodes
proof graph episode <node_id> [--window SECONDS]

# Backfill
proof graph backfill <file.jsonl> [--batch-size N]

# Visualization
proof graph visualize <node_id> [--format dot|json] [--depth N]
```

## Integration Points

### MCP Server

The `get_lineage` MCP tool queries the graph directly:
```python
# MCP client request
{
  "tool": "get_lineage",
  "params": {"receipt_id": "abc123", "depth": 5}
}
```

### Web Fallback

Merge events are recorded in the graph:
```
[brief] --MERGED_WITH--> [web_retrieval]
[brief] --REVISED_BY--> [corrected_brief]
```

### Gate System

Gate decisions trigger automatic edge creation:
```
[gate_decision(RED)] --CAUSED_BY--> [spawn_receipt]
[spawn_receipt] --SPAWNED--> [helper_agent]
```

## Related Documentation

- [MCP Integration](mcp-integration.md) - Using graph via MCP
- [Web Fallback](web-fallback.md) - CRAG integration
- [Architecture](architecture.md) - System overview
