# MCP Integration Guide

ProofPack v3.1 includes a Model Context Protocol (MCP) server that exposes ProofPack capabilities to Claude Desktop, Cursor, Windsurf, and other MCP-compatible AI clients.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Desktop │     │  ProofPack MCP   │     │  ProofPack Core │
│  / Cursor       │◄───►│  Server          │◄───►│  (Ledger, Gate) │
│  / Windsurf     │     │  (Port 8765)     │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Available Tools

| Tool | Description | Scope Required |
|------|-------------|----------------|
| `query_receipts` | Search receipt ledger by criteria | read |
| `validate_receipt` | Verify dual-hash integrity | read |
| `get_lineage` | Trace receipt ancestry via graph | read |
| `spawn_helper` | Trigger RED gate helper spawning | spawn |
| `check_confidence` | Run gate check without execution | read |
| `list_patterns` | Get graduated helper patterns | read |
| `agent_status` | Current spawned agents and states | read |

## Quick Start

### 1. Enable Feature Flag

```python
# config/features.py
FEATURE_MCP_SERVER_ENABLED = True
FEATURE_MCP_AUTH_REQUIRED = True
```

### 2. Start Server

```bash
# CLI command
proof mcp start

# Or directly
python -m proofpack.mcp.server

# With options
proof mcp start --port 9000 --allow-spawn
```

### 3. Configure Client

Copy the appropriate config from `docs/mcp-setup/`:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "proofpack": {
      "command": "python",
      "args": ["-m", "proofpack.mcp.server"],
      "env": {
        "PROOFPACK_AUTH_TOKEN": "your-token-here"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "servers": [
    {
      "name": "proofpack",
      "type": "stdio",
      "command": "python",
      "args": ["-m", "proofpack.mcp.server"]
    }
  ]
}
```

## Authentication

Token-based authentication is enabled by default:

```bash
# Set token via environment
export PROOFPACK_AUTH_TOKEN="your-secure-token"

# Or via CLI
proof mcp start --token "your-secure-token"
```

Disable for local development only:
```bash
proof mcp start --no-auth
```

## Rate Limiting

Default limits:
- 100 requests per minute per client
- Burst: 20 requests per 10 seconds

Configure via environment:
```bash
export PROOFPACK_MCP_RATE_LIMIT=200
export PROOFPACK_MCP_BURST=30
```

## Tool Details

### query_receipts

Search the receipt ledger with flexible filtering.

**Parameters:**
```json
{
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-12-31T23:59:59Z"
  },
  "receipt_type": "gate_decision",
  "payload_filter": {
    "confidence_score": {"$gte": 0.8}
  },
  "limit": 100
}
```

**Response:**
```json
{
  "receipts": [...],
  "count": 42,
  "has_more": false
}
```

### get_lineage

Trace receipt ancestry using the temporal knowledge graph.

**Parameters:**
```json
{
  "receipt_id": "abc123def456",
  "depth": 5,
  "direction": "ancestors"
}
```

**Response:**
```json
{
  "nodes": [
    {"id": "abc123def456", "type": "gate_decision", "ts": "..."},
    {"id": "parent123", "type": "spawn", "ts": "..."}
  ],
  "edges": [
    {"source": "abc123def456", "target": "parent123", "type": "CAUSED_BY"}
  ]
}
```

### spawn_helper

Trigger helper spawning for complex problems. Requires `spawn` scope.

**Parameters:**
```json
{
  "problem_description": "Unable to resolve complex query",
  "context": {
    "confidence": 0.5,
    "wound_count": 3
  },
  "strategy": "parallel"
}
```

**Response:**
```json
{
  "spawned": true,
  "agent_ids": ["helper_001", "helper_002"],
  "spawn_receipt": "..."
}
```

### check_confidence

Preview gate decision without execution.

**Parameters:**
```json
{
  "action_proposal": {
    "description": "Execute database migration",
    "confidence": 0.75,
    "variance": 0.1
  }
}
```

**Response:**
```json
{
  "gate": "YELLOW",
  "confidence": 0.75,
  "recommendation": "Execute with monitoring",
  "would_spawn": false
}
```

## Security Considerations

### Spawn Control

External spawning is disabled by default. Enable only after:
1. Verifying client authentication
2. Setting appropriate rate limits
3. Configuring spawn depth limits

```bash
# Enable spawning
proof mcp start --allow-spawn --max-spawn-depth 2
```

### Network Exposure

By default, server binds to `127.0.0.1`. For remote access:

```bash
# NOT RECOMMENDED for production
proof mcp start --host 0.0.0.0

# Use SSH tunnel instead
ssh -L 8765:localhost:8765 user@server
```

## Monitoring

### Server Status

```bash
proof mcp status
```

Output:
```
MCP Server: running
Port: 8765
Clients connected: 2
Requests (1h): 1,234
Rate limited: 5
Auth failures: 0
```

### Request Logging

All MCP requests emit receipts:
```json
{
  "receipt_type": "mcp_request",
  "ts": "2024-01-15T10:30:00Z",
  "client_id": "cursor-abc123",
  "tool": "query_receipts",
  "latency_ms": 45
}
```

## Integration with Knowledge Graph

MCP tools automatically integrate with the temporal knowledge graph:

1. `get_lineage` queries the graph directly
2. Spawn events are recorded as graph nodes
3. Tool calls can be traced back to their triggers

See [Temporal Graph Documentation](temporal-graph.md) for details.

## CLI Reference

```bash
# Start server
proof mcp start [--port PORT] [--allow-spawn] [--no-auth]

# Stop server
proof mcp stop

# Check status
proof mcp status

# List available tools
proof mcp tools

# Test configuration
proof mcp test
```

## Troubleshooting

### Connection Refused
- Verify server is running: `proof mcp status`
- Check port: `lsof -i :8765`

### Authentication Failed
- Ensure token matches between server and client
- Check token is not expired

### Rate Limited
- Response includes `Retry-After` header
- Wait specified seconds before retrying

### Spawn Not Allowed
- Enable with `--allow-spawn` flag
- Verify `spawn` scope in authentication

## Related Documentation

- [MCP Setup Guide](mcp-setup/README.md) - Client configuration files
- [Temporal Graph](temporal-graph.md) - Receipt relationship queries
- [Web Fallback](web-fallback.md) - Confidence-gated augmentation
