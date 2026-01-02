"""MCP server configuration.

Configuration for the ProofPack MCP server. All settings can be
overridden via environment variables with PROOFPACK_MCP_ prefix.
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class MCPConfig:
    """MCP server configuration."""

    # Server settings
    port: int = 8765
    host: str = "127.0.0.1"
    max_connections: int = 10

    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20

    # Authentication
    auth_required: bool = True
    auth_token: str = ""

    # Tool access control
    allowed_tools: List[str] = field(default_factory=lambda: [
        "query_receipts",
        "validate_receipt",
        "get_lineage",
        "spawn_helper",
        "check_confidence",
        "list_patterns",
        "agent_status",
        "query_graph",
        "get_episode",
    ])

    # Spawning control (requires explicit enablement)
    spawn_allowed: bool = False
    spawn_max_depth: int = 3
    spawn_max_population: int = 50

    # Timeouts
    request_timeout_ms: int = 30000
    spawn_timeout_ms: int = 5000

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Load configuration from environment variables."""
        config = cls()

        # Server settings
        if "PROOFPACK_MCP_PORT" in os.environ:
            config.port = int(os.environ["PROOFPACK_MCP_PORT"])
        if "PROOFPACK_MCP_HOST" in os.environ:
            config.host = os.environ["PROOFPACK_MCP_HOST"]
        if "PROOFPACK_MCP_MAX_CONNECTIONS" in os.environ:
            config.max_connections = int(os.environ["PROOFPACK_MCP_MAX_CONNECTIONS"])

        # Rate limiting
        if "PROOFPACK_MCP_RATE_LIMIT" in os.environ:
            config.rate_limit_per_minute = int(os.environ["PROOFPACK_MCP_RATE_LIMIT"])

        # Authentication
        if "PROOFPACK_MCP_AUTH_REQUIRED" in os.environ:
            config.auth_required = os.environ["PROOFPACK_MCP_AUTH_REQUIRED"].lower() == "true"
        if "PROOFPACK_AUTH_TOKEN" in os.environ:
            config.auth_token = os.environ["PROOFPACK_AUTH_TOKEN"]

        # Spawning
        if "PROOFPACK_MCP_SPAWN_ALLOWED" in os.environ:
            config.spawn_allowed = os.environ["PROOFPACK_MCP_SPAWN_ALLOWED"].lower() == "true"

        return config

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of errors."""
        errors = []

        if self.port < 1 or self.port > 65535:
            errors.append(f"Invalid port: {self.port}")

        if self.max_connections < 1:
            errors.append(f"max_connections must be >= 1, got {self.max_connections}")

        if self.rate_limit_per_minute < 1:
            errors.append(f"rate_limit_per_minute must be >= 1, got {self.rate_limit_per_minute}")

        if self.auth_required and not self.auth_token:
            errors.append("auth_required=True but no auth_token configured")

        if self.spawn_max_depth < 1 or self.spawn_max_depth > 5:
            errors.append(f"spawn_max_depth must be 1-5, got {self.spawn_max_depth}")

        if self.spawn_max_population < 1 or self.spawn_max_population > 100:
            errors.append(f"spawn_max_population must be 1-100, got {self.spawn_max_population}")

        return errors


# Default configuration instance
DEFAULT_CONFIG = MCPConfig.from_env()
