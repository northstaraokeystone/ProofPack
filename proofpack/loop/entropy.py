"""Entropy Module - Information-theoretic primitives.

Shannon 1948, not metaphor. Entropy is the fundamental measure of
system disorder. Agents must export disorder (2nd law constraint).
If entropy reduction is visible but export is not tracked, risk is hiding.
"""

import math
from collections import Counter

from proofpack.core.receipt import emit_receipt


def system_entropy(receipts: list) -> float:
    """Calculate Shannon entropy of receipt stream.

    H = -Σ p(x) log₂ p(x)

    Args:
        receipts: List of receipt dicts with 'receipt_type' field

    Returns:
        Entropy in bits. Higher = more disorder/variety.
        Returns 0.0 for empty list or single type.
    """
    if not receipts:
        return 0.0

    # Count receipt types
    types = [r.get("receipt_type", "unknown") for r in receipts]
    counts = Counter(types)
    total = len(types)

    if total == 0:
        return 0.0

    # Shannon entropy: H = -Σ p(x) log₂ p(x)
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    return entropy


def agent_fitness(
    helper_id: str,
    receipts_before: list,
    receipts_after: list,
) -> float:
    """Calculate agent fitness as entropy reduction per action.

    Fitness = (H_before - H_after) / n_actions
    Positive = good (reduces disorder)
    Negative = bad (increases disorder)
    Zero = neutral (no effect)

    Args:
        helper_id: Identifier for the helper being measured
        receipts_before: Receipt stream before helper actions
        receipts_after: Receipt stream after helper actions

    Returns:
        Entropy reduction per action. Positive is good.
    """
    h_before = system_entropy(receipts_before)
    h_after = system_entropy(receipts_after)

    # Count actuation receipts for this helper
    n_actions = sum(
        1
        for r in receipts_after
        if r.get("receipt_type") == "actuation"
        and r.get("helper_id") == helper_id
    )

    if n_actions == 0:
        # No actions taken, return raw delta
        return h_before - h_after

    return (h_before - h_after) / n_actions


def entropy_conservation(cycle_receipts: dict) -> dict:
    """Validate entropy conservation for a cycle.

    2nd law: sum(entropy_in) = sum(entropy_out) + work_done

    If entropy reduction is visible but export is not tracked,
    risk is hiding. resource_consumed tracks WHERE entropy goes.

    Args:
        cycle_receipts: Dict with 'sensed', 'emitted', 'work' keys
            - sensed: list of input receipts
            - emitted: list of output receipts
            - work: dict with resource consumption metrics

    Returns:
        Dict with:
            - valid: bool - whether conservation holds
            - entropy_in: float - input entropy
            - entropy_out: float - output entropy
            - work: float - work done (entropy exported)
            - delta: float - conservation violation (should be ~0)
    """
    sensed = cycle_receipts.get("sensed", [])
    emitted = cycle_receipts.get("emitted", [])
    work = cycle_receipts.get("work", {})

    h_in = system_entropy(sensed)
    h_out = system_entropy(emitted)

    # Work done exports entropy (compute cycles, network calls, etc.)
    # Each unit of work allows entropy reduction
    work_entropy = _calculate_work_entropy(work)

    # Conservation: H_in = H_out + Work (approximately)
    delta = h_in - (h_out + work_entropy)

    # Allow small tolerance for floating point
    valid = abs(delta) < 0.1

    return {
        "valid": valid,
        "entropy_in": h_in,
        "entropy_out": h_out,
        "work": work_entropy,
        "delta": delta,
    }


def _calculate_work_entropy(work: dict) -> float:
    """Calculate entropy exported through work.

    Work metrics map to entropy export:
    - cpu_ms: Compute cycles export entropy
    - io_ops: I/O operations export entropy
    - network_calls: Network calls export entropy

    Args:
        work: Dict with work metrics

    Returns:
        Entropy exported through work (bits)
    """
    # Rough entropy cost per work unit (empirical)
    CPU_ENTROPY_PER_MS = 0.001
    IO_ENTROPY_PER_OP = 0.01
    NETWORK_ENTROPY_PER_CALL = 0.05

    cpu_ms = work.get("cpu_ms", 0)
    io_ops = work.get("io_ops", 0)
    network_calls = work.get("network_calls", 0)

    return (
        cpu_ms * CPU_ENTROPY_PER_MS
        + io_ops * IO_ENTROPY_PER_OP
        + network_calls * NETWORK_ENTROPY_PER_CALL
    )


def entropy_delta(receipts_t0: list, receipts_t1: list) -> float:
    """Calculate change in entropy between two timepoints.

    Args:
        receipts_t0: Receipt stream at time t0
        receipts_t1: Receipt stream at time t1

    Returns:
        Change in entropy (H_t1 - H_t0).
        Negative = system degrading (less variety, more disorder concentration)
        Positive = system diversifying
    """
    return system_entropy(receipts_t1) - system_entropy(receipts_t0)


def emit_entropy_receipt(
    tenant_id: str,
    cycle_id: str,
    conservation: dict,
    delta: float,
) -> dict:
    """Emit entropy measurement receipt.

    Args:
        tenant_id: Tenant identifier
        cycle_id: Cycle identifier
        conservation: Conservation check result
        delta: Entropy delta from previous cycle

    Returns:
        Emitted receipt
    """
    return emit_receipt(
        "entropy",
        {
            "tenant_id": tenant_id,
            "cycle_id": cycle_id,
            "conservation": conservation,
            "delta": delta,
            "valid": conservation.get("valid", False),
        },
    )
