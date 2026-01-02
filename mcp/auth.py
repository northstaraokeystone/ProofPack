"""Authentication handler for MCP clients.

Simple token-based authentication for MCP server.
Future versions may support OAuth or other auth methods.
"""
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Optional

from core.receipt import emit_receipt

from .config import MCPConfig


@dataclass
class AuthResult:
    """Result of authentication attempt."""
    authenticated: bool
    client_id: str
    error: Optional[str] = None
    scopes: list[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int, burst: int = 20):
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._requests: dict[str, list[float]] = {}

    def check(self, client_id: str) -> tuple[bool, int]:
        """Check if client is within rate limit.

        Returns (allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - 60  # 1 minute window

        if client_id not in self._requests:
            self._requests[client_id] = []

        # Clean old requests
        self._requests[client_id] = [
            t for t in self._requests[client_id]
            if t > window_start
        ]

        current_count = len(self._requests[client_id])

        if current_count >= self.requests_per_minute:
            oldest = self._requests[client_id][0]
            retry_after = int(oldest + 60 - now) + 1
            return False, retry_after

        # Check burst (last 10 seconds) - allow up to burst requests
        burst_window = now - 10
        burst_count = len([t for t in self._requests[client_id] if t > burst_window])
        if burst_count > self.burst:
            return False, 10

        return True, 0

    def record(self, client_id: str) -> None:
        """Record a request from client."""
        if client_id not in self._requests:
            self._requests[client_id] = []
        self._requests[client_id].append(time.time())


class AuthHandler:
    """Handles MCP client authentication."""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.rate_limiter = RateLimiter(
            config.rate_limit_per_minute,
            config.rate_limit_burst
        )
        self._active_sessions: dict[str, dict] = {}

    def authenticate(
        self,
        token: str,
        client_id: str = "",
    ) -> AuthResult:
        """Authenticate a client request.

        Args:
            token: Authentication token from client
            client_id: Client identifier (derived from token if not provided)

        Returns:
            AuthResult with authentication status
        """
        if not self.config.auth_required:
            return AuthResult(
                authenticated=True,
                client_id=client_id or "anonymous",
                scopes=["read", "write", "spawn"] if self.config.spawn_allowed else ["read", "write"]
            )

        if not token:
            emit_receipt("mcp_auth_failure", {
                "client_id": client_id or "unknown",
                "reason": "missing_token",
            })
            return AuthResult(
                authenticated=False,
                client_id="",
                error="Authentication token required"
            )

        # Verify token using constant-time comparison
        expected_token = self.config.auth_token
        if not hmac.compare_digest(token, expected_token):
            emit_receipt("mcp_auth_failure", {
                "client_id": client_id or "unknown",
                "reason": "invalid_token",
            })
            return AuthResult(
                authenticated=False,
                client_id="",
                error="Invalid authentication token"
            )

        # Generate client_id from token if not provided
        if not client_id:
            client_id = hashlib.sha256(token.encode()).hexdigest()[:16]

        # Check rate limit
        allowed, retry_after = self.rate_limiter.check(client_id)
        if not allowed:
            emit_receipt("mcp_rate_limited", {
                "client_id": client_id,
                "retry_after": retry_after,
            })
            return AuthResult(
                authenticated=False,
                client_id=client_id,
                error=f"Rate limited. Retry after {retry_after} seconds"
            )

        # Record successful request
        self.rate_limiter.record(client_id)

        # Determine scopes
        scopes = ["read", "write"]
        if self.config.spawn_allowed:
            scopes.append("spawn")

        emit_receipt("mcp_auth_success", {
            "client_id": client_id,
            "scopes": scopes,
        })

        return AuthResult(
            authenticated=True,
            client_id=client_id,
            scopes=scopes
        )

    def check_tool_access(
        self,
        client_id: str,
        tool_name: str,
        scopes: list[str],
    ) -> tuple[bool, str]:
        """Check if client has access to a tool.

        Args:
            client_id: Authenticated client ID
            tool_name: Name of tool being accessed
            scopes: Client's scopes from authentication

        Returns:
            (allowed, error_message)
        """
        # Check if tool is in allowed list
        if tool_name not in self.config.allowed_tools:
            return False, f"Tool '{tool_name}' is not available"

        # Check scope requirements
        if tool_name == "spawn_helper":
            if "spawn" not in scopes:
                return False, "Spawn scope required for spawn_helper tool"

        return True, ""

    def create_session(self, client_id: str) -> str:
        """Create a session for authenticated client.

        Returns session token for subsequent requests.
        """
        session_id = hashlib.sha256(
            f"{client_id}:{time.time()}".encode()
        ).hexdigest()[:32]

        self._active_sessions[session_id] = {
            "client_id": client_id,
            "created_at": time.time(),
            "last_request": time.time(),
        }

        return session_id

    def validate_session(self, session_id: str) -> Optional[str]:
        """Validate a session and return client_id if valid."""
        session = self._active_sessions.get(session_id)
        if not session:
            return None

        # Check session age (max 1 hour)
        if time.time() - session["created_at"] > 3600:
            del self._active_sessions[session_id]
            return None

        session["last_request"] = time.time()
        return session["client_id"]

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            return True
        return False
