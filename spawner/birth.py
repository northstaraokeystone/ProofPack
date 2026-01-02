"""Agent Birth - Spawn agents based on gate color.

Gate-triggered spawning rules:
- GREEN (>0.9): 1 success_learner, TTL 60s
- YELLOW (0.7-0.9): 3 watchers (drift, wound, success), TTL action+30s
- RED (<0.7): (wound_count // 2) + 1 helpers, min 1, max 6, TTL 300s

High variance (>0.3) adds +1 to helper spawn count.
"""

import time
import uuid
from dataclasses import dataclass

from core.receipt import emit_receipt, merkle

from .registry import (
    Agent,
    AgentType,
    register_agent,
    can_spawn,
    DEFAULT_TTL_SECONDS,
)
from .lifecycle import activate_agent

# Spawn limits
MIN_HELPERS = 1
MAX_HELPERS = 6
GREEN_LEARNER_TTL = 60
YELLOW_WATCHER_TTL_BUFFER = 30
HIGH_VARIANCE_THRESHOLD = 0.3


@dataclass
class SpawnResult:
    """Result of a spawn operation."""
    agent_ids: list[str]
    spawn_count: int
    trigger: str
    group_id: str
    depth_level: int


def calculate_helper_count(wound_count: int, variance: float = 0.0) -> int:
    """Calculate number of helpers to spawn for RED gate.

    Formula: (wound_count // 2) + 1
    If variance > 0.3, add 1 more helper.
    Bounded by [MIN_HELPERS, MAX_HELPERS].
    """
    base = (wound_count // 2) + 1

    # High variance bonus
    if variance > HIGH_VARIANCE_THRESHOLD:
        base += 1

    return max(MIN_HELPERS, min(MAX_HELPERS, base))


def spawn_for_gate(
    gate_color: str,
    confidence_score: float,
    wound_count: int = 0,
    variance: float = 0.0,
    action_duration_seconds: int = 0,
    parent_agent_id: str | None = None,
    tenant_id: str = "default",
) -> tuple[SpawnResult | None, dict | None]:
    """Spawn agents based on gate decision.

    Args:
        gate_color: "GREEN", "YELLOW", or "RED"
        confidence_score: Current confidence (0-1)
        wound_count: Number of wounds for RED gate formula
        variance: Monte Carlo variance for bonus calculation
        action_duration_seconds: Expected action duration for YELLOW TTL
        parent_agent_id: Parent agent if this is recursive spawning
        tenant_id: Tenant identifier

    Returns:
        (SpawnResult, spawn_receipt) or (None, None) if spawning disabled/failed
    """
    # Import feature flag here to avoid circular import
    from config.features import FEATURE_AGENT_SPAWNING_ENABLED

    if not FEATURE_AGENT_SPAWNING_ENABLED:
        # Shadow mode - log what would happen
        would_spawn = _count_would_spawn(gate_color, wound_count, variance)
        emit_receipt("spawn_shadow", {
            "tenant_id": tenant_id,
            "gate_color": gate_color,
            "would_spawn": would_spawn,
            "reason": "feature_disabled",
        })
        return None, None

    t0 = time.perf_counter()
    group_id = str(uuid.uuid4())
    agents: list[Agent] = []
    depth = 0

    if gate_color == "GREEN":
        agents = _spawn_green(
            confidence_score, group_id, parent_agent_id, tenant_id
        )
    elif gate_color == "YELLOW":
        agents = _spawn_yellow(
            confidence_score, group_id, action_duration_seconds,
            parent_agent_id, tenant_id
        )
    elif gate_color == "RED":
        agents = _spawn_red(
            confidence_score, wound_count, variance, group_id,
            parent_agent_id, tenant_id
        )

    if not agents:
        return None, None

    # Activate all spawned agents
    for agent in agents:
        activate_agent(agent.agent_id, tenant_id)
        depth = max(depth, agent.depth)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = SpawnResult(
        agent_ids=[a.agent_id for a in agents],
        spawn_count=len(agents),
        trigger=f"{gate_color}_GATE",
        group_id=group_id,
        depth_level=depth,
    )

    # Emit spawn receipt
    agent_data = [{"agent_id": a.agent_id, "type": a.agent_type.value}
                  for a in agents]

    receipt = emit_receipt("spawn", {
        "tenant_id": tenant_id,
        "parent_agent_id": parent_agent_id,
        "child_agents": result.agent_ids,
        "trigger": result.trigger,
        "confidence_at_spawn": confidence_score,
        "depth_level": depth,
        "max_ttl_seconds": max(a.ttl_seconds for a in agents),
        "wound_count": wound_count,
        "helpers_spawned": len(agents),
        "convergence_proof": 0.0,  # Set by caller if available
        "merkle_root": merkle(agent_data),
        "spawn_ms": elapsed_ms,
    })

    return result, receipt


def _spawn_green(
    confidence: float,
    group_id: str,
    parent_id: str | None,
    tenant_id: str,
) -> list[Agent]:
    """GREEN gate: spawn 1 success_learner."""
    # Check feature flag
    from config.features import FEATURE_GREEN_LEARNERS_ENABLED
    if not FEATURE_GREEN_LEARNERS_ENABLED:
        return []

    if not can_spawn(1):
        return []

    agent, _ = register_agent(
        agent_type=AgentType.SUCCESS_LEARNER,
        gate_color="GREEN",
        confidence_at_spawn=confidence,
        parent_id=parent_id,
        group_id=group_id,
        ttl_seconds=GREEN_LEARNER_TTL,
        metadata={"purpose": "capture_success_pattern"},
        tenant_id=tenant_id,
    )

    return [agent] if agent else []


def _spawn_yellow(
    confidence: float,
    group_id: str,
    action_duration: int,
    parent_id: str | None,
    tenant_id: str,
) -> list[Agent]:
    """YELLOW gate: spawn 3 watchers (drift, wound, success)."""
    # Check feature flag
    from config.features import FEATURE_YELLOW_WATCHERS_ENABLED
    if not FEATURE_YELLOW_WATCHERS_ENABLED:
        return []

    if not can_spawn(3):
        return []

    ttl = action_duration + YELLOW_WATCHER_TTL_BUFFER
    agents = []

    watcher_types = [
        (AgentType.DRIFT_WATCHER, "monitor_context_drift"),
        (AgentType.WOUND_WATCHER, "monitor_confidence_changes"),
        (AgentType.SUCCESS_WATCHER, "monitor_outcome_vs_prediction"),
    ]

    for agent_type, purpose in watcher_types:
        agent, _ = register_agent(
            agent_type=agent_type,
            gate_color="YELLOW",
            confidence_at_spawn=confidence,
            parent_id=parent_id,
            group_id=group_id,
            ttl_seconds=ttl,
            metadata={"purpose": purpose},
            tenant_id=tenant_id,
        )
        if agent:
            agents.append(agent)

    return agents


def _spawn_red(
    confidence: float,
    wound_count: int,
    variance: float,
    group_id: str,
    parent_id: str | None,
    tenant_id: str,
) -> list[Agent]:
    """RED gate: spawn (wound_count // 2) + 1 helpers."""
    # Check feature flag
    from config.features import FEATURE_RED_HELPERS_ENABLED
    if not FEATURE_RED_HELPERS_ENABLED:
        return []

    helper_count = calculate_helper_count(wound_count, variance)

    if not can_spawn(helper_count):
        # Try to spawn as many as we can
        from .registry import MAX_AGENTS, get_population_count
        available = MAX_AGENTS - get_population_count()
        helper_count = min(helper_count, available)
        if helper_count <= 0:
            return []

    agents = []
    decomposition_angles = [
        "simplify", "decompose", "reframe", "analogize",
        "constrain", "relax",
    ]

    for i in range(helper_count):
        angle = decomposition_angles[i % len(decomposition_angles)]
        agent, _ = register_agent(
            agent_type=AgentType.HELPER,
            gate_color="RED",
            confidence_at_spawn=confidence,
            parent_id=parent_id,
            group_id=group_id,
            ttl_seconds=DEFAULT_TTL_SECONDS,
            metadata={
                "purpose": "solve_problem",
                "decomposition_angle": angle,
                "helper_index": i,
            },
            tenant_id=tenant_id,
        )
        if agent:
            agents.append(agent)

    return agents


def _count_would_spawn(gate_color: str, wound_count: int, variance: float) -> int:
    """Calculate how many agents would spawn (for shadow mode)."""
    if gate_color == "GREEN":
        return 1
    elif gate_color == "YELLOW":
        return 3
    elif gate_color == "RED":
        return calculate_helper_count(wound_count, variance)
    return 0


def simulate_spawn(
    gate_color: str,
    confidence_score: float,
    wound_count: int = 0,
    variance: float = 0.0,
) -> dict:
    """Simulate spawning without actually creating agents.

    Returns a dict describing what would be spawned.
    """
    spawn_count = _count_would_spawn(gate_color, wound_count, variance)

    if gate_color == "GREEN":
        agent_types = ["success_learner"]
        ttl = GREEN_LEARNER_TTL
    elif gate_color == "YELLOW":
        agent_types = ["drift_watcher", "wound_watcher", "success_watcher"]
        ttl = YELLOW_WATCHER_TTL_BUFFER
    elif gate_color == "RED":
        agent_types = ["helper"] * spawn_count
        ttl = DEFAULT_TTL_SECONDS
    else:
        agent_types = []
        ttl = 0

    return {
        "gate_color": gate_color,
        "confidence_score": confidence_score,
        "wound_count": wound_count,
        "variance": variance,
        "would_spawn": spawn_count,
        "agent_types": agent_types,
        "ttl_seconds": ttl,
    }
