"""Hook validation and tenant ID mapping for QED bridge.

Maps QED hook names to ProofPack tenant IDs per CLAUDEME Section 4.1.
Only the 6 defined hooks are valid - all others trigger stoprule.
"""
from ..core.receipt import emit_receipt, StopRule


# Hook to tenant ID mapping - 6 defined companies only
HOOK_TENANT_MAP: dict[str, str] = {
    "tesla": "tesla-automotive",
    "spacex": "spacex-aerospace",
    "starlink": "starlink-constellation",
    "boring": "boring-infrastructure",
    "neuralink": "neuralink-medical",
    "xai": "xai-research",
}

# Valid hooks set for O(1) lookup
VALID_HOOKS: set[str] = set(HOOK_TENANT_MAP.keys())


def stoprule_invalid_hook(hook: str) -> None:
    """Emit anomaly receipt and raise StopRule for invalid hook.

    Args:
        hook: The invalid hook name

    Raises:
        StopRule: Always raised after emitting anomaly receipt
    """
    emit_receipt("anomaly", {
        "tenant_id": "system",
        "metric": "hook_validation",
        "baseline": None,
        "delta": None,
        "classification": "violation",
        "action": "halt",
        "invalid_hook": hook,
        "valid_hooks": list(VALID_HOOKS),
    })
    raise StopRule(f"Invalid hook '{hook}'. Valid hooks: {sorted(VALID_HOOKS)}")


def validate_hook(hook: str) -> str:
    """Validate that hook exists in VALID_HOOKS.

    Args:
        hook: Hook name string to validate

    Returns:
        The validated hook string if valid

    Raises:
        StopRule: If hook is not in VALID_HOOKS
    """
    if hook not in VALID_HOOKS:
        stoprule_invalid_hook(hook)
    return hook


def get_tenant_id(hook: str) -> str:
    """Get tenant ID for a validated hook.

    Must call validate_hook() first. Pure function with no side effects.

    Args:
        hook: Validated hook name

    Returns:
        Tenant ID string from HOOK_TENANT_MAP
    """
    return HOOK_TENANT_MAP[hook]
