"""MCP server entry point for ProofPack.

This module implements an MCP (Model Context Protocol) server that exposes
ProofPack capabilities to MCP-compatible clients like Claude Desktop, Cursor,
and Windsurf.

Usage:
    # Start server (CLI)
    python -m proofpack.mcp.server

    # Start server (programmatic)
    from mcp import start_server
    start_server()

    # With custom config
    from mcp.config import MCPConfig
    config = MCPConfig(port=9000, auth_required=False)
    start_server(config)
"""
import asyncio
import json
import logging
import sys
import time
from typing import Optional

from core.receipt import emit_receipt

from .auth import AuthHandler
from .config import MCPConfig, DEFAULT_CONFIG
from .tools import list_tools, execute_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("proofpack.mcp")


class MCPServer:
    """MCP Server implementation for ProofPack."""

    def __init__(self, config: MCPConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.auth_handler = AuthHandler(self.config)
        self._running = False
        self._start_time: Optional[float] = None
        self._request_count = 0
        self._connections: dict[str, dict] = {}

    async def handle_request(self, request: dict) -> dict:
        """Handle an incoming MCP request.

        Args:
            request: MCP request dictionary

        Returns:
            MCP response dictionary
        """
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})

        try:
            # Handle different MCP methods
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return self._handle_list_tools(request_id, params)
            elif method == "tools/call":
                return await self._handle_call_tool(request_id, params)
            elif method == "ping":
                return self._success_response(request_id, {"pong": True})
            else:
                return self._error_response(
                    request_id,
                    -32601,
                    f"Unknown method: {method}"
                )

        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            return self._error_response(request_id, -32603, str(e))

    def _handle_initialize(self, request_id: str, params: dict) -> dict:
        """Handle initialize request."""
        client_info = params.get("clientInfo", {})
        client_name = client_info.get("name", "unknown")

        logger.info(f"Client initialized: {client_name}")

        emit_receipt("mcp_initialized", {
            "client_name": client_name,
            "protocol_version": params.get("protocolVersion", "1.0"),
        })

        return self._success_response(request_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "proofpack-mcp",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
            },
        })

    def _handle_list_tools(self, request_id: str, params: dict) -> dict:
        """Handle tools/list request."""
        tools = list_tools()

        # Filter to allowed tools
        allowed = set(self.config.allowed_tools)
        tools = [t for t in tools if t["name"] in allowed]

        return self._success_response(request_id, {"tools": tools})

    async def _handle_call_tool(self, request_id: str, params: dict) -> dict:
        """Handle tools/call request."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Check if tool is allowed
        if tool_name not in self.config.allowed_tools:
            return self._error_response(
                request_id,
                -32602,
                f"Tool not allowed: {tool_name}"
            )

        # Check spawn permission for spawn_helper
        if tool_name == "spawn_helper" and not self.config.spawn_allowed:
            return self._error_response(
                request_id,
                -32602,
                "Spawning not allowed for this server"
            )

        # Execute tool
        self._request_count += 1
        start_time = time.time()

        result = execute_tool(tool_name, arguments)

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(f"Tool {tool_name} executed in {elapsed_ms:.1f}ms")

        if result.success:
            return self._success_response(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result.data, indent=2),
                    }
                ],
                "isError": False,
            })
        else:
            return self._success_response(request_id, {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {result.error}",
                    }
                ],
                "isError": True,
            })

    def _success_response(self, request_id: str, result: dict) -> dict:
        """Build a success response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _error_response(self, request_id: str, code: int, message: str) -> dict:
        """Build an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def run_stdio(self):
        """Run server using stdio transport (for Claude Desktop)."""
        self._running = True
        self._start_time = time.time()

        logger.info("ProofPack MCP server starting on stdio")

        emit_receipt("mcp_server_started", {
            "transport": "stdio",
            "config": {
                "auth_required": self.config.auth_required,
                "spawn_allowed": self.config.spawn_allowed,
                "tools_count": len(self.config.allowed_tools),
            },
        })

        # Read from stdin, write to stdout
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol, sys.stdin
        )

        while self._running:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break

                # Parse request
                try:
                    request = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                # Handle request
                response = await self.handle_request(request)

                # Write response to stdout
                response_line = json.dumps(response) + "\n"
                sys.stdout.write(response_line)
                sys.stdout.flush()

            except Exception as e:
                logger.exception(f"Error in stdio loop: {e}")
                break

        logger.info("ProofPack MCP server stopped")

    def stop(self):
        """Stop the server."""
        self._running = False
        logger.info("Server stop requested")

    def get_status(self) -> dict:
        """Get server status."""
        uptime = time.time() - self._start_time if self._start_time else 0

        return {
            "running": self._running,
            "uptime_seconds": int(uptime),
            "request_count": self._request_count,
            "connections": len(self._connections),
            "config": {
                "port": self.config.port,
                "auth_required": self.config.auth_required,
                "spawn_allowed": self.config.spawn_allowed,
            },
        }


# Global server instance
_server: Optional[MCPServer] = None


def start_server(config: MCPConfig = None):
    """Start the MCP server.

    Args:
        config: Optional server configuration
    """
    global _server

    if _server and _server._running:
        logger.warning("Server already running")
        return

    _server = MCPServer(config or DEFAULT_CONFIG)

    # Run the server
    try:
        asyncio.run(_server.run_stdio())
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        _server.stop()


def stop_server():
    """Stop the MCP server."""
    global _server

    if _server:
        _server.stop()
        _server = None


def get_server_status() -> Optional[dict]:
    """Get current server status."""
    if _server:
        return _server.get_status()
    return None


def test_server() -> bool:
    """Test server configuration without starting.

    Returns True if configuration is valid.
    """
    config = MCPConfig.from_env()
    errors = config.validate()

    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        return False

    logger.info("Server configuration valid")
    logger.info(f"  Port: {config.port}")
    logger.info(f"  Auth required: {config.auth_required}")
    logger.info(f"  Spawn allowed: {config.spawn_allowed}")
    logger.info(f"  Tools: {len(config.allowed_tools)}")

    return True


# Entry point for python -m proofpack.mcp.server
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ProofPack MCP Server")
    parser.add_argument("--test", action="store_true", help="Test configuration only")
    parser.add_argument("--port", type=int, help="Server port")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication")
    parser.add_argument("--allow-spawn", action="store_true", help="Allow spawning")

    args = parser.parse_args()

    if args.test:
        success = test_server()
        sys.exit(0 if success else 1)

    # Build config from args
    config = MCPConfig.from_env()

    if args.port:
        config.port = args.port
    if args.no_auth:
        config.auth_required = False
    if args.allow_spawn:
        config.spawn_allowed = True

    # Validate
    errors = config.validate()
    if errors and config.auth_required:
        for error in errors:
            logger.error(f"Config error: {error}")
        sys.exit(1)

    # Start server
    start_server(config)
