"""Genesis Module - Synthesize helper blueprints from wound patterns.

ARCHITECT agent logic: Convert wound patterns into actionable helper
blueprints with triggers, actions, and validation criteria.
"""

import uuid
from collections import Counter

from proofpack.core.receipt import emit_receipt

# Protected components (cannot be modified by helpers)
PROTECTED = [
    "loop.cycle",
    "loop.gate",
    "loop.completeness",
    "ledger.anchor",
    "anchor.dual_hash",
]


def synthesize_helper(
    wound_pattern: dict,
    wound_receipts: list,
) -> dict:
    """Create helper blueprint from wound pattern.

    Extracts trigger, action, and parameters from resolution patterns.

    Args:
        wound_pattern: Pattern dict from harvest (problem_type, count, etc.)
        wound_receipts: List of wound receipts that match this pattern

    Returns:
        Helper blueprint dict with all required fields
    """
    blueprint_id = str(uuid.uuid4())
    problem_type = wound_pattern.get("problem_type", "unknown")

    # Extract trigger and action from wound patterns
    trigger = extract_trigger(wound_receipts)
    action = extract_action(wound_receipts)

    # Calculate risk and autonomy
    risk_score = _calculate_blueprint_risk(wound_pattern, wound_receipts)
    autonomy = _determine_autonomy(risk_score)

    # Backtest against historical wounds
    backtest_result = backtest(
        {"trigger": trigger, "action": action},
        wound_receipts,
    )

    # Calculate total human hours saved
    total_resolve_ms = sum(
        w.get("time_to_resolve_ms", 0) for w in wound_receipts
    )
    total_hours_saved = total_resolve_ms / 3600000

    blueprint = {
        "blueprint_id": blueprint_id,
        "name": f"helper_{problem_type}",
        "origin": {
            "gap_count": len(wound_receipts),
            "total_human_hours_saved": round(total_hours_saved, 2),
            "wound_receipt_ids": [
                w.get("payload_hash", "") for w in wound_receipts[:20]
            ],
        },
        "pattern": {
            "trigger": trigger,
            "action": action,
            "parameters": _extract_parameters(wound_receipts),
        },
        "validation": {
            "backtested_gaps": backtest_result.get("backtested_count", 0),
            "would_have_resolved": backtest_result.get("would_have_resolved", 0),
            "success_rate": backtest_result.get("success_rate", 0.0),
        },
        "risk_score": risk_score,
        "autonomy": autonomy,
        "requires_approval": risk_score >= 0.2,  # Auto-approve only <0.2
        "status": "proposed",
    }

    # Emit helper_blueprint receipt (L4)
    emit_receipt(
        "helper_blueprint",
        {
            "tenant_id": wound_pattern.get("tenant_id", "default"),
            "blueprint_id": blueprint_id,
            "name": blueprint["name"],
            "origin": blueprint["origin"],
            "pattern": blueprint["pattern"],
            "validation": blueprint["validation"],
            "risk_score": risk_score,
            "autonomy": autonomy,
            "requires_approval": blueprint["requires_approval"],
            "status": "proposed",
        },
    )

    return blueprint


def validate_blueprint(blueprint: dict) -> bool:
    """Validate a helper blueprint.

    Checks:
    - Required fields present
    - Not targeting PROTECTED components
    - Action is known/valid

    Args:
        blueprint: Blueprint dict to validate

    Returns:
        True if valid, False otherwise
    """
    # Required fields
    required_fields = [
        "blueprint_id",
        "name",
        "pattern",
        "risk_score",
        "autonomy",
        "status",
    ]
    for field in required_fields:
        if field not in blueprint:
            return False

    # Pattern must have trigger and action
    pattern = blueprint.get("pattern", {})
    if not pattern.get("trigger") or not pattern.get("action"):
        return False

    # Check if targeting protected components
    action = pattern.get("action", "")
    trigger = pattern.get("trigger", "")

    for protected in PROTECTED:
        if protected in action or protected in trigger:
            return False

    # Risk score must be valid
    risk = blueprint.get("risk_score", -1)
    if not 0 <= risk <= 1:
        return False

    # Autonomy must be valid
    if blueprint.get("autonomy") not in ("low", "medium", "high"):
        return False

    return True


def backtest(
    blueprint: dict,
    historical_wounds: list,
) -> dict:
    """Simulate blueprint against historical wounds.

    Args:
        blueprint: Blueprint with trigger and action
        historical_wounds: List of wound receipts to test against

    Returns:
        Dict with backtested_count, would_have_resolved, success_rate
    """
    if not historical_wounds:
        return {
            "backtested_count": 0,
            "would_have_resolved": 0,
            "success_rate": 0.0,
        }

    trigger = blueprint.get("trigger", "")
    action = blueprint.get("action", "")

    # Simulate: would this blueprint have matched the wound?
    matched = 0
    would_resolve = 0

    for wound in historical_wounds:
        # Check if trigger would match
        problem_type = wound.get("problem_type", "")
        if trigger and problem_type and trigger in problem_type:
            matched += 1

            # Check if action matches resolution
            resolution = wound.get("resolution_action", "")
            if action and resolution and action in resolution:
                would_resolve += 1

    # If no specific trigger, assume all match
    if not trigger:
        matched = len(historical_wounds)
        would_resolve = sum(
            1 for w in historical_wounds if w.get("could_automate", False)
        )

    success_rate = would_resolve / matched if matched > 0 else 0.0

    return {
        "backtested_count": matched,
        "would_have_resolved": would_resolve,
        "success_rate": round(success_rate, 3),
    }


def extract_trigger(wounds: list) -> str:
    """Analyze wound patterns to extract trigger condition.

    Args:
        wounds: List of wound receipts

    Returns:
        Trigger condition string
    """
    if not wounds:
        return ""

    # Find common problem types
    problem_types = [w.get("problem_type", "") for w in wounds if w.get("problem_type")]

    if not problem_types:
        return ""

    # Most common problem type becomes the trigger
    type_counts = Counter(problem_types)
    most_common = type_counts.most_common(1)[0][0]

    return f"problem_type == '{most_common}'"


def extract_action(wounds: list) -> str:
    """Analyze resolution_action patterns to extract action.

    Args:
        wounds: List of wound receipts

    Returns:
        Action string
    """
    if not wounds:
        return ""

    # Find common resolution actions
    actions = [
        w.get("resolution_action", "") for w in wounds if w.get("resolution_action")
    ]

    if not actions:
        return ""

    # Most common action
    action_counts = Counter(actions)
    most_common = action_counts.most_common(1)[0][0]

    return most_common


def _extract_parameters(wounds: list) -> dict:
    """Extract common parameters from wound resolutions.

    Args:
        wounds: List of wound receipts

    Returns:
        Dict of parameters
    """
    params = {}

    # Extract common resolution steps
    all_steps = []
    for wound in wounds:
        steps = wound.get("resolution_steps", [])
        if steps:
            all_steps.extend(steps)

    if all_steps:
        # Find most common steps
        step_counts = Counter(all_steps)
        common_steps = [s for s, c in step_counts.most_common(5) if c >= 2]
        if common_steps:
            params["common_steps"] = common_steps

    return params


def _calculate_blueprint_risk(wound_pattern: dict, wounds: list) -> float:
    """Calculate risk score for a blueprint.

    Factors:
    - Consistency of resolutions (higher = lower risk)
    - Automation confidence (higher = lower risk)
    - Scope of action (broader = higher risk)

    Args:
        wound_pattern: Pattern dict
        wounds: List of wound receipts

    Returns:
        Risk score 0-1
    """
    base_risk = 0.5  # Start at medium

    # Consistency reduces risk
    actions = [w.get("resolution_action", "") for w in wounds if w.get("resolution_action")]
    if actions:
        unique_actions = len(set(actions))
        if unique_actions == 1:
            base_risk -= 0.2  # Highly consistent
        elif unique_actions <= 3:
            base_risk -= 0.1  # Reasonably consistent

    # High automation confidence reduces risk
    confidences = [w.get("automation_confidence", 0.5) for w in wounds]
    if confidences:
        avg_confidence = sum(confidences) / len(confidences)
        base_risk -= (avg_confidence - 0.5) * 0.2  # Scale by confidence

    # Many wounds = well-understood problem = lower risk
    count = wound_pattern.get("count", 0)
    if count >= 20:
        base_risk -= 0.1
    elif count >= 10:
        base_risk -= 0.05

    return max(0.0, min(1.0, base_risk))


def _determine_autonomy(risk_score: float) -> str:
    """Determine autonomy level from risk score.

    Args:
        risk_score: Risk score 0-1

    Returns:
        "low", "medium", or "high"
    """
    if risk_score < 0.2:
        return "high"  # Can operate with minimal oversight
    elif risk_score < 0.5:
        return "medium"  # Needs periodic review
    else:
        return "low"  # Needs human approval for each action
