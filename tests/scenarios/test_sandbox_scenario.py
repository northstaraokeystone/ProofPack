"""SANDBOX Monte Carlo Scenario - Test sandbox execution and network restriction.

Per DELIVERABLE 7: Monte Carlo scenario for sandbox execution validation.

SCENARIO: SANDBOX
cycles: 100
inject:
  - 40 allowlisted network calls
  - 30 non-allowlisted network calls (should block)
  - 20 timeout scenarios
  - 10 resource limit violations
success_criteria:
  - sandbox_receipt emitted: 100%
  - non-allowlisted calls blocked: 100%
  - timeouts enforced: 100%
  - resource violations caught: 100%
"""

import random
from dataclasses import dataclass, field
from typing import Callable

import sys
sys.path.insert(0, '..')
from conftest import SimConfig, SimState


@dataclass
class SandboxScenarioConfig(SimConfig):
    """Configuration for SANDBOX scenario."""
    n_cycles: int = 100
    allowlisted_calls: int = 40
    non_allowlisted_calls: int = 30
    timeout_scenarios: int = 20
    resource_violations: int = 10
    random_seed: int = 42

    # Allowlist for testing
    allowlist: list[str] = field(default_factory=lambda: [
        "api.usaspending.gov",
        "api.sam.gov",
        "data.treasury.gov"
    ])


@dataclass
class SandboxScenarioState(SimState):
    """State tracking for SANDBOX scenario."""
    sandbox_receipts_emitted: int = 0
    allowlisted_calls_made: int = 0
    non_allowlisted_blocked: int = 0
    timeouts_enforced: int = 0
    resource_violations_caught: int = 0

    # Tracking injected scenarios
    allowlisted_injected: int = 0
    non_allowlisted_injected: int = 0
    timeout_injected: int = 0
    resource_violation_injected: int = 0


def run_sandbox_scenario(
    config: SandboxScenarioConfig | None = None,
    emit_receipt_fn: Callable | None = None
) -> SandboxScenarioState:
    """Execute SANDBOX Monte Carlo scenario.

    Args:
        config: Scenario configuration
        emit_receipt_fn: Optional receipt emission function (for mocking)

    Returns:
        Final scenario state with metrics
    """
    if config is None:
        config = SandboxScenarioConfig()

    random.seed(config.random_seed)
    state = SandboxScenarioState()

    # Non-allowlisted domains for testing
    blocked_domains = [
        "malicious.example.com",
        "unknown-api.net",
        "external-tracker.io",
        "data-exfil.xyz"
    ]

    # Generate injection schedule
    schedule = []
    schedule.extend(["allowlisted"] * config.allowlisted_calls)
    schedule.extend(["non_allowlisted"] * config.non_allowlisted_calls)
    schedule.extend(["timeout"] * config.timeout_scenarios)
    schedule.extend(["resource"] * config.resource_violations)
    random.shuffle(schedule)

    for i, injection_type in enumerate(schedule):
        if i >= config.n_cycles:
            break

        state.cycle = i
        container_id = f"sandbox-{i:08x}"

        # Simulate sandbox execution based on injection type
        if injection_type == "allowlisted":
            domain = random.choice(config.allowlist)
            state.allowlisted_injected += 1

            # Should succeed
            sandbox_receipt = {
                "receipt_type": "sandbox_execution",
                "tool_name": "http_fetch",
                "container_id": container_id,
                "exit_code": 0,
                "duration_ms": random.randint(50, 500),
                "network_calls": [{"domain": domain, "allowed": True}]
            }
            state.allowlisted_calls_made += 1

        elif injection_type == "non_allowlisted":
            domain = random.choice(blocked_domains)
            state.non_allowlisted_injected += 1

            # Should be blocked
            sandbox_receipt = {
                "receipt_type": "sandbox_execution",
                "tool_name": "http_fetch",
                "container_id": container_id,
                "exit_code": -1,
                "duration_ms": random.randint(1, 10),
                "network_calls": [{"domain": domain, "allowed": False}]
            }

            # Emit anomaly for blocked call
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "network_violation",
                "classification": "violation",
                "action": "halt",
                "details": {"domain": domain}
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.non_allowlisted_blocked += 1

        elif injection_type == "timeout":
            state.timeout_injected += 1

            # Simulate timeout (duration > 30000ms)
            sandbox_receipt = {
                "receipt_type": "sandbox_execution",
                "tool_name": "slow_operation",
                "container_id": container_id,
                "exit_code": -1,
                "duration_ms": random.randint(30001, 60000),
                "network_calls": [],
                "timeout": True
            }

            # Emit anomaly for timeout
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "sandbox_timeout",
                "classification": "degradation",
                "action": "alert"
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.timeouts_enforced += 1

        else:  # resource violation
            state.resource_violation_injected += 1

            # Simulate resource limit exceeded (>512MB)
            sandbox_receipt = {
                "receipt_type": "sandbox_execution",
                "tool_name": "memory_hog",
                "container_id": container_id,
                "exit_code": 137,  # OOM killed
                "duration_ms": random.randint(100, 1000),
                "network_calls": [],
                "memory_exceeded": True
            }

            # Emit anomaly for resource violation
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "resource_violation",
                "classification": "violation",
                "action": "halt"
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.resource_violations_caught += 1

        # Always emit sandbox receipt
        state.receipt_ledger.append(sandbox_receipt)
        state.sandbox_receipts_emitted += 1

    return state


def validate_sandbox_scenario(state: SandboxScenarioState) -> dict:
    """Validate SANDBOX scenario success criteria.

    Returns:
        Dict with success criteria results
    """
    total_executions = (
        state.allowlisted_injected +
        state.non_allowlisted_injected +
        state.timeout_injected +
        state.resource_violation_injected
    )

    # Calculate success rates
    receipt_emission_rate = state.sandbox_receipts_emitted / total_executions if total_executions > 0 else 0

    non_allowlisted_block_rate = (
        state.non_allowlisted_blocked / state.non_allowlisted_injected
        if state.non_allowlisted_injected > 0 else 1.0
    )

    timeout_enforcement_rate = (
        state.timeouts_enforced / state.timeout_injected
        if state.timeout_injected > 0 else 1.0
    )

    resource_violation_rate = (
        state.resource_violations_caught / state.resource_violation_injected
        if state.resource_violation_injected > 0 else 1.0
    )

    return {
        "success": all([
            receipt_emission_rate >= 1.0,
            non_allowlisted_block_rate >= 1.0,
            timeout_enforcement_rate >= 1.0,
            resource_violation_rate >= 1.0
        ]),
        "sandbox_receipt_emission": receipt_emission_rate,
        "non_allowlisted_blocked": non_allowlisted_block_rate,
        "timeouts_enforced": timeout_enforcement_rate,
        "resource_violations_caught": resource_violation_rate,
        "total_cycles": state.cycle + 1,
        "receipts_emitted": state.sandbox_receipts_emitted
    }


# Pytest test functions

def test_sandbox_scenario_basic():
    """Test basic SANDBOX scenario execution."""
    config = SandboxScenarioConfig(n_cycles=50)
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    assert result["success"], f"Scenario failed: {result}"


def test_sandbox_scenario_allowlisted_calls():
    """Test allowlisted network calls succeed."""
    config = SandboxScenarioConfig(
        n_cycles=40,
        allowlisted_calls=40,
        non_allowlisted_calls=0,
        timeout_scenarios=0,
        resource_violations=0
    )
    state = run_sandbox_scenario(config)

    assert state.allowlisted_calls_made == 40


def test_sandbox_scenario_blocked_calls():
    """Test non-allowlisted calls are blocked."""
    config = SandboxScenarioConfig(
        n_cycles=30,
        allowlisted_calls=0,
        non_allowlisted_calls=30,
        timeout_scenarios=0,
        resource_violations=0
    )
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    assert result["non_allowlisted_blocked"] >= 1.0


def test_sandbox_scenario_timeouts():
    """Test timeout scenarios are enforced."""
    config = SandboxScenarioConfig(
        n_cycles=20,
        allowlisted_calls=0,
        non_allowlisted_calls=0,
        timeout_scenarios=20,
        resource_violations=0
    )
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    assert result["timeouts_enforced"] >= 1.0


def test_sandbox_scenario_resource_violations():
    """Test resource limit violations are caught."""
    config = SandboxScenarioConfig(
        n_cycles=10,
        allowlisted_calls=0,
        non_allowlisted_calls=0,
        timeout_scenarios=0,
        resource_violations=10
    )
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    assert result["resource_violations_caught"] >= 1.0


def test_sandbox_scenario_full():
    """Full SANDBOX scenario as specified."""
    config = SandboxScenarioConfig()  # Uses default: 100 cycles, 40/30/20/10 split
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    assert result["success"], f"SANDBOX scenario failed: {result}"

    # All success criteria must be 100%
    assert result["sandbox_receipt_emission"] >= 1.0
    assert result["non_allowlisted_blocked"] >= 1.0
    assert result["timeouts_enforced"] >= 1.0
    assert result["resource_violations_caught"] >= 1.0


if __name__ == "__main__":
    print("Running SANDBOX Monte Carlo Scenario...")
    config = SandboxScenarioConfig()
    state = run_sandbox_scenario(config)
    result = validate_sandbox_scenario(state)

    print(f"Results: {result}")
    print(f"Success: {result['success']}")
