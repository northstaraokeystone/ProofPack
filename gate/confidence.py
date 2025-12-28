"""Confidence scoring for pre-execution gating.

Calculates interpretation stability score from action plan, context, and reasoning.
"""
import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any

from ledger.core import emit_receipt
from anchor import dual_hash


@dataclass
class ActionPlan:
    """Represents a proposed action with metadata."""
    action_id: str
    action_type: str
    target: str
    parameters: dict
    reasoning_chain: list[str]


@dataclass
class ContextState:
    """Current execution context."""
    initial_hash: str
    current_hash: str
    entropy: float
    timestamp: float


@dataclass
class ReasoningHistory:
    """History of reasoning steps."""
    steps: list[dict]
    confidence_trajectory: list[float]
    question_hashes: list[str]


def calculate_entropy(data: dict | list | str) -> float:
    """Calculate Shannon entropy of data representation.

    Higher entropy = more uncertainty = lower confidence.
    """
    if isinstance(data, dict):
        text = str(sorted(data.items()))
    elif isinstance(data, list):
        text = str(data)
    else:
        text = str(data)

    if not text:
        return 0.0

    # Character frequency distribution
    freq = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1

    total = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    # Normalize to 0-1 range (max entropy for ASCII is ~7)
    return min(entropy / 7.0, 1.0)


def calculate_reasoning_stability(history: ReasoningHistory) -> float:
    """Calculate stability of reasoning over time.

    Stable reasoning = consistent confidence trajectory.
    """
    if len(history.confidence_trajectory) < 2:
        return 1.0  # Not enough data, assume stable

    # Calculate variance in confidence
    mean = sum(history.confidence_trajectory) / len(history.confidence_trajectory)
    variance = sum((x - mean) ** 2 for x in history.confidence_trajectory) / len(history.confidence_trajectory)

    # Low variance = high stability
    stability = 1.0 - min(variance * 4, 1.0)  # Scale variance to 0-1
    return stability


def detect_reasoning_loops(history: ReasoningHistory, threshold: int = 5) -> bool:
    """Detect if agent is asking same question repeatedly."""
    if len(history.question_hashes) < threshold:
        return False

    # Check for repeated patterns
    hash_counts = {}
    for h in history.question_hashes:
        hash_counts[h] = hash_counts.get(h, 0) + 1
        if hash_counts[h] >= threshold:
            return True

    return False


def calculate_confidence(
    action_plan: ActionPlan,
    context_state: ContextState,
    reasoning_history: ReasoningHistory,
    variance_score: float | None = None,
    tenant_id: str = "default"
) -> tuple[float, dict]:
    """Calculate interpretation stability score.

    Combines multiple signals:
    - Context drift (how much has changed since reasoning started)
    - Reasoning entropy (how chaotic is the decision process)
    - Reasoning stability (consistency of confidence over time)
    - Loop detection (are we stuck in a loop)
    - Monte Carlo variance (if provided)

    Returns (confidence_score: 0-1, receipt)
    """
    t0 = time.perf_counter()

    # Calculate component scores
    from .drift import measure_drift
    drift_score = measure_drift(context_state.initial_hash, context_state.current_hash)

    # Reasoning entropy
    reasoning_entropy = calculate_entropy(action_plan.reasoning_chain)

    # Reasoning stability
    stability = calculate_reasoning_stability(reasoning_history)

    # Loop detection penalty
    loop_detected = detect_reasoning_loops(reasoning_history)
    loop_penalty = 0.3 if loop_detected else 0.0

    # Combine scores
    # Base confidence from stability and low entropy
    base_confidence = (stability * 0.4) + ((1 - reasoning_entropy) * 0.3) + ((1 - drift_score) * 0.3)

    # Apply variance penalty if Monte Carlo provided
    if variance_score is not None:
        variance_penalty = min(variance_score, 0.3)
        base_confidence -= variance_penalty

    # Apply loop penalty
    base_confidence -= loop_penalty

    # Clamp to 0-1
    confidence_score = max(0.0, min(1.0, base_confidence))

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("confidence_calculation", {
        "action_id": action_plan.action_id,
        "confidence_score": confidence_score,
        "drift_score": drift_score,
        "reasoning_entropy": reasoning_entropy,
        "stability": stability,
        "loop_detected": loop_detected,
        "variance_score": variance_score,
        "calculation_ms": elapsed_ms
    }, tenant_id=tenant_id)

    return confidence_score, receipt


def stoprule_confidence_calculation_timeout(elapsed_ms: float, budget_ms: float = 50.0):
    """Stoprule if confidence calculation exceeds latency budget."""
    if elapsed_ms > budget_ms:
        emit_receipt("anomaly", {
            "metric": "confidence_latency",
            "baseline": budget_ms,
            "delta": elapsed_ms - budget_ms,
            "classification": "degradation",
            "action": "alert"
        })
