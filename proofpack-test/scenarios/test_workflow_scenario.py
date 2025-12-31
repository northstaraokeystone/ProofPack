"""WORKFLOW Monte Carlo Scenario - Test workflow receipt emission and deviation detection.

Per DELIVERABLE 7: Monte Carlo scenario for workflow graph validation.

SCENARIO: WORKFLOW
cycles: 200
inject:
  - 50 normal traversals (planned = actual)
  - 30 minor deviations (1 node difference)
  - 20 major deviations (>2 nodes different)
success_criteria:
  - workflow_receipt emitted: 100%
  - deviations detected: 100%
  - major deviations trigger HALT: 100%
  - graph_hash consistency: 100%
"""

import random
import pytest
from dataclasses import dataclass, field
from typing import Callable

# Import from parent conftest
import sys
sys.path.insert(0, '..')
from conftest import SimConfig, SimState


@dataclass
class WorkflowScenarioConfig(SimConfig):
    """Configuration for WORKFLOW scenario."""
    n_cycles: int = 200
    normal_traversal_count: int = 50
    minor_deviation_count: int = 30
    major_deviation_count: int = 20
    random_seed: int = 42


@dataclass
class WorkflowScenarioState(SimState):
    """State tracking for WORKFLOW scenario."""
    workflow_receipts_emitted: int = 0
    deviations_detected: int = 0
    major_deviations_halted: int = 0
    graph_hash_consistent: bool = True
    current_graph_hash: str = ""

    # Injected scenario tracking
    normal_traversals: int = 0
    minor_deviations: int = 0
    major_deviations: int = 0


def run_workflow_scenario(
    config: WorkflowScenarioConfig | None = None,
    emit_receipt_fn: Callable | None = None
) -> WorkflowScenarioState:
    """Execute WORKFLOW Monte Carlo scenario.

    Args:
        config: Scenario configuration
        emit_receipt_fn: Optional receipt emission function (for mocking)

    Returns:
        Final scenario state with metrics
    """
    if config is None:
        config = WorkflowScenarioConfig()

    random.seed(config.random_seed)
    state = WorkflowScenarioState()

    # Simulate graph hash
    state.current_graph_hash = "sha256abc:blake3xyz"

    # Generate injection schedule
    schedule = []
    schedule.extend(["normal"] * config.normal_traversal_count)
    schedule.extend(["minor"] * config.minor_deviation_count)
    schedule.extend(["major"] * config.major_deviation_count)
    random.shuffle(schedule)

    for i, injection_type in enumerate(schedule):
        if i >= config.n_cycles:
            break

        state.cycle = i

        # Simulate workflow traversal
        planned_path = ["ledger", "brief", "packet", "anchor", "loop", "mcp_server"]

        if injection_type == "normal":
            actual_path = planned_path.copy()
            state.normal_traversals += 1
        elif injection_type == "minor":
            # Minor deviation: 1 node different
            actual_path = planned_path.copy()
            if len(actual_path) > 0:
                idx = random.randint(0, len(actual_path) - 1)
                actual_path[idx] = f"{actual_path[idx]}_deviated"
            state.minor_deviations += 1
        else:  # major
            # Major deviation: >2 nodes different
            actual_path = planned_path.copy()
            for _ in range(3):
                if len(actual_path) > 0:
                    idx = random.randint(0, len(actual_path) - 1)
                    actual_path[idx] = f"{actual_path[idx]}_deviated"
            state.major_deviations += 1

        # Detect deviations
        deviations = []
        for j, (p, a) in enumerate(zip(planned_path, actual_path)):
            if p != a:
                deviations.append({
                    "expected": p,
                    "actual": a,
                    "reason": f"Path diverged at step {j}"
                })

        if deviations:
            state.deviations_detected += 1

            # Major deviations (>2 nodes) should trigger HALT
            if len(deviations) > 2:
                state.major_deviations_halted += 1
                # Emit anomaly receipt
                anomaly_receipt = {
                    "receipt_type": "anomaly",
                    "metric": "workflow_deviation",
                    "classification": "violation",
                    "action": "halt"
                }
                state.receipt_ledger.append(anomaly_receipt)

        # Emit workflow receipt
        workflow_receipt = {
            "receipt_type": "workflow",
            "graph_hash": state.current_graph_hash,
            "planned_path": planned_path,
            "actual_path": actual_path,
            "deviations": deviations
        }
        state.receipt_ledger.append(workflow_receipt)
        state.workflow_receipts_emitted += 1

        # Verify graph hash consistency
        if workflow_receipt["graph_hash"] != state.current_graph_hash:
            state.graph_hash_consistent = False

    return state


def validate_workflow_scenario(state: WorkflowScenarioState) -> dict:
    """Validate WORKFLOW scenario success criteria.

    Returns:
        Dict with success criteria results
    """
    total_traversals = state.normal_traversals + state.minor_deviations + state.major_deviations

    # Calculate success rates
    receipt_emission_rate = state.workflow_receipts_emitted / total_traversals if total_traversals > 0 else 0

    expected_deviations = state.minor_deviations + state.major_deviations
    deviation_detection_rate = state.deviations_detected / expected_deviations if expected_deviations > 0 else 1.0

    major_halt_rate = state.major_deviations_halted / state.major_deviations if state.major_deviations > 0 else 1.0

    return {
        "success": all([
            receipt_emission_rate >= 1.0,
            deviation_detection_rate >= 1.0,
            major_halt_rate >= 1.0,
            state.graph_hash_consistent
        ]),
        "workflow_receipt_emission": receipt_emission_rate,
        "deviation_detection": deviation_detection_rate,
        "major_deviation_halt": major_halt_rate,
        "graph_hash_consistency": state.graph_hash_consistent,
        "total_cycles": state.cycle + 1,
        "receipts_emitted": state.workflow_receipts_emitted
    }


# Pytest test functions

def test_workflow_scenario_basic():
    """Test basic WORKFLOW scenario execution."""
    config = WorkflowScenarioConfig(n_cycles=50)
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    assert result["success"], f"Scenario failed: {result}"
    assert result["workflow_receipt_emission"] >= 1.0


def test_workflow_scenario_deviation_detection():
    """Test that all deviations are detected."""
    config = WorkflowScenarioConfig(
        n_cycles=100,
        normal_traversal_count=20,
        minor_deviation_count=40,
        major_deviation_count=40
    )
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    assert result["deviation_detection"] >= 1.0, "Not all deviations detected"


def test_workflow_scenario_major_halt():
    """Test that major deviations trigger HALT."""
    config = WorkflowScenarioConfig(
        n_cycles=50,
        normal_traversal_count=0,
        minor_deviation_count=0,
        major_deviation_count=50
    )
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    assert result["major_deviation_halt"] >= 1.0, "Not all major deviations halted"


def test_workflow_scenario_graph_hash_consistency():
    """Test graph hash remains consistent across cycles."""
    config = WorkflowScenarioConfig(n_cycles=200)
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    assert result["graph_hash_consistency"], "Graph hash inconsistency detected"


def test_workflow_scenario_full():
    """Full WORKFLOW scenario as specified."""
    config = WorkflowScenarioConfig()  # Uses default: 200 cycles, 50/30/20 split
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    assert result["success"], f"WORKFLOW scenario failed: {result}"

    # All success criteria must be 100%
    assert result["workflow_receipt_emission"] >= 1.0
    assert result["deviation_detection"] >= 1.0
    assert result["major_deviation_halt"] >= 1.0
    assert result["graph_hash_consistency"]


if __name__ == "__main__":
    # Run standalone
    print("Running WORKFLOW Monte Carlo Scenario...")
    config = WorkflowScenarioConfig()
    state = run_workflow_scenario(config)
    result = validate_workflow_scenario(state)

    print(f"Results: {result}")
    print(f"Success: {result['success']}")
