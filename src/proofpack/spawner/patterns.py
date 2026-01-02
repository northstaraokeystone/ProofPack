"""Pattern Storage - Store and retrieve graduated patterns.

When an agent is classified as OPEN topology and graduates:
- Extract solution pattern from agent's successful approach
- Store pattern in permanent helper registry
- Future RED gates check registry before spawning
- If matching pattern exists, apply pattern instead of spawning new helpers
"""

import json
import os
import time
import uuid
from dataclasses import dataclass

from proofpack.core.receipt import emit_receipt

# Pattern storage file (append-only JSONL like receipts)
PATTERNS_FILE = "patterns.jsonl"


@dataclass
class Pattern:
    """A graduated solution pattern."""
    pattern_id: str
    agent_type: str
    gate_color: str
    decomposition_angle: str | None
    solution_approach: dict
    created_from_agent: str
    created_at: float
    match_criteria: dict
    effectiveness: float
    use_count: int


def store_pattern(
    pattern_data: dict,
    tenant_id: str = "default",
) -> tuple[str, dict]:
    """Store a graduated pattern for future reuse.

    Returns (pattern_id, receipt)
    """
    pattern_id = str(uuid.uuid4())

    pattern = {
        "pattern_id": pattern_id,
        "tenant_id": tenant_id,
        "agent_type": pattern_data.get("agent_type", "unknown"),
        "gate_color": pattern_data.get("gate_color", "RED"),
        "decomposition_angle": pattern_data.get("decomposition_angle"),
        "solution_approach": pattern_data.get("solution_approach", {}),
        "created_from_agent": pattern_data.get("created_from_agent"),
        "created_at": pattern_data.get("created_at", time.time()),
        "match_criteria": _derive_match_criteria(pattern_data),
        "effectiveness": pattern_data.get("effectiveness", 0.85),
        "use_count": 0,
    }

    # Append to patterns file
    patterns_path = _get_patterns_path()
    with open(patterns_path, "a") as f:
        f.write(json.dumps(pattern, sort_keys=True) + "\n")

    receipt = emit_receipt("pattern_stored", {
        "tenant_id": tenant_id,
        "pattern_id": pattern_id,
        "agent_type": pattern["agent_type"],
        "gate_color": pattern["gate_color"],
        "created_from_agent": pattern["created_from_agent"],
    })

    return pattern_id, receipt


def find_matching_pattern(
    gate_color: str,
    confidence: float,
    context: dict | None = None,
    tenant_id: str = "default",
) -> tuple[Pattern | None, dict]:
    """Find a pattern that matches the current situation.

    If a matching pattern is found, it can be applied instead of spawning
    new helper agents.

    Returns (Pattern or None, search_receipt)
    """
    patterns = load_patterns(tenant_id)

    if not patterns:
        receipt = emit_receipt("pattern_search", {
            "tenant_id": tenant_id,
            "gate_color": gate_color,
            "patterns_checked": 0,
            "match_found": False,
        })
        return None, receipt

    # Find patterns that match the gate color
    candidates = [p for p in patterns if p.gate_color == gate_color]

    if not candidates:
        receipt = emit_receipt("pattern_search", {
            "tenant_id": tenant_id,
            "gate_color": gate_color,
            "patterns_checked": len(patterns),
            "match_found": False,
        })
        return None, receipt

    # Score candidates by effectiveness and context match
    best_match = None
    best_score = 0.0

    for pattern in candidates:
        score = _score_pattern_match(pattern, confidence, context)
        if score > best_score:
            best_score = score
            best_match = pattern

    # Only use pattern if score is high enough
    if best_match and best_score >= 0.7:
        # Increment use count
        _increment_use_count(best_match.pattern_id)

        receipt = emit_receipt("pattern_matched", {
            "tenant_id": tenant_id,
            "pattern_id": best_match.pattern_id,
            "gate_color": gate_color,
            "match_score": best_score,
            "use_count": best_match.use_count + 1,
        })
        return best_match, receipt

    receipt = emit_receipt("pattern_search", {
        "tenant_id": tenant_id,
        "gate_color": gate_color,
        "patterns_checked": len(patterns),
        "match_found": False,
        "best_score": best_score,
    })
    return None, receipt


def load_patterns(tenant_id: str | None = None) -> list[Pattern]:
    """Load all patterns from storage."""
    patterns_path = _get_patterns_path()

    if not os.path.exists(patterns_path):
        return []

    patterns = []
    with open(patterns_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if tenant_id and data.get("tenant_id") != tenant_id:
                    continue
                patterns.append(_dict_to_pattern(data))
            except json.JSONDecodeError:
                continue

    return patterns


def get_pattern(pattern_id: str) -> Pattern | None:
    """Get a specific pattern by ID."""
    patterns = load_patterns()
    for p in patterns:
        if p.pattern_id == pattern_id:
            return p
    return None


def apply_pattern(
    pattern: Pattern,
    tenant_id: str = "default",
) -> tuple[dict, dict]:
    """Apply a stored pattern to solve a problem.

    Returns (solution_result, receipt)
    """
    # The solution approach from the pattern
    solution = pattern.solution_approach.copy()
    solution["applied_from_pattern"] = pattern.pattern_id

    receipt = emit_receipt("pattern_applied", {
        "tenant_id": tenant_id,
        "pattern_id": pattern.pattern_id,
        "decomposition_angle": pattern.decomposition_angle,
        "effectiveness": pattern.effectiveness,
    })

    return solution, receipt


def list_patterns(
    gate_color: str | None = None,
    tenant_id: str = "default",
) -> list[dict]:
    """List all patterns, optionally filtered by gate color."""
    patterns = load_patterns(tenant_id)

    if gate_color:
        patterns = [p for p in patterns if p.gate_color == gate_color]

    return [
        {
            "pattern_id": p.pattern_id,
            "agent_type": p.agent_type,
            "gate_color": p.gate_color,
            "decomposition_angle": p.decomposition_angle,
            "effectiveness": p.effectiveness,
            "use_count": p.use_count,
            "created_at": p.created_at,
        }
        for p in patterns
    ]


def _get_patterns_path() -> str:
    """Get the path to the patterns file."""
    # Store in project root by default
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        PATTERNS_FILE,
    )


def _derive_match_criteria(pattern_data: dict) -> dict:
    """Derive matching criteria from pattern data."""
    return {
        "gate_color": pattern_data.get("gate_color"),
        "confidence_range": [0.0, 0.7] if pattern_data.get("gate_color") == "RED" else None,
        "decomposition_angle": pattern_data.get("decomposition_angle"),
    }


def _score_pattern_match(
    pattern: Pattern,
    confidence: float,
    context: dict | None,
) -> float:
    """Score how well a pattern matches the current situation."""
    score = 0.0

    # Base score from effectiveness
    score += pattern.effectiveness * 0.5

    # Bonus for high use count (battle-tested)
    if pattern.use_count >= 10:
        score += 0.2
    elif pattern.use_count >= 3:
        score += 0.1

    # Context matching (if available)
    if context and pattern.match_criteria:
        matching_keys = 0
        total_keys = 0
        for key, value in pattern.match_criteria.items():
            if value is None:
                continue
            total_keys += 1
            if key in context and context[key] == value:
                matching_keys += 1
        if total_keys > 0:
            score += 0.3 * (matching_keys / total_keys)

    return min(1.0, score)


def _dict_to_pattern(data: dict) -> Pattern:
    """Convert a dict to a Pattern object."""
    return Pattern(
        pattern_id=data.get("pattern_id", ""),
        agent_type=data.get("agent_type", "unknown"),
        gate_color=data.get("gate_color", "RED"),
        decomposition_angle=data.get("decomposition_angle"),
        solution_approach=data.get("solution_approach", {}),
        created_from_agent=data.get("created_from_agent", ""),
        created_at=data.get("created_at", 0),
        match_criteria=data.get("match_criteria", {}),
        effectiveness=data.get("effectiveness", 0.85),
        use_count=data.get("use_count", 0),
    )


def _increment_use_count(pattern_id: str) -> None:
    """Increment the use count for a pattern.

    Note: This is a simple implementation that rewrites the file.
    Production would use a database.
    """
    patterns_path = _get_patterns_path()
    if not os.path.exists(patterns_path):
        return

    lines = []
    with open(patterns_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("pattern_id") == pattern_id:
                    data["use_count"] = data.get("use_count", 0) + 1
                lines.append(json.dumps(data, sort_keys=True))
            except json.JSONDecodeError:
                lines.append(line)

    with open(patterns_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def clear_patterns() -> None:
    """Clear all patterns (for testing)."""
    patterns_path = _get_patterns_path()
    if os.path.exists(patterns_path):
        os.remove(patterns_path)
