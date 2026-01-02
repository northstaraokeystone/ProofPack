"""Sandbox execution module for containerized tool calls.

Provides:
    - execute_in_sandbox: Run commands in Docker container
    - validate_network_call: Check domain against allowlist
    - emit_sandbox_receipt: Emit sandbox execution receipt
    - SandboxResult: Result of sandbox execution
"""

from .executor import (
    SandboxResult,
    execute_in_sandbox,
    validate_network_call,
    emit_sandbox_receipt,
    load_allowlist,
)

__all__ = [
    "SandboxResult",
    "execute_in_sandbox",
    "validate_network_call",
    "emit_sandbox_receipt",
    "load_allowlist",
]
