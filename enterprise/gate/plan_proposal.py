"""Plan Proposal Module - HITL visibility before ACTUATE phase.

Per DELIVERABLE 5: Show human the execution plan before ACTUATE phase.

Plan states:
    - PROPOSED: Plan generated, awaiting approval
    - APPROVED: Human approved, ready for execution
    - MODIFIED: Human edited the plan
    - REJECTED: Human rejected, do not execute
    - TIMEOUT: Auto-rejected after timeout (default 5 minutes)

Risk levels:
    - CRITICAL/HIGH: PLAN_PROPOSAL is mandatory
    - MEDIUM: Plan shown but auto-approved after 60s
    - LOW: No plan proposal, direct to ACTUATE
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Callable

from core.receipt import emit_receipt, dual_hash


class PlanStatus(Enum):
    """Status of a plan proposal."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class RiskLevel(Enum):
    """Risk level of an action."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PlanStep:
    """Single step in execution plan."""
    step_id: str
    node_id: str
    action: str
    tool: str
    params: dict = field(default_factory=dict)
    estimated_duration_ms: int = 1000
    requires_sandbox: bool = False
    requires_network: bool = False
    network_domains: list[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """Risk assessment for a plan."""
    score: float  # 0.0 to 1.0
    level: RiskLevel
    factors: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """Execution plan for workflow traversal."""
    plan_id: str
    steps: list[PlanStep]
    total_estimated_duration_ms: int
    risk_assessment: RiskAssessment
    requires_sandbox: list[str] = field(default_factory=list)
    requires_network: list[dict] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PROPOSED
    parent_plan_id: str | None = None  # For modified plans

    @classmethod
    def new(cls, steps: list[PlanStep], risk_score: float = 0.0) -> "Plan":
        """Create a new plan with auto-generated ID."""
        total_duration = sum(s.estimated_duration_ms for s in steps)

        # Determine risk level
        if risk_score >= 0.8:
            level = RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            level = RiskLevel.HIGH
        elif risk_score >= 0.3:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        # Collect steps requiring sandbox/network
        sandbox_steps = [s.step_id for s in steps if s.requires_sandbox]
        network_steps = [
            {"step_id": s.step_id, "domains": s.network_domains}
            for s in steps if s.requires_network
        ]

        # Identify risk factors
        factors = []
        if sandbox_steps:
            factors.append(f"sandbox_required:{len(sandbox_steps)}_steps")
        if network_steps:
            factors.append(f"network_required:{len(network_steps)}_steps")
        if total_duration > 30000:
            factors.append(f"long_duration:{total_duration}ms")

        return cls(
            plan_id=str(uuid.uuid4()),
            steps=steps,
            total_estimated_duration_ms=total_duration,
            risk_assessment=RiskAssessment(
                score=risk_score,
                level=level,
                factors=factors
            ),
            requires_sandbox=sandbox_steps,
            requires_network=network_steps
        )


@dataclass
class ApprovalResult:
    """Result of plan approval request."""
    approved: bool
    plan_id: str
    status: PlanStatus
    modifier_id: str | None = None
    modification_reason: str | None = None
    modified_plan: Plan | None = None


# In-memory store for pending plans (in production, use persistent storage)
_pending_plans: dict[str, tuple[Plan, datetime]] = {}


def generate_plan(
    workflow_graph,  # WorkflowGraph from workflow module
    context: dict,
    tenant_id: str = "default"
) -> Plan:
    """Generate execution plan from workflow graph.

    Analyzes the workflow and context to create a detailed
    step-by-step execution plan.

    Args:
        workflow_graph: WorkflowGraph to plan execution for
        context: Execution context
        tenant_id: Tenant identifier

    Returns:
        Plan object with steps and risk assessment
    """
    from enterprise.workflow.graph import plan_path

    # Get planned path through graph
    planned_path = plan_path(workflow_graph, context)

    steps = []
    risk_score = 0.0

    for i, node_id in enumerate(planned_path):
        node = workflow_graph.get_node(node_id)
        if not node:
            continue

        # Determine if step requires sandbox/network based on node type
        requires_sandbox = node.type in ("execution", "external", "api")
        requires_network = node.type in ("api", "external", "fetch")
        network_domains = context.get(f"{node_id}_domains", [])

        # Estimate duration based on node type
        duration_map = {
            "ingestion": 100,
            "summarization": 500,
            "packaging": 200,
            "detection": 300,
            "anchoring": 150,
            "orchestration": 1000,
            "exposure": 100,
        }
        estimated_duration = duration_map.get(node.type, 500)

        step = PlanStep(
            step_id=f"step_{i}_{node_id}",
            node_id=node_id,
            action=f"execute_{node.type}",
            tool=node.function_ref,
            params=context.get(f"{node_id}_params", {}),
            estimated_duration_ms=estimated_duration,
            requires_sandbox=requires_sandbox,
            requires_network=requires_network,
            network_domains=network_domains
        )
        steps.append(step)

        # Accumulate risk score
        if requires_sandbox:
            risk_score += 0.1
        if requires_network:
            risk_score += 0.15

    # Cap risk score at 1.0
    risk_score = min(1.0, risk_score)

    return Plan.new(steps, risk_score)


def emit_plan_proposal_receipt(
    plan: Plan,
    editable_until: str | None = None,
    tenant_id: str = "default"
) -> dict:
    """Emit plan proposal receipt for HITL visibility.

    Args:
        plan: The execution plan
        editable_until: ISO8601 timestamp when edit window closes
        tenant_id: Tenant identifier

    Returns:
        Plan proposal receipt dict
    """
    if not editable_until:
        # Default 5 minute window
        editable_until = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat().replace("+00:00", "Z")

    return emit_receipt("plan_proposal", {
        "tenant_id": tenant_id,
        "plan_id": plan.plan_id,
        "steps": [
            {
                "step_id": s.step_id,
                "node_id": s.node_id,
                "action": s.action,
                "tool": s.tool,
                "estimated_duration_ms": s.estimated_duration_ms
            }
            for s in plan.steps
        ],
        "total_estimated_duration_ms": plan.total_estimated_duration_ms,
        "risk_assessment": {
            "score": plan.risk_assessment.score,
            "level": plan.risk_assessment.level.value,
            "factors": plan.risk_assessment.factors
        },
        "requires_sandbox": plan.requires_sandbox,
        "requires_network": plan.requires_network,
        "editable_until": editable_until
    })


def await_plan_approval(
    plan: Plan,
    timeout: int = 300,
    approval_callback: Callable[[str], ApprovalResult] | None = None,
    tenant_id: str = "default"
) -> ApprovalResult:
    """Wait for human approval of plan.

    Behavior based on risk level:
    - CRITICAL/HIGH: Wait for full timeout
    - MEDIUM: Auto-approve after 60s if no response
    - LOW: Immediate auto-approve

    Args:
        plan: Plan to await approval for
        timeout: Timeout in seconds (default 5 minutes)
        approval_callback: Optional callback to check for approval
        tenant_id: Tenant identifier

    Returns:
        ApprovalResult with approval status
    """
    risk_level = plan.risk_assessment.level

    # LOW risk: immediate auto-approve
    if risk_level == RiskLevel.LOW:
        plan.status = PlanStatus.APPROVED
        return ApprovalResult(
            approved=True,
            plan_id=plan.plan_id,
            status=PlanStatus.APPROVED
        )

    # Store plan for approval
    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout)
    _pending_plans[plan.plan_id] = (plan, deadline)

    # Emit proposal receipt
    emit_plan_proposal_receipt(
        plan,
        editable_until=deadline.isoformat().replace("+00:00", "Z"),
        tenant_id=tenant_id
    )

    # MEDIUM risk: shorter auto-approve timeout
    if risk_level == RiskLevel.MEDIUM:
        timeout = min(timeout, 60)

    # Wait for approval
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for approval via callback
        if approval_callback:
            result = approval_callback(plan.plan_id)
            if result.status != PlanStatus.PROPOSED:
                _pending_plans.pop(plan.plan_id, None)
                return result

        # Check if plan was modified/approved externally
        if plan.plan_id in _pending_plans:
            stored_plan, _ = _pending_plans[plan.plan_id]
            if stored_plan.status != PlanStatus.PROPOSED:
                _pending_plans.pop(plan.plan_id, None)
                return ApprovalResult(
                    approved=stored_plan.status == PlanStatus.APPROVED,
                    plan_id=plan.plan_id,
                    status=stored_plan.status
                )

        time.sleep(0.1)  # Poll interval

    # Timeout reached
    _pending_plans.pop(plan.plan_id, None)

    # MEDIUM risk auto-approves on timeout
    if risk_level == RiskLevel.MEDIUM:
        plan.status = PlanStatus.APPROVED
        return ApprovalResult(
            approved=True,
            plan_id=plan.plan_id,
            status=PlanStatus.APPROVED
        )

    # CRITICAL/HIGH risk: timeout means rejection
    plan.status = PlanStatus.TIMEOUT
    emit_receipt("anomaly", {
        "tenant_id": tenant_id,
        "metric": "plan_timeout",
        "baseline": timeout,
        "delta": 0,
        "classification": "deviation",
        "action": "reject",
        "details": {"plan_id": plan.plan_id}
    })

    return ApprovalResult(
        approved=False,
        plan_id=plan.plan_id,
        status=PlanStatus.TIMEOUT
    )


def approve_plan(plan_id: str) -> bool:
    """Approve a pending plan (called by external approval system).

    Args:
        plan_id: ID of plan to approve

    Returns:
        True if plan was approved, False if not found
    """
    if plan_id in _pending_plans:
        plan, deadline = _pending_plans[plan_id]
        plan.status = PlanStatus.APPROVED
        return True
    return False


def reject_plan(plan_id: str) -> bool:
    """Reject a pending plan (called by external approval system).

    Args:
        plan_id: ID of plan to reject

    Returns:
        True if plan was rejected, False if not found
    """
    if plan_id in _pending_plans:
        plan, deadline = _pending_plans[plan_id]
        plan.status = PlanStatus.REJECTED
        return True
    return False


def modify_plan(
    plan_id: str,
    modified_steps: list[PlanStep],
    modifier_id: str,
    reason: str,
    tenant_id: str = "default"
) -> Plan | None:
    """Modify a pending plan (called by external approval system).

    Creates a new plan with lineage to original.

    Args:
        plan_id: ID of plan to modify
        modified_steps: New steps for the plan
        modifier_id: ID of human who modified
        reason: Reason for modification
        tenant_id: Tenant identifier

    Returns:
        New modified Plan, or None if original not found
    """
    if plan_id not in _pending_plans:
        return None

    original_plan, deadline = _pending_plans[plan_id]

    # Create new plan with lineage
    new_plan = Plan.new(modified_steps, original_plan.risk_assessment.score)
    new_plan.parent_plan_id = plan_id
    new_plan.status = PlanStatus.MODIFIED

    # Emit modification receipt
    emit_plan_modification_receipt(
        original_plan=original_plan,
        modified_plan=new_plan,
        modifier_id=modifier_id,
        reason=reason,
        tenant_id=tenant_id
    )

    # Update pending plans
    _pending_plans.pop(plan_id, None)
    _pending_plans[new_plan.plan_id] = (new_plan, deadline)

    return new_plan


def emit_plan_modification_receipt(
    original_plan: Plan,
    modified_plan: Plan,
    modifier_id: str,
    reason: str,
    tenant_id: str = "default"
) -> dict:
    """Emit receipt for plan modification.

    Captures the lineage from original to modified plan.

    Args:
        original_plan: The original plan
        modified_plan: The modified plan
        modifier_id: ID of human who made modification
        reason: Reason for modification
        tenant_id: Tenant identifier

    Returns:
        Plan modification receipt dict
    """
    # Compute diff between plans
    original_steps = {s.step_id: s for s in original_plan.steps}
    modified_steps = {s.step_id: s for s in modified_plan.steps}

    added = [s for s in modified_steps if s not in original_steps]
    removed = [s for s in original_steps if s not in modified_steps]
    changed = [
        s for s in modified_steps
        if s in original_steps and modified_steps[s] != original_steps[s]
    ]

    return emit_receipt("plan_modification", {
        "tenant_id": tenant_id,
        "original_plan_id": original_plan.plan_id,
        "modified_plan_id": modified_plan.plan_id,
        "modifier_id": modifier_id,
        "reason": reason,
        "diff": {
            "steps_added": added,
            "steps_removed": removed,
            "steps_changed": changed
        },
        "original_hash": dual_hash(json.dumps([s.step_id for s in original_plan.steps])),
        "modified_hash": dual_hash(json.dumps([s.step_id for s in modified_plan.steps]))
    })


def requires_plan_proposal(risk_level: RiskLevel) -> bool:
    """Check if risk level requires plan proposal.

    Per specification:
    - CRITICAL/HIGH: mandatory
    - MEDIUM: shown but auto-approved
    - LOW: no proposal needed

    Args:
        risk_level: The risk level to check

    Returns:
        True if plan proposal is required
    """
    return risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM)
