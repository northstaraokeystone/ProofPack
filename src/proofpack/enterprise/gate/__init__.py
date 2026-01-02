"""Gate module for plan proposal and HITL visibility.

Provides:
    - generate_plan: Generate execution plan from workflow
    - emit_plan_proposal_receipt: Emit plan proposal for approval
    - await_plan_approval: Wait for human approval
    - emit_plan_modification_receipt: Track plan modifications
"""

from .plan_proposal import (
    ApprovalResult,
    Plan,
    PlanStep,
    await_plan_approval,
    emit_plan_modification_receipt,
    emit_plan_proposal_receipt,
    generate_plan,
)

__all__ = [
    "Plan",
    "PlanStep",
    "ApprovalResult",
    "generate_plan",
    "emit_plan_proposal_receipt",
    "await_plan_approval",
    "emit_plan_modification_receipt",
]
