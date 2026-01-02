"""Tests for MCP server module.

Validates that MCP server starts, exposes tools, and handles auth.
"""
from unittest.mock import patch


class TestMCPConfig:
    """Tests for MCP configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig()

        assert config.port == 8765
        assert config.max_connections == 10
        assert config.auth_required is True
        assert config.spawn_allowed is False
        assert len(config.allowed_tools) > 0

    def test_config_from_env(self):
        """Test loading config from environment."""
        from proofpack.mcp.config import MCPConfig

        with patch.dict('os.environ', {'PROOFPACK_MCP_PORT': '9000'}):
            config = MCPConfig.from_env()

        assert config.port == 9000

    def test_config_validation(self):
        """Test configuration validation."""
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(port=0)
        errors = config.validate()

        assert len(errors) > 0
        assert any("port" in e.lower() for e in errors)

    def test_auth_required_needs_token(self):
        """Test that auth_required needs token."""
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=True, auth_token="")
        errors = config.validate()

        assert any("auth" in e.lower() for e in errors)


class TestMCPAuth:
    """Tests for MCP authentication."""

    def test_auth_disabled_allows_all(self):
        """Test that disabled auth allows all requests."""
        from proofpack.mcp.auth import AuthHandler
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=False)
        handler = AuthHandler(config)

        with patch('sys.stdout'):
            result = handler.authenticate("", "client1")

        assert result.authenticated is True
        assert result.client_id == "client1"

    def test_auth_required_rejects_empty_token(self):
        """Test that empty token is rejected when auth required."""
        from proofpack.mcp.auth import AuthHandler
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=True, auth_token="secret")
        handler = AuthHandler(config)

        with patch('sys.stdout'):
            result = handler.authenticate("", "client1")

        assert result.authenticated is False
        assert "required" in result.error.lower()

    def test_auth_valid_token(self):
        """Test that valid token is accepted."""
        from proofpack.mcp.auth import AuthHandler
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=True, auth_token="secret123")
        handler = AuthHandler(config)

        with patch('sys.stdout'):
            result = handler.authenticate("secret123", "client1")

        assert result.authenticated is True

    def test_rate_limiting(self):
        """Test rate limiting enforcement."""
        from proofpack.mcp.auth import RateLimiter

        limiter = RateLimiter(requests_per_minute=2, burst=1)

        # First request should pass
        allowed, _ = limiter.check("client1")
        assert allowed is True
        limiter.record("client1")

        # Second should pass
        allowed, _ = limiter.check("client1")
        assert allowed is True
        limiter.record("client1")

        # Third should be rate limited
        allowed, retry_after = limiter.check("client1")
        assert allowed is False
        assert retry_after > 0


class TestMCPTools:
    """Tests for MCP tools."""

    def test_list_tools(self):
        """Test that tools are listed correctly."""
        from proofpack.mcp.tools import list_tools

        tools = list_tools()

        assert len(tools) > 0
        assert all("name" in t for t in tools)
        assert all("description" in t for t in tools)

        # Check expected tools exist
        tool_names = [t["name"] for t in tools]
        assert "query_receipts" in tool_names
        assert "validate_receipt" in tool_names
        assert "agent_status" in tool_names

    def test_get_tool(self):
        """Test getting individual tool."""
        from proofpack.mcp.tools import get_tool

        tool = get_tool("query_receipts")

        assert tool is not None
        assert tool.name == "query_receipts"
        assert callable(tool.handler)

    def test_execute_unknown_tool(self):
        """Test executing unknown tool returns error."""
        from proofpack.mcp.tools import execute_tool

        result = execute_tool("unknown_tool", {})

        assert result.success is False
        assert "unknown" in result.error.lower()


class TestMCPServer:
    """Tests for MCP server."""

    def test_server_initialization(self):
        """Test server can be initialized."""
        from proofpack.mcp.server import MCPServer
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=False)
        server = MCPServer(config)

        assert server._running is False
        assert server._request_count == 0

    def test_handle_initialize(self):
        """Test initialize request handling."""
        import asyncio
        from proofpack.mcp.server import MCPServer
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=False)
        server = MCPServer(config)

        with patch('sys.stdout'):
            response = asyncio.run(server.handle_request({
                "method": "initialize",
                "id": "1",
                "params": {
                    "clientInfo": {"name": "test-client"},
                    "protocolVersion": "1.0"
                }
            }))

        assert response["id"] == "1"
        assert "result" in response
        assert "serverInfo" in response["result"]

    def test_handle_list_tools(self):
        """Test tools/list request handling."""
        import asyncio
        from proofpack.mcp.server import MCPServer
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=False)
        server = MCPServer(config)

        response = asyncio.run(server.handle_request({
            "method": "tools/list",
            "id": "2",
            "params": {}
        }))

        assert response["id"] == "2"
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) > 0

    def test_handle_unknown_method(self):
        """Test unknown method returns error."""
        import asyncio
        from proofpack.mcp.server import MCPServer
        from proofpack.mcp.config import MCPConfig

        config = MCPConfig(auth_required=False)
        server = MCPServer(config)

        response = asyncio.run(server.handle_request({
            "method": "unknown/method",
            "id": "3",
            "params": {}
        }))

        assert "error" in response
        assert response["error"]["code"] == -32601
