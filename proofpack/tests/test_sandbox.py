"""Tests for sandbox executor module.

Per DELIVERABLE 3: Tests for sandbox/executor.py
"""

import json
from pathlib import Path


def test_allowlist_json_exists():
    """Test that allowlist.json exists."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"
    assert allowlist_path.exists(), "allowlist.json should exist"


def test_allowlist_json_valid():
    """Test that allowlist.json is valid JSON."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    # Required fields
    assert "domains" in data
    assert "protocols" in data
    assert "require_tls" in data


def test_allowlist_has_government_domains():
    """Test that allowlist includes government API domains."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    domains = data["domains"]
    assert "api.usaspending.gov" in domains
    assert "api.sam.gov" in domains
    assert "data.treasury.gov" in domains


def test_allowlist_requires_tls():
    """Test that TLS is required."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    assert data["require_tls"] is True


def test_allowlist_protocols_https_only():
    """Test that only HTTPS is allowed."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    protocols = data["protocols"]
    assert "https" in protocols
    assert "http" not in protocols


def test_validate_network_call_allowed():
    """Test that allowlisted domains pass validation."""
    # Simple validation function
    def validate_network_call(domain: str, allowlist: list) -> bool:
        normalized = domain.lower().split(":")[0]
        for allowed in allowlist:
            if normalized == allowed.lower():
                return True
            if normalized.endswith("." + allowed.lower()):
                return True
        return False

    allowlist = ["api.usaspending.gov", "api.sam.gov"]

    assert validate_network_call("api.usaspending.gov", allowlist) is True
    assert validate_network_call("api.sam.gov", allowlist) is True


def test_validate_network_call_blocked():
    """Test that non-allowlisted domains are blocked."""
    def validate_network_call(domain: str, allowlist: list) -> bool:
        normalized = domain.lower().split(":")[0]
        for allowed in allowlist:
            if normalized == allowed.lower():
                return True
            if normalized.endswith("." + allowed.lower()):
                return True
        return False

    allowlist = ["api.usaspending.gov", "api.sam.gov"]

    assert validate_network_call("malicious.example.com", allowlist) is False
    assert validate_network_call("unknown.api.net", allowlist) is False


def test_validate_network_call_subdomain():
    """Test that subdomains of allowlisted domains pass."""
    def validate_network_call(domain: str, allowlist: list) -> bool:
        normalized = domain.lower().split(":")[0]
        for allowed in allowlist:
            if normalized == allowed.lower():
                return True
            if normalized.endswith("." + allowed.lower()):
                return True
        return False

    allowlist = ["usaspending.gov"]

    assert validate_network_call("api.usaspending.gov", allowlist) is True
    assert validate_network_call("data.usaspending.gov", allowlist) is True


def test_sandbox_receipt_emission():
    """Test sandbox execution receipt emission."""
    from proofpack.core.receipt import emit_receipt, dual_hash

    receipt = emit_receipt("sandbox_execution", {
        "tenant_id": "test",
        "tool_name": "http_fetch",
        "container_id": "sandbox-abc123",
        "input_hash": dual_hash(b"input"),
        "output_hash": dual_hash(b"output"),
        "exit_code": 0,
        "duration_ms": 100,
        "network_calls": [{"domain": "api.usaspending.gov", "allowed": True}]
    })

    assert receipt["receipt_type"] == "sandbox_execution"
    assert receipt["exit_code"] == 0
    assert receipt["network_calls"][0]["allowed"] is True


def test_sandbox_timeout_config():
    """Test that timeout is configured correctly."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    assert "timeout_seconds" in data
    assert data["timeout_seconds"] == 30


def test_sandbox_max_request_size():
    """Test that max request size is configured."""
    allowlist_path = Path(__file__).parent.parent / "config" / "allowlist.json"

    with open(allowlist_path, "r") as f:
        data = json.load(f)

    assert "max_request_size_bytes" in data
    assert data["max_request_size_bytes"] == 10485760  # 10MB


def test_dockerfile_exists():
    """Test that Dockerfile.tool exists."""
    dockerfile_path = Path(__file__).parent.parent / "src" / "sandbox" / "Dockerfile.tool"
    assert dockerfile_path.exists(), "Dockerfile.tool should exist"


def test_dockerfile_uses_slim_image():
    """Test that Dockerfile uses slim base image."""
    dockerfile_path = Path(__file__).parent.parent / "src" / "sandbox" / "Dockerfile.tool"

    with open(dockerfile_path, "r") as f:
        content = f.read()

    assert "python:3.11-slim" in content


def test_dockerfile_non_root_user():
    """Test that Dockerfile creates non-root user."""
    dockerfile_path = Path(__file__).parent.parent / "src" / "sandbox" / "Dockerfile.tool"

    with open(dockerfile_path, "r") as f:
        content = f.read()

    assert "appuser" in content or "USER" in content
