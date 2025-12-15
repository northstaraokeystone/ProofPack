"""Actuate Module - Execute approved actions and deploy helpers.

Enforces PROTECTED component restrictions and handles deployment lifecycle.
"""

from datetime import datetime, timezone
from typing import Any

from proofpack.core.receipt import emit_receipt, StopRule

# Protected components (cannot be modified by helpers)
PROTECTED = [
    "loop.cycle",
    "loop.gate",
    "loop.completeness",
    "ledger.anchor",
    "anchor.dual_hash",
]

# In-memory helper registry (in production, this would be in ledger)
_deployed_helpers: dict = {}


def execute_action(
    approved: dict,
    tenant_id: str,
) -> dict:
    """Execute an approved action.

    Args:
        approved: Approved blueprint or action dict
        tenant_id: Tenant identifier

    Returns:
        Execution result dict

    Raises:
        StopRule: If action targets protected component or fails
    """
    action_type = approved.get("action_type", "deploy")
    target = approved.get("target", approved.get("name", "unknown"))
    blueprint_id = approved.get("blueprint_id")

    # Check protected components
    if is_protected(target):
        emit_receipt(
            "anomaly",
            {
                "tenant_id": tenant_id,
                "type": "protected_modification_attempt",
                "target": target,
                "action_type": action_type,
                "severity": "high",
            },
        )
        raise StopRule(f"Cannot modify protected component: {target}")

    # Execute based on action type
    try:
        if action_type == "deploy":
            result = deploy_helper(approved, tenant_id)
        elif action_type == "rollback":
            helper_id = approved.get("helper_id", blueprint_id)
            reason = approved.get("reason", "manual rollback")
            result = rollback_helper(helper_id, reason, tenant_id)
        elif action_type == "modify":
            result = _modify_helper(approved, tenant_id)
        else:
            result = {
                "status": "failed",
                "reason": f"Unknown action type: {action_type}",
            }
    except Exception as e:
        # Emit anomaly and re-raise as StopRule
        emit_receipt(
            "anomaly",
            {
                "tenant_id": tenant_id,
                "type": "actuation_failure",
                "target": target,
                "action_type": action_type,
                "error": str(e),
                "severity": "high",
            },
        )
        raise StopRule(f"Actuation failed: {e}")

    # Emit actuation receipt (L1)
    emit_receipt(
        "actuation",
        {
            "tenant_id": tenant_id,
            "action_type": action_type,
            "target": target,
            "blueprint_id": blueprint_id,
            "status": result.get("status", "unknown"),
            "reason": result.get("reason"),
        },
    )

    return result


def deploy_helper(
    blueprint: dict,
    tenant_id: str = "default",
) -> dict:
    """Register and deploy a helper.

    Args:
        blueprint: Helper blueprint dict
        tenant_id: Tenant identifier

    Returns:
        Deployment result dict
    """
    blueprint_id = blueprint.get("blueprint_id")
    name = blueprint.get("name", "unknown")

    if not blueprint_id:
        return {
            "status": "failed",
            "reason": "No blueprint_id provided",
        }

    # Check if targeting protected
    pattern = blueprint.get("pattern", {})
    target = pattern.get("action", "") + pattern.get("trigger", "")
    if is_protected(target):
        return {
            "status": "failed",
            "reason": f"Blueprint targets protected component",
        }

    # Register helper
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    helper_record = {
        "helper_id": blueprint_id,
        "name": name,
        "blueprint": blueprint,
        "tenant_id": tenant_id,
        "status": "deployed",
        "deployed_at": now,
        "actions_taken": 0,
        "actions_successful": 0,
    }

    _deployed_helpers[blueprint_id] = helper_record

    return {
        "status": "success",
        "helper_id": blueprint_id,
        "deployed_at": now,
    }


def rollback_helper(
    helper_id: str,
    reason: str,
    tenant_id: str = "default",
) -> dict:
    """Deactivate a helper (rollback).

    Does not delete (append-only), just marks as rolled_back.

    Args:
        helper_id: Helper identifier
        reason: Reason for rollback
        tenant_id: Tenant identifier

    Returns:
        Rollback result dict
    """
    if helper_id not in _deployed_helpers:
        return {
            "status": "failed",
            "reason": f"Helper {helper_id} not found",
        }

    helper = _deployed_helpers[helper_id]

    # Check if already rolled back
    if helper.get("status") == "rolled_back":
        return {
            "status": "failed",
            "reason": f"Helper {helper_id} already rolled back",
        }

    # Mark as rolled back (don't delete - append-only)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    helper["status"] = "rolled_back"
    helper["rolled_back_at"] = now
    helper["rollback_reason"] = reason

    # Emit rollback receipt
    emit_receipt(
        "actuation",
        {
            "tenant_id": tenant_id,
            "action_type": "rollback",
            "target": helper.get("name", helper_id),
            "blueprint_id": helper_id,
            "status": "success",
            "reason": reason,
        },
    )

    return {
        "status": "success",
        "helper_id": helper_id,
        "rolled_back_at": now,
        "reason": reason,
    }


def _modify_helper(
    modification: dict,
    tenant_id: str,
) -> dict:
    """Modify an existing helper.

    Args:
        modification: Modification dict with helper_id and changes
        tenant_id: Tenant identifier

    Returns:
        Modification result dict
    """
    helper_id = modification.get("helper_id")
    if not helper_id or helper_id not in _deployed_helpers:
        return {
            "status": "failed",
            "reason": f"Helper {helper_id} not found",
        }

    helper = _deployed_helpers[helper_id]

    # Apply modifications (only to allowed fields)
    allowed_fields = ["pattern", "validation"]
    changes = modification.get("changes", {})

    for field, value in changes.items():
        if field in allowed_fields:
            helper["blueprint"][field] = value

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    helper["modified_at"] = now

    return {
        "status": "success",
        "helper_id": helper_id,
        "modified_at": now,
    }


def is_protected(target: str) -> bool:
    """Check if target is a protected component.

    Args:
        target: Target identifier string

    Returns:
        True if protected, False otherwise
    """
    if not target:
        return False

    for protected in PROTECTED:
        if protected in target:
            return True
    return False


def get_helper(helper_id: str) -> dict | None:
    """Get a deployed helper by ID.

    Args:
        helper_id: Helper identifier

    Returns:
        Helper record dict or None if not found
    """
    return _deployed_helpers.get(helper_id)


def get_active_helpers(tenant_id: str = None) -> list:
    """Get all active (deployed, not rolled back) helpers.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        List of active helper records
    """
    active = []
    for helper_id, helper in _deployed_helpers.items():
        if helper.get("status") == "deployed":
            if tenant_id is None or helper.get("tenant_id") == tenant_id:
                active.append(helper)
    return active


def record_helper_action(
    helper_id: str,
    success: bool,
) -> None:
    """Record a helper action for tracking.

    Args:
        helper_id: Helper identifier
        success: Whether the action succeeded
    """
    if helper_id in _deployed_helpers:
        helper = _deployed_helpers[helper_id]
        helper["actions_taken"] = helper.get("actions_taken", 0) + 1
        if success:
            helper["actions_successful"] = helper.get("actions_successful", 0) + 1


def clear_helpers() -> None:
    """Clear all deployed helpers (for testing)."""
    global _deployed_helpers
    _deployed_helpers = {}
