"""Detect reasoning loops (same question asked repeatedly).

A loop is detected when the same question appears 5+ times.
"""
import hashlib
import time
from dataclasses import dataclass, field

from proofpack.core.constants import CONVERGENCE_LOOP_THRESHOLD
from proofpack.core.receipt import dual_hash, emit_receipt


@dataclass
class ConvergenceState:
    """Tracks reasoning history for loop detection."""
    question_hashes: list[str] = field(default_factory=list)
    hash_counts: dict[str, int] = field(default_factory=dict)
    loop_detected: bool = False
    loop_question_hash: str | None = None
    loop_count: int = 0


def hash_question(question: str) -> str:
    """Create a hash of a question for comparison."""
    # Normalize question (lowercase, strip whitespace)
    normalized = question.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def track_question(
    state: ConvergenceState,
    question: str,
    threshold: int = CONVERGENCE_LOOP_THRESHOLD,
    tenant_id: str = "default"
) -> tuple[ConvergenceState, bool, dict | None]:
    """Track a question, detect if it forms a loop.

    Returns (updated_state, loop_detected, receipt_if_loop)
    """
    q_hash = hash_question(question)

    # Update counts
    new_counts = state.hash_counts.copy()
    new_counts[q_hash] = new_counts.get(q_hash, 0) + 1

    # Update history
    new_history = state.question_hashes + [q_hash]

    # Check for loop
    loop_detected = new_counts[q_hash] >= threshold
    loop_question_hash = q_hash if loop_detected else state.loop_question_hash
    loop_count = new_counts[q_hash] if loop_detected else state.loop_count

    # Create receipt only if loop newly detected
    receipt = None
    if loop_detected and not state.loop_detected:
        receipt = emit_receipt("convergence", {
            "loop_detected": True,
            "question_hash": q_hash,
            "repeat_count": new_counts[q_hash],
            "threshold": threshold,
            "payload_hash": dual_hash(f"loop:{q_hash}:{new_counts[q_hash]}")
        }, tenant_id=tenant_id)

    new_state = ConvergenceState(
        question_hashes=new_history,
        hash_counts=new_counts,
        loop_detected=loop_detected,
        loop_question_hash=loop_question_hash,
        loop_count=loop_count
    )

    return new_state, loop_detected, receipt


def detect_loops(
    reasoning_history: list[str],
    threshold: int = CONVERGENCE_LOOP_THRESHOLD,
    tenant_id: str = "default"
) -> tuple[bool, dict]:
    """Check a reasoning history for loops.

    Returns (loop_detected, receipt)
    """
    t0 = time.perf_counter()

    state = ConvergenceState()
    loop_detected = False
    loop_hash = None

    for question in reasoning_history:
        state, detected, _ = track_question(state, question, threshold, tenant_id)
        if detected:
            loop_detected = True
            loop_hash = state.loop_question_hash

    elapsed_ms = (time.perf_counter() - t0) * 1000

    receipt = emit_receipt("loop_analysis", {
        "loop_detected": loop_detected,
        "questions_analyzed": len(reasoning_history),
        "unique_questions": len(state.hash_counts),
        "loop_hash": loop_hash,
        "analysis_ms": elapsed_ms,
        "payload_hash": dual_hash(f"analysis:{loop_detected}:{len(reasoning_history)}")
    }, tenant_id=tenant_id)

    return loop_detected, receipt


def compute_convergence_proof(
    state: ConvergenceState
) -> float:
    """Compute convergence proof score (0-1).

    Higher score = more evidence of convergence/looping.
    """
    if not state.hash_counts:
        return 0.0

    # Calculate repetition ratio
    total_questions = len(state.question_hashes)
    unique_questions = len(state.hash_counts)

    if total_questions == 0:
        return 0.0

    # Repetition ratio: 1 means all unique, higher means more repeats
    repetition_ratio = total_questions / max(unique_questions, 1)

    # Max repetition
    max_repeats = max(state.hash_counts.values()) if state.hash_counts else 0

    # Combine signals
    # High repetition ratio + high max repeats = high convergence proof
    ratio_score = min((repetition_ratio - 1) / 4, 1.0)  # 5x repetition = 1.0
    repeat_score = min(max_repeats / 10, 1.0)  # 10 repeats = 1.0

    convergence_proof = (ratio_score * 0.4) + (repeat_score * 0.6)

    return min(convergence_proof, 1.0)


def stoprule_infinite_loop(
    state: ConvergenceState,
    critical_threshold: int = 10
):
    """Stoprule if a question is repeated critically many times."""
    if state.loop_count >= critical_threshold:
        emit_receipt("anomaly", {
            "metric": "loop_count",
            "baseline": critical_threshold,
            "delta": state.loop_count - critical_threshold,
            "classification": "anti_pattern",
            "action": "halt"
        })
