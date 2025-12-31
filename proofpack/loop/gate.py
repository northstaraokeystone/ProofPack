"""Gate Module - Human approval workflow.

Calculate risk and route to appropriate gate:
- <0.2: auto-approve
- 0.2-0.5: single HITL approval
- 0.5-0.8: dual approval
- >0.8: dual approval + observation period
"""

from datetime import datetime, timedelta, timezone

from proofpack.core.receipt import emit_receipt

# Risk thresholds (ProofPack v3)
RISK_THRESHOLDS = {
    "auto_approve": 0.2,       # <0.2: auto-approve
    "single_approval": 0.5,   # 0.2-0.5: single HITL approval
    "dual_approval": 0.8,     # 0.5-0.8: two HITL approvals
    "observation": 0.8,       # >0.8: dual approval + observation period
}

# HITL timeout (QED v7: "After 14 days, proposals auto-decline")
HITL_TIMEOUT_DAYS = 14

# In-memory approval state (in production, this would be in ledger)
_pending_approvals: dict = {}


def calculate_risk(action: dict) -> float:
    """Calculate risk score for an action (0-1).

    Factors:
    - action type (deploy vs modify vs delete)
    - affected scope (single vs multiple)
    - reversibility (can rollback vs permanent)
    - confidence (backtest success rate)

    Args:
        action: Action dict with type, target, validation info

    Returns:
        Risk score 0-1
    """
    base_risk = 0.5

    # Action type risk
    action_type = action.get("action_type", action.get("type", "unknown"))
    if action_type == "deploy":
        base_risk += 0.0  # New deployment is neutral
    elif action_type == "modify":
        base_risk += 0.1  # Modification is slightly riskier
    elif action_type == "delete":
        base_risk += 0.3  # Deletion is risky
    elif action_type == "rollback":
        base_risk -= 0.1  # Rollback is safe

    # Scope risk
    targets = action.get("targets", [action.get("target", "")])
    if len(targets) > 5:
        base_risk += 0.2  # Broad scope
    elif len(targets) > 1:
        base_risk += 0.1  # Multiple targets

    # Reversibility (from blueprint if available)
    if action.get("reversible", True):
        base_risk -= 0.1

    # Validation confidence reduces risk
    validation = action.get("validation", {})
    success_rate = validation.get("success_rate", 0.5)
    base_risk -= (success_rate - 0.5) * 0.4  # Good validation reduces risk

    # Risk from blueprint
    blueprint_risk = action.get("risk_score", 0.0)
    if blueprint_risk > 0:
        # Average with blueprint risk
        base_risk = (base_risk + blueprint_risk) / 2

    return max(0.0, min(1.0, base_risk))


def request_approval(
    blueprint: dict,
    tenant_id: str,
) -> dict:
    """Route blueprint to appropriate approval gate.

    Args:
        blueprint: Helper blueprint dict
        tenant_id: Tenant identifier

    Returns:
        Approval result dict with decision and gate_type
    """
    blueprint_id = blueprint.get("blueprint_id", "unknown")
    risk_score = blueprint.get("risk_score", calculate_risk(blueprint))

    # Determine gate type based on risk
    if risk_score < RISK_THRESHOLDS["auto_approve"]:
        gate_type = "auto"
        decision = "approved"
        approver = "auto"
    elif risk_score < RISK_THRESHOLDS["single_approval"]:
        gate_type = "single"
        decision = "deferred"
        approver = None
    elif risk_score < RISK_THRESHOLDS["dual_approval"]:
        gate_type = "dual"
        decision = "deferred"
        approver = None
    else:
        gate_type = "observation"
        decision = "deferred"
        approver = None

    # Calculate expiration
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=HITL_TIMEOUT_DAYS)).isoformat().replace("+00:00", "Z")

    result = {
        "blueprint_id": blueprint_id,
        "action_proposed": blueprint.get("name", "unknown"),
        "risk_score": risk_score,
        "gate_type": gate_type,
        "decision": decision,
        "approver": approver,
        "rationale": _generate_rationale(blueprint, risk_score, gate_type),
        "expires_at": expires_at if decision == "deferred" else None,
    }

    # Store pending approval if deferred
    if decision == "deferred":
        _pending_approvals[blueprint_id] = {
            "blueprint": blueprint,
            "result": result,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at,
            "approvals": [],  # List of approver IDs
        }

    # Emit approval receipt (L4)
    emit_receipt(
        "approval",
        {
            "tenant_id": tenant_id,
            "blueprint_id": blueprint_id,
            "action_proposed": result["action_proposed"],
            "risk_score": risk_score,
            "gate_type": gate_type,
            "decision": decision,
            "approver": approver,
            "rationale": result["rationale"],
            "expires_at": result["expires_at"],
        },
    )

    return result


def check_approval_status(blueprint_id: str) -> str:
    """Check the approval status of a blueprint.

    Args:
        blueprint_id: Blueprint identifier

    Returns:
        "approved" | "deferred" | "rejected" | "pending"
    """
    if blueprint_id not in _pending_approvals:
        return "pending"

    approval = _pending_approvals[blueprint_id]

    # Check if expired
    now = datetime.now(timezone.utc)
    expires_at = approval.get("expires_at")
    if expires_at:
        expire_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if now > expire_dt:
            return "rejected"  # Auto-declined

    result = approval.get("result", {})
    return result.get("decision", "pending")


def auto_decline_stale(
    pending_blueprints: list = None,
    timeout_days: int = HITL_TIMEOUT_DAYS,
) -> list:
    """Auto-decline blueprints pending longer than timeout.

    Args:
        pending_blueprints: List of blueprint IDs to check (default: all pending)
        timeout_days: Days after which to auto-decline

    Returns:
        List of declined blueprint IDs
    """
    declined = []
    now = datetime.now(timezone.utc)

    # Use provided list or all pending
    if pending_blueprints is None:
        pending_blueprints = list(_pending_approvals.keys())

    for blueprint_id in pending_blueprints:
        if blueprint_id not in _pending_approvals:
            continue

        approval = _pending_approvals[blueprint_id]
        expires_at = approval.get("expires_at")

        if expires_at:
            expire_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if now > expire_dt:
                # Auto-decline
                approval["result"]["decision"] = "auto_declined"
                declined.append(blueprint_id)

                # Emit approval receipt
                emit_receipt(
                    "approval",
                    {
                        "tenant_id": approval["blueprint"].get("tenant_id", "default"),
                        "blueprint_id": blueprint_id,
                        "action_proposed": approval["result"]["action_proposed"],
                        "risk_score": approval["result"]["risk_score"],
                        "gate_type": approval["result"]["gate_type"],
                        "decision": "auto_declined",
                        "approver": "system",
                        "rationale": f"Auto-declined after {timeout_days} days without approval",
                        "expires_at": None,
                    },
                )

    return declined


def approve_blueprint(
    blueprint_id: str,
    approver_id: str,
    tenant_id: str = "default",
) -> dict:
    """Approve a pending blueprint.

    Args:
        blueprint_id: Blueprint identifier
        approver_id: ID of the approver
        tenant_id: Tenant identifier

    Returns:
        Updated approval result
    """
    if blueprint_id not in _pending_approvals:
        return {"error": "Blueprint not found or not pending"}

    approval = _pending_approvals[blueprint_id]
    gate_type = approval["result"]["gate_type"]

    # Add approval
    approval["approvals"].append(approver_id)

    # Check if enough approvals
    if gate_type == "single" and len(approval["approvals"]) >= 1:
        approval["result"]["decision"] = "approved"
        approval["result"]["approver"] = approver_id
    elif gate_type in ("dual", "observation") and len(approval["approvals"]) >= 2:
        approval["result"]["decision"] = "approved"
        approval["result"]["approver"] = ",".join(approval["approvals"])

    # Emit approval receipt
    emit_receipt(
        "approval",
        {
            "tenant_id": tenant_id,
            "blueprint_id": blueprint_id,
            "action_proposed": approval["result"]["action_proposed"],
            "risk_score": approval["result"]["risk_score"],
            "gate_type": gate_type,
            "decision": approval["result"]["decision"],
            "approver": approval["result"]["approver"],
            "rationale": f"Approved by {approver_id}",
            "expires_at": approval["result"]["expires_at"],
        },
    )

    return approval["result"]


def reject_blueprint(
    blueprint_id: str,
    rejector_id: str,
    reason: str,
    tenant_id: str = "default",
) -> dict:
    """Reject a pending blueprint.

    Args:
        blueprint_id: Blueprint identifier
        rejector_id: ID of the rejector
        reason: Reason for rejection
        tenant_id: Tenant identifier

    Returns:
        Updated approval result
    """
    if blueprint_id not in _pending_approvals:
        return {"error": "Blueprint not found or not pending"}

    approval = _pending_approvals[blueprint_id]
    approval["result"]["decision"] = "rejected"
    approval["result"]["approver"] = rejector_id
    approval["result"]["rationale"] = reason

    # Emit approval receipt
    emit_receipt(
        "approval",
        {
            "tenant_id": tenant_id,
            "blueprint_id": blueprint_id,
            "action_proposed": approval["result"]["action_proposed"],
            "risk_score": approval["result"]["risk_score"],
            "gate_type": approval["result"]["gate_type"],
            "decision": "rejected",
            "approver": rejector_id,
            "rationale": reason,
            "expires_at": None,
        },
    )

    return approval["result"]


def _generate_rationale(blueprint: dict, risk_score: float, gate_type: str) -> str:
    """Generate human-readable rationale for approval decision.

    Args:
        blueprint: Blueprint dict
        risk_score: Calculated risk score
        gate_type: Type of gate applied

    Returns:
        Rationale string
    """
    name = blueprint.get("name", "unknown")
    origin = blueprint.get("origin", {})
    validation = blueprint.get("validation", {})

    rationale_parts = [f"Helper '{name}'"]

    # Origin info
    gap_count = origin.get("gap_count", 0)
    hours_saved = origin.get("total_human_hours_saved", 0)
    if gap_count:
        rationale_parts.append(f"addresses {gap_count} wounds")
    if hours_saved:
        rationale_parts.append(f"saves ~{hours_saved:.1f} hours")

    # Validation info
    success_rate = validation.get("success_rate", 0)
    if success_rate:
        rationale_parts.append(f"{success_rate:.0%} backtest success")

    # Risk and gate
    rationale_parts.append(f"risk={risk_score:.2f}")
    rationale_parts.append(f"gate={gate_type}")

    return ". ".join(rationale_parts)


def get_pending_approvals(tenant_id: str = None) -> list:
    """Get all pending approvals.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        List of pending approval dicts
    """
    pending = []
    for blueprint_id, approval in _pending_approvals.items():
        if approval["result"]["decision"] == "deferred":
            if tenant_id is None or approval["blueprint"].get("tenant_id") == tenant_id:
                pending.append({
                    "blueprint_id": blueprint_id,
                    "created_at": approval["created_at"],
                    "expires_at": approval["expires_at"],
                    "gate_type": approval["result"]["gate_type"],
                    "approvals_received": len(approval["approvals"]),
                })
    return pending


def clear_pending_approvals() -> None:
    """Clear all pending approvals (for testing)."""
    global _pending_approvals
    _pending_approvals = {}
