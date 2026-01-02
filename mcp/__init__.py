"""MCP (Model Context Protocol) server for ProofPack.

Exposes ProofPack capabilities as MCP tools for Claude Desktop, Cursor,
Windsurf, and other MCP-compatible clients.

Tools available:
    - query_receipts: Search receipt ledger by criteria
    - validate_receipt: Verify dual-hash integrity
    - get_lineage: Trace receipt ancestry
    - spawn_helper: Trigger RED gate helper spawning
    - check_confidence: Run gate check without execution
    - list_patterns: Get graduated helper patterns
    - agent_status: Current spawned agents

Usage:
    python -m mcp.server

Configuration:
    See proofpack.mcp.config for server settings.
"""

from .config import MCPConfig
from .server import start_server, stop_server

__all__ = [
    "MCPConfig",
    "start_server",
    "stop_server",
]
