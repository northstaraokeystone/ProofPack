"""Monte Carlo simulation engine for LOOP dynamics testing.

Implements simulation of the full LOOP cycle:
SENSE → ANALYZE → HARVEST → HYPOTHESIZE → GATE → ACTUATE → EMIT
"""
import random
import time
import uuid
from typing import Optional

from conftest import SimConfig, SimState


def run_simulation(
    config: SimConfig,
    initial_state: Optional[SimState] = None
) -> SimState:
    """Execute n_cycles, return final state."""
    random.seed(config.random_seed)
    state = initial_state if initial_state else SimState()

    start_time = time.time()

    while state.cycle < config.n_cycles:
        # Check timeout
        if time.time() - start_time > config.timeout_seconds:
            state.violations.append(f"timeout_at_cycle_{state.cycle}")
            break

        state = simulate_cycle(state, config)
        state.cycle += 1

    return state


def simulate_cycle(state: SimState, config: SimConfig) -> SimState:
    """One SENSE→ANALYZE→HARVEST→HYPOTHESIZE→GATE→ACTUATE→EMIT cycle."""
    cycle_id = f"cycle_{state.cycle}"

    # SENSE: Detect gaps with probability gap_rate
    state = simulate_gap(state, config.gap_rate)

    # ANALYZE: Process any detected gaps
    receipts = []
    observation = {
        "receipt_type": "observation",
        "cycle": state.cycle,
        "gaps_detected": len([g for g in state.gap_history if g.get("cycle") == state.cycle])
    }
    receipts.append(observation)

    # HARVEST: Identify patterns from gap history
    harvest_receipt = _simulate_harvest(state)
    receipts.append(harvest_receipt)

    # HYPOTHESIZE: Propose helpers based on patterns
    state = simulate_genesis(state)

    # GATE: Approve/reject helper proposals
    for helper in list(state.active_helpers):
        if helper.get("state") == "pending":
            approval = simulate_approval(state, helper.get("risk_score", 0.5))
            helper["state"] = approval
            receipts.append({
                "receipt_type": "approval",
                "helper_id": helper.get("id"),
                "decision": approval
            })

    # ACTUATE: Execute approved helpers (simulated)
    for helper in state.active_helpers:
        if helper.get("state") == "approved":
            helper["executions"] = helper.get("executions", 0) + 1

    # EMIT: Record cycle receipt
    cycle_receipt = {
        "receipt_type": "cycle",
        "cycle_id": cycle_id,
        "cycle_num": state.cycle,
        "active_helpers": len(state.active_helpers),
        "gap_count": len(state.gap_history)
    }
    receipts.append(cycle_receipt)

    # Check completeness
    completeness = check_completeness(state)
    state.completeness_trace.append(completeness)

    # Validate state
    violations = validate_state(state)
    state.violations.extend(violations)

    # Add all receipts to ledger
    state.receipt_ledger.extend(receipts)

    return state


def simulate_gap(state: SimState, gap_rate: float) -> SimState:
    """Inject gap with probability gap_rate."""
    if random.random() < gap_rate:
        problem_types = ["timeout", "resource_exhaustion", "parsing_error", "validation_failure", "api_error"]
        gap = {
            "id": f"gap_{uuid.uuid4().hex[:8]}",
            "cycle": state.cycle,
            "problem_type": random.choice(problem_types),
            "resolve_time": random.uniform(5, 120),  # minutes
            "ts": time.time()
        }
        state.gap_history.append(gap)
    return state


def simulate_genesis(state: SimState) -> SimState:
    """Check for ≥5 recurring gaps, propose helper."""
    # Count problem types
    problem_counts: dict[str, list[dict]] = {}
    for gap in state.gap_history:
        ptype = gap.get("problem_type", "unknown")
        if ptype not in problem_counts:
            problem_counts[ptype] = []
        problem_counts[ptype].append(gap)

    # Genesis trigger: ≥5 occurrences of same problem_type AND median resolve_time > 30
    for ptype, gaps in problem_counts.items():
        if len(gaps) >= 5:
            resolve_times = sorted([g.get("resolve_time", 0) for g in gaps])
            median_resolve = resolve_times[len(resolve_times) // 2]

            if median_resolve > 30:
                # Check if helper already exists for this pattern
                existing = any(h.get("pattern_id") == ptype for h in state.active_helpers)
                if not existing:
                    helper = {
                        "id": f"helper_{uuid.uuid4().hex[:8]}",
                        "pattern_id": ptype,
                        "state": "pending",
                        "risk_score": _compute_risk_score(gaps),
                        "created_cycle": state.cycle,
                        "executions": 0
                    }
                    state.active_helpers.append(helper)

    return state


def simulate_approval(state: SimState, risk_score: float) -> str:
    """Return 'approved'|'pending'|'rejected' based on risk.

    Approval gate thresholds:
    - risk < 0.2 → auto-approve
    - 0.2 ≤ risk < 0.5 → single approval (simulated)
    - 0.5 ≤ risk < 0.8 → two approvals (simulated with lower probability)
    - risk ≥ 0.8 → two approvals + observation period (pending)
    """
    if risk_score < 0.2:
        return "approved"
    elif risk_score < 0.5:
        # Single approval - 80% chance
        return "approved" if random.random() < 0.8 else "pending"
    elif risk_score < 0.8:
        # Two approvals - 60% chance
        return "approved" if random.random() < 0.6 else "pending"
    else:
        # High risk - require observation period
        return "pending"


def check_completeness(state: SimState) -> dict:
    """Return {L0: float, L1: float, ..., L4: float, self_verifying: bool}."""
    # Count receipt types at each level
    level_map = {
        "ingest": "L0", "anchor": "L0", "anomaly": "L0",
        "scan": "L1", "observation": "L1", "cycle": "L1",
        "harvest": "L2", "helper_blueprint": "L2", "backtest": "L2",
        "effectiveness": "L3", "approval": "L3",
        "meta_fitness": "L4", "completeness": "L4"
    }

    level_counts = {"L0": set(), "L1": set(), "L2": set(), "L3": set(), "L4": set()}
    for receipt in state.receipt_ledger:
        rtype = receipt.get("receipt_type", "unknown")
        level = level_map.get(rtype, "L0")
        level_counts[level].add(rtype)

    # Asymptotic coverage: f(n) = 1 - 1/(1+n)
    def asymptotic_coverage(n: int) -> float:
        return 1.0 - 1.0 / (1.0 + n)

    coverages = {
        level: asymptotic_coverage(len(types))
        for level, types in level_counts.items()
    }

    # Self-verifying if L4 feeds back to L0
    l4_coverage = coverages["L4"]
    l0_coverage = coverages["L0"]
    self_verifying = l4_coverage > 0.5 and l0_coverage > 0.5

    return {
        **coverages,
        "self_verifying": self_verifying
    }


def validate_state(state: SimState) -> list[str]:
    """Return list of violation strings (empty = healthy)."""
    violations = []

    # Check for orphaned helpers (no pattern in gap history)
    gap_patterns = {g.get("problem_type") for g in state.gap_history}
    for helper in state.active_helpers:
        if helper.get("pattern_id") not in gap_patterns:
            violations.append(f"orphaned_helper_{helper.get('id')}")

    # Check for duplicate helper IDs
    helper_ids = [h.get("id") for h in state.active_helpers]
    if len(helper_ids) != len(set(helper_ids)):
        violations.append("duplicate_helper_ids")

    # Check for missing receipt types in ledger
    if state.cycle > 0 and not state.receipt_ledger:
        violations.append("empty_ledger_after_cycles")

    # Check completeness regression
    if len(state.completeness_trace) >= 2:
        prev = state.completeness_trace[-2]
        curr = state.completeness_trace[-1]
        for level in ["L0", "L1", "L2", "L3", "L4"]:
            if curr.get(level, 0) < prev.get(level, 0) - 0.01:
                violations.append(f"completeness_regression_{level}")

    return violations


def _simulate_harvest(state: SimState) -> dict:
    """Simulate pattern harvest."""
    # Count patterns
    pattern_counts: dict[str, int] = {}
    for gap in state.gap_history:
        ptype = gap.get("problem_type", "unknown")
        pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1

    actionable = [
        {"pattern_id": p, "count": c}
        for p, c in pattern_counts.items()
        if c >= 3
    ]

    return {
        "receipt_type": "harvest",
        "signals_processed": len(state.gap_history),
        "patterns_total": len(pattern_counts),
        "actionable_patterns": actionable
    }


def _compute_risk_score(gaps: list[dict]) -> float:
    """Compute risk score from gap history."""
    if not gaps:
        return 0.5

    # Higher resolve times = higher risk
    avg_resolve = sum(g.get("resolve_time", 30) for g in gaps) / len(gaps)
    # Normalize to 0-1 (assuming 120 min is max)
    risk = min(1.0, avg_resolve / 120.0)
    return risk
