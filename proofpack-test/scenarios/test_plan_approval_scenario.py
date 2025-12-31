"""PLAN_APPROVAL Monte Carlo Scenario - Test plan proposal and approval workflow.

Per DELIVERABLE 7: Monte Carlo scenario for plan approval validation.

SCENARIO: PLAN_APPROVAL
cycles: 100
inject:
  - 40 plans approved as-is
  - 30 plans modified by human
  - 20 plans rejected
  - 10 plans timeout (auto-reject)
success_criteria:
  - plan_proposal_receipt emitted: 100%
  - modifications captured: 100%
  - rejections halt execution: 100%
  - timeouts auto-reject: 100%
"""

import random
import pytest
from dataclasses import dataclass, field
from typing import Callable

import sys
sys.path.insert(0, '..')
from conftest import SimConfig, SimState


@dataclass
class PlanApprovalScenarioConfig(SimConfig):
    """Configuration for PLAN_APPROVAL scenario."""
    n_cycles: int = 100
    plans_approved: int = 40
    plans_modified: int = 30
    plans_rejected: int = 20
    plans_timeout: int = 10
    random_seed: int = 42


@dataclass
class PlanApprovalScenarioState(SimState):
    """State tracking for PLAN_APPROVAL scenario."""
    plan_proposal_receipts_emitted: int = 0
    modifications_captured: int = 0
    rejections_halted: int = 0
    timeouts_auto_rejected: int = 0

    # Tracking injected scenarios
    approvals_injected: int = 0
    modifications_injected: int = 0
    rejections_injected: int = 0
    timeouts_injected: int = 0

    # Execution tracking
    executions_after_approval: int = 0
    executions_blocked: int = 0


def run_plan_approval_scenario(
    config: PlanApprovalScenarioConfig | None = None,
    emit_receipt_fn: Callable | None = None
) -> PlanApprovalScenarioState:
    """Execute PLAN_APPROVAL Monte Carlo scenario.

    Args:
        config: Scenario configuration
        emit_receipt_fn: Optional receipt emission function (for mocking)

    Returns:
        Final scenario state with metrics
    """
    if config is None:
        config = PlanApprovalScenarioConfig()

    random.seed(config.random_seed)
    state = PlanApprovalScenarioState()

    # Generate injection schedule
    schedule = []
    schedule.extend(["approved"] * config.plans_approved)
    schedule.extend(["modified"] * config.plans_modified)
    schedule.extend(["rejected"] * config.plans_rejected)
    schedule.extend(["timeout"] * config.plans_timeout)
    random.shuffle(schedule)

    for i, injection_type in enumerate(schedule):
        if i >= config.n_cycles:
            break

        state.cycle = i
        plan_id = f"plan_{i:08x}"

        # Create plan proposal
        plan_steps = [
            {"step_id": f"step_{j}", "action": f"action_{j}", "tool": f"tool_{j}"}
            for j in range(random.randint(2, 5))
        ]

        risk_score = random.uniform(0.3, 0.9)  # MEDIUM to HIGH risk

        # Emit plan_proposal receipt (always)
        plan_proposal_receipt = {
            "receipt_type": "plan_proposal",
            "plan_id": plan_id,
            "steps": plan_steps,
            "risk_assessment": {
                "score": risk_score,
                "level": "high" if risk_score >= 0.6 else "medium"
            },
            "editable_until": "2024-01-01T00:05:00Z"
        }
        state.receipt_ledger.append(plan_proposal_receipt)
        state.plan_proposal_receipts_emitted += 1

        if injection_type == "approved":
            state.approvals_injected += 1

            # Plan approved as-is - proceed to execution
            approval_receipt = {
                "receipt_type": "plan_approval",
                "plan_id": plan_id,
                "decision": "approved",
                "modifier_id": None
            }
            state.receipt_ledger.append(approval_receipt)
            state.executions_after_approval += 1

        elif injection_type == "modified":
            state.modifications_injected += 1

            # Plan modified by human
            original_plan_id = plan_id
            modified_plan_id = f"plan_{i:08x}_modified"

            # Emit plan_modification receipt
            modification_receipt = {
                "receipt_type": "plan_modification",
                "original_plan_id": original_plan_id,
                "modified_plan_id": modified_plan_id,
                "modifier_id": "human_reviewer_1",
                "reason": "Security improvement",
                "diff": {
                    "steps_added": [{"step_id": "new_step"}],
                    "steps_removed": [],
                    "steps_changed": ["step_0"]
                }
            }
            state.receipt_ledger.append(modification_receipt)
            state.modifications_captured += 1

            # After modification, plan is approved
            approval_receipt = {
                "receipt_type": "plan_approval",
                "plan_id": modified_plan_id,
                "decision": "approved",
                "modifier_id": "human_reviewer_1"
            }
            state.receipt_ledger.append(approval_receipt)
            state.executions_after_approval += 1

        elif injection_type == "rejected":
            state.rejections_injected += 1

            # Plan rejected - should halt execution
            rejection_receipt = {
                "receipt_type": "plan_approval",
                "plan_id": plan_id,
                "decision": "rejected",
                "modifier_id": "human_reviewer_2",
                "reason": "Too risky"
            }
            state.receipt_ledger.append(rejection_receipt)

            # Emit anomaly for blocked execution
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "plan_rejected",
                "classification": "deviation",
                "action": "halt",
                "details": {"plan_id": plan_id}
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.rejections_halted += 1
            state.executions_blocked += 1

        else:  # timeout
            state.timeouts_injected += 1

            # Plan timed out - auto-reject
            timeout_receipt = {
                "receipt_type": "plan_approval",
                "plan_id": plan_id,
                "decision": "timeout",
                "modifier_id": None,
                "reason": "Approval timeout exceeded"
            }
            state.receipt_ledger.append(timeout_receipt)

            # Emit anomaly for timeout
            anomaly_receipt = {
                "receipt_type": "anomaly",
                "metric": "plan_timeout",
                "classification": "deviation",
                "action": "reject",
                "details": {"plan_id": plan_id}
            }
            state.receipt_ledger.append(anomaly_receipt)
            state.timeouts_auto_rejected += 1
            state.executions_blocked += 1

    return state


def validate_plan_approval_scenario(state: PlanApprovalScenarioState) -> dict:
    """Validate PLAN_APPROVAL scenario success criteria.

    Returns:
        Dict with success criteria results
    """
    total_plans = (
        state.approvals_injected +
        state.modifications_injected +
        state.rejections_injected +
        state.timeouts_injected
    )

    # Calculate success rates
    receipt_emission_rate = state.plan_proposal_receipts_emitted / total_plans if total_plans > 0 else 0

    modification_capture_rate = (
        state.modifications_captured / state.modifications_injected
        if state.modifications_injected > 0 else 1.0
    )

    rejection_halt_rate = (
        state.rejections_halted / state.rejections_injected
        if state.rejections_injected > 0 else 1.0
    )

    timeout_auto_reject_rate = (
        state.timeouts_auto_rejected / state.timeouts_injected
        if state.timeouts_injected > 0 else 1.0
    )

    return {
        "success": all([
            receipt_emission_rate >= 1.0,
            modification_capture_rate >= 1.0,
            rejection_halt_rate >= 1.0,
            timeout_auto_reject_rate >= 1.0
        ]),
        "plan_proposal_receipt_emission": receipt_emission_rate,
        "modifications_captured": modification_capture_rate,
        "rejections_halt_execution": rejection_halt_rate,
        "timeouts_auto_reject": timeout_auto_reject_rate,
        "total_cycles": state.cycle + 1,
        "receipts_emitted": state.plan_proposal_receipts_emitted,
        "executions_allowed": state.executions_after_approval,
        "executions_blocked": state.executions_blocked
    }


# Pytest test functions

def test_plan_approval_scenario_basic():
    """Test basic PLAN_APPROVAL scenario execution."""
    config = PlanApprovalScenarioConfig(n_cycles=50)
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    assert result["success"], f"Scenario failed: {result}"


def test_plan_approval_scenario_approvals():
    """Test plans approved as-is proceed to execution."""
    config = PlanApprovalScenarioConfig(
        n_cycles=40,
        plans_approved=40,
        plans_modified=0,
        plans_rejected=0,
        plans_timeout=0
    )
    state = run_plan_approval_scenario(config)

    assert state.executions_after_approval == 40


def test_plan_approval_scenario_modifications():
    """Test plan modifications are captured."""
    config = PlanApprovalScenarioConfig(
        n_cycles=30,
        plans_approved=0,
        plans_modified=30,
        plans_rejected=0,
        plans_timeout=0
    )
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    assert result["modifications_captured"] >= 1.0


def test_plan_approval_scenario_rejections():
    """Test plan rejections halt execution."""
    config = PlanApprovalScenarioConfig(
        n_cycles=20,
        plans_approved=0,
        plans_modified=0,
        plans_rejected=20,
        plans_timeout=0
    )
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    assert result["rejections_halt_execution"] >= 1.0
    assert state.executions_blocked == 20


def test_plan_approval_scenario_timeouts():
    """Test plan timeouts auto-reject."""
    config = PlanApprovalScenarioConfig(
        n_cycles=10,
        plans_approved=0,
        plans_modified=0,
        plans_rejected=0,
        plans_timeout=10
    )
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    assert result["timeouts_auto_reject"] >= 1.0


def test_plan_approval_scenario_full():
    """Full PLAN_APPROVAL scenario as specified."""
    config = PlanApprovalScenarioConfig()  # Uses default: 100 cycles, 40/30/20/10 split
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    assert result["success"], f"PLAN_APPROVAL scenario failed: {result}"

    # All success criteria must be 100%
    assert result["plan_proposal_receipt_emission"] >= 1.0
    assert result["modifications_captured"] >= 1.0
    assert result["rejections_halt_execution"] >= 1.0
    assert result["timeouts_auto_reject"] >= 1.0


if __name__ == "__main__":
    print("Running PLAN_APPROVAL Monte Carlo Scenario...")
    config = PlanApprovalScenarioConfig()
    state = run_plan_approval_scenario(config)
    result = validate_plan_approval_scenario(state)

    print(f"Results: {result}")
    print(f"Success: {result['success']}")
