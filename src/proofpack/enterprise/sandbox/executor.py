"""Sandbox Executor Module - Containerized execution for external tool calls.

Per CLAUDEME §13: All external tool calls must run in Docker container with:
- Network restricted to config/allowlist.json domains only
- Timeout: 30 seconds default, configurable per tool
- Resource limits: 512MB RAM, 1 CPU core
- Non-root user
- No host filesystem access

Stoprule: Network call to non-allowlisted domain → HALT + emit violation
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from proofpack.core.receipt import StopRule, dual_hash, emit_receipt

# Try to import docker, but allow graceful degradation for mock mode
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


# Default configuration
DEFAULT_TIMEOUT_S = 30
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_LIMIT = 1.0
CONTAINER_IMAGE = "python:3.11-slim"


@dataclass
class Allowlist:
    """Network allowlist configuration."""
    domains: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=lambda: ["https"])
    require_tls: bool = True
    max_request_size_bytes: int = 10485760  # 10MB
    timeout_seconds: int = 30


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    container_id: str
    exit_code: int
    stdout: bytes
    stderr: bytes
    duration_ms: int
    network_calls: list[dict] = field(default_factory=list)
    receipt: dict | None = None


def load_allowlist(path: str = "config/allowlist.json") -> Allowlist:
    """Load network allowlist from JSON file.

    Args:
        path: Path to allowlist.json

    Returns:
        Allowlist configuration

    If file doesn't exist, returns empty allowlist.
    """
    allowlist_path = Path(path)

    if not allowlist_path.exists():
        return Allowlist()

    try:
        with open(allowlist_path) as f:
            data = json.load(f)

        return Allowlist(
            domains=data.get("domains", []),
            protocols=data.get("protocols", ["https"]),
            require_tls=data.get("require_tls", True),
            max_request_size_bytes=data.get("max_request_size_bytes", 10485760),
            timeout_seconds=data.get("timeout_seconds", 30)
        )
    except (OSError, json.JSONDecodeError):
        return Allowlist()


def validate_network_call(domain: str, allowlist: list[str] | Allowlist) -> bool:
    """Validate if domain is in allowlist.

    Args:
        domain: Domain to validate (e.g., "api.usaspending.gov")
        allowlist: List of allowed domains or Allowlist object

    Returns:
        True if domain is allowed, False otherwise
    """
    if isinstance(allowlist, Allowlist):
        allowed_domains = allowlist.domains
    else:
        allowed_domains = allowlist

    # Normalize domain (remove port, lowercase)
    normalized = domain.lower().split(":")[0]

    for allowed in allowed_domains:
        allowed_normalized = allowed.lower()
        # Exact match or subdomain match
        if normalized == allowed_normalized:
            return True
        if normalized.endswith("." + allowed_normalized):
            return True

    return False


def execute_in_sandbox(
    tool_name: str,
    command: str,
    params: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
    allowlist_path: str = "config/allowlist.json",
    tenant_id: str = "default",
    mock_mode: bool = False
) -> SandboxResult:
    """Execute command in sandboxed Docker container.

    Per CLAUDEME §13: All external tool calls run in container.

    Args:
        tool_name: Name of the tool being executed
        command: Command to run in container
        params: Optional parameters dict
        timeout: Timeout in seconds (default 30)
        allowlist_path: Path to allowlist.json
        tenant_id: Tenant identifier
        mock_mode: If True, simulate execution without Docker

    Returns:
        SandboxResult with output and receipt

    Raises:
        StopRule: If network violation detected
    """
    container_id = f"sandbox-{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    # Load allowlist
    allowlist = load_allowlist(allowlist_path)

    # Prepare input
    input_data = json.dumps({
        "command": command,
        "params": params or {}
    }).encode()

    network_calls: list[dict] = []

    if mock_mode or not DOCKER_AVAILABLE:
        # Mock execution for development/testing
        result = _mock_execute(command, params, timeout)
        stdout = result.get("stdout", b"")
        stderr = result.get("stderr", b"")
        exit_code = result.get("exit_code", 0)
        network_calls = result.get("network_calls", [])
    else:
        # Real Docker execution
        stdout, stderr, exit_code, network_calls = _docker_execute(
            command, params, timeout, allowlist
        )

    # Check network calls against allowlist
    for call in network_calls:
        domain = call.get("domain", "")
        allowed = validate_network_call(domain, allowlist)
        call["allowed"] = allowed

        if not allowed:
            # Emit violation and HALT
            stoprule_network_violation(domain, tool_name, tenant_id)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Emit receipt
    receipt = emit_sandbox_receipt(
        tool_name=tool_name,
        container_id=container_id,
        input_data=input_data,
        output_data=stdout,
        exit_code=exit_code,
        duration_ms=duration_ms,
        network_calls=network_calls,
        tenant_id=tenant_id
    )

    return SandboxResult(
        success=exit_code == 0,
        container_id=container_id,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        network_calls=network_calls,
        receipt=receipt
    )


def _mock_execute(
    command: str,
    params: dict | None,
    timeout: int
) -> dict:
    """Mock execution for testing without Docker.

    Returns simulated output based on command.
    """
    # Simulate execution
    time.sleep(0.01)  # Small delay to simulate work

    # Parse command to detect potential network calls
    network_calls = []
    if "http://" in command or "https://" in command:
        # Extract domain from command
        import re
        urls = re.findall(r'https?://([^/\s]+)', command)
        for url in urls:
            network_calls.append({"domain": url})

    return {
        "stdout": f"Mock execution of: {command}".encode(),
        "stderr": b"",
        "exit_code": 0,
        "network_calls": network_calls
    }


def _docker_execute(
    command: str,
    params: dict | None,
    timeout: int,
    allowlist: Allowlist
) -> tuple[bytes, bytes, int, list[dict]]:
    """Execute command in real Docker container.

    Returns (stdout, stderr, exit_code, network_calls)
    """
    if not DOCKER_AVAILABLE:
        raise RuntimeError("Docker SDK not available")

    client = docker.from_env()

    # Configure container
    container_config = {
        "image": CONTAINER_IMAGE,
        "command": ["python", "-c", command],
        "detach": True,
        "mem_limit": DEFAULT_MEMORY_LIMIT,
        "cpu_period": 100000,
        "cpu_quota": int(DEFAULT_CPU_LIMIT * 100000),
        "network_mode": "none",  # No network by default
        "user": "nobody",  # Non-root user
        "read_only": True,  # Read-only filesystem
    }

    # If allowlist has domains, create restricted network
    # For now, we use network_mode="none" and mock network calls

    try:
        container = client.containers.run(**container_config)

        # Wait for completion with timeout
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            container.stop(timeout=1)
            exit_code = -1

        # Get logs
        stdout = container.logs(stdout=True, stderr=False)
        stderr = container.logs(stdout=False, stderr=True)

        # Clean up
        container.remove()

    except docker.errors.ContainerError as e:
        stdout = e.stderr or b""
        stderr = str(e).encode()
        exit_code = e.exit_status

    except Exception as e:
        stdout = b""
        stderr = str(e).encode()
        exit_code = -1

    # Network calls would be tracked via container networking
    # For now, return empty list (network is disabled)
    network_calls: list[dict] = []

    return stdout, stderr, exit_code, network_calls


def emit_sandbox_receipt(
    tool_name: str,
    container_id: str,
    input_data: bytes,
    output_data: bytes,
    exit_code: int,
    duration_ms: int,
    network_calls: list[dict],
    tenant_id: str = "default"
) -> dict:
    """Emit sandbox execution receipt.

    Per CLAUDEME §13: Every sandbox execution emits receipt.

    Args:
        tool_name: Name of executed tool
        container_id: Docker container ID
        input_data: Input bytes
        output_data: Output bytes
        exit_code: Container exit code
        duration_ms: Execution duration
        network_calls: List of network calls made
        tenant_id: Tenant identifier

    Returns:
        Sandbox execution receipt dict
    """
    return emit_receipt("sandbox_execution", {
        "tenant_id": tenant_id,
        "tool_name": tool_name,
        "container_id": container_id,
        "input_hash": dual_hash(input_data),
        "output_hash": dual_hash(output_data),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "network_calls": network_calls
    })


def stoprule_network_violation(domain: str, tool_name: str, tenant_id: str = "default"):
    """HALT on network call to non-allowlisted domain.

    Per CLAUDEME §13: Non-allowlisted domain → HALT + emit violation.
    """
    emit_receipt("anomaly", {
        "tenant_id": tenant_id,
        "metric": "network_violation",
        "baseline": 0,
        "delta": -1,
        "classification": "violation",
        "action": "halt",
        "details": {
            "domain": domain,
            "tool_name": tool_name
        }
    })
    raise StopRule(
        f"Network violation in sandbox: {tool_name} attempted to call "
        f"non-allowlisted domain '{domain}'"
    )
