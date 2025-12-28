# ProofPack MCP Server Setup

This guide explains how to configure ProofPack as an MCP (Model Context Protocol) server for use with Claude Desktop, Cursor, Windsurf, and other MCP-compatible clients.

## Overview

The ProofPack MCP server exposes the following tools:

| Tool | Description |
|------|-------------|
| `query_receipts` | Search receipt ledger by criteria |
| `validate_receipt` | Verify dual-hash integrity |
| `get_lineage` | Trace receipt ancestry |
| `spawn_helper` | Trigger RED gate helper spawning |
| `check_confidence` | Run gate check without execution |
| `list_patterns` | Get graduated helper patterns |
| `agent_status` | Current spawned agents |

## Quick Start

### 1. Start the MCP Server

```bash
# Default configuration
python -m proofpack.mcp.server

# With custom port
python -m proofpack.mcp.server --port 9000

# With spawning enabled
python -m proofpack.mcp.server --allow-spawn

# Test configuration
python -m proofpack.mcp.server --test
```

### 2. Configure Your Client

See the client-specific configuration files in this directory:
- `claude_desktop_config.json` - For Claude Desktop
- `cursor_mcp.json` - For Cursor
- `windsurf_mcp.json` - For Windsurf

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROOFPACK_MCP_PORT` | Server port | 8765 |
| `PROOFPACK_MCP_HOST` | Server host | 127.0.0.1 |
| `PROOFPACK_MCP_AUTH_REQUIRED` | Require authentication | true |
| `PROOFPACK_AUTH_TOKEN` | Authentication token | (required if auth enabled) |
| `PROOFPACK_MCP_SPAWN_ALLOWED` | Allow spawning via MCP | false |
| `PROOFPACK_MCP_RATE_LIMIT` | Requests per minute | 100 |

### Security

**Authentication**: Token-based authentication is enabled by default. Set `PROOFPACK_AUTH_TOKEN` environment variable with a secure token.

**Spawning**: External spawning is disabled by default. Enable only after verifying access controls.

**Rate Limiting**: 100 requests per minute per client, with burst limit of 20 requests per 10 seconds.

## Tool Details

### query_receipts

Search the receipt ledger with flexible filtering.

```json
{
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-12-31T23:59:59Z"
  },
  "receipt_type": "gate_decision",
  "payload_filter": {
    "confidence_score": 0.85
  },
  "limit": 100
}
```

### validate_receipt

Verify the integrity of a receipt using dual-hash validation.

```json
{
  "receipt_id": "abc123def456..."
}
```

### spawn_helper

Trigger helper spawning for problem-solving. Requires `spawn` scope.

```json
{
  "problem_description": "Unable to resolve complex query",
  "context": {
    "confidence": 0.5,
    "wound_count": 3
  }
}
```

### check_confidence

Preview gate decision without execution.

```json
{
  "action_proposal": {
    "confidence": 0.75,
    "wound_count": 0,
    "variance": 0.1
  }
}
```

## Troubleshooting

### Connection refused

Ensure the server is running and the port is correct.

### Authentication failed

Check that `PROOFPACK_AUTH_TOKEN` is set correctly in both server and client configurations.

### Rate limited

Wait for the retry-after period, or increase the rate limit.

### Spawn not allowed

Enable spawning with `--allow-spawn` or set `PROOFPACK_MCP_SPAWN_ALLOWED=true`.
