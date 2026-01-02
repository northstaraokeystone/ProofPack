"""Test convergence/loop detection.

Pass criteria:
- Same question 5+ times triggers loop detection
- Convergence proof calculated correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from proofpack.loop.src.convergence import (
    ConvergenceState,
    hash_question,
    track_question,
    detect_loops,
    compute_convergence_proof
)


class TestConvergence:
    """Test convergence/loop detection."""

    def test_same_question_5x_loop_detected(self):
        """CONVERGENCE: Same question 5 times triggers loop."""
        state = ConvergenceState()
        question = "What is the error?"

        for i in range(5):
            state, detected, receipt = track_question(state, question)

        assert detected is True, "5 repeats should trigger loop detection"
        assert state.loop_detected is True
        assert state.loop_count == 5

    def test_4_repeats_no_loop(self):
        """CONVERGENCE: 4 repeats does not trigger loop."""
        state = ConvergenceState()
        question = "What is the error?"

        for i in range(4):
            state, detected, _ = track_question(state, question)

        assert detected is False, "4 repeats should not trigger loop"
        assert state.loop_detected is False

    def test_different_questions_no_loop(self):
        """CONVERGENCE: Different questions don't trigger loop."""
        state = ConvergenceState()

        for i in range(10):
            state, detected, _ = track_question(state, f"Question {i}")

        assert detected is False
        assert state.loop_detected is False

    def test_loop_receipt_emitted(self):
        """CONVERGENCE: Receipt emitted when loop detected."""
        state = ConvergenceState()
        question = "Why is this failing?"

        receipt = None
        for i in range(5):
            state, detected, r = track_question(state, question)
            if r is not None:
                receipt = r

        assert receipt is not None
        assert receipt["receipt_type"] == "convergence"
        assert receipt["loop_detected"] is True

    def test_detect_loops_batch(self):
        """CONVERGENCE: detect_loops works on batch history."""
        history = ["Q1", "Q2", "Q1", "Q3", "Q1", "Q4", "Q1", "Q5", "Q1"]  # Q1 appears 5 times

        loop_detected, receipt = detect_loops(history)

        assert loop_detected is True
        assert receipt["loop_detected"] is True

    def test_convergence_proof_calculation(self):
        """CONVERGENCE: Convergence proof reflects repetition."""
        state = ConvergenceState()

        # Add highly repetitive questions
        for _ in range(8):
            state, _, _ = track_question(state, "Same question")
        state, _, _ = track_question(state, "Different question")

        proof = compute_convergence_proof(state)

        assert proof > 0.5, f"High repetition should produce high proof, got {proof}"

    def test_convergence_proof_low_for_unique(self):
        """CONVERGENCE: Low proof for unique questions."""
        state = ConvergenceState()

        for i in range(10):
            state, _, _ = track_question(state, f"Unique question {i}")

        proof = compute_convergence_proof(state)

        assert proof < 0.3, f"Unique questions should produce low proof, got {proof}"

    def test_hash_normalization(self):
        """CONVERGENCE: Questions are normalized before hashing."""
        # Same question with different casing/spacing
        h1 = hash_question("What is the error?")
        h2 = hash_question("what is the error?")
        h3 = hash_question("  WHAT IS THE ERROR?  ")

        assert h1 == h2 == h3, "Normalized questions should have same hash"

    def test_custom_threshold(self):
        """CONVERGENCE: Custom threshold works."""
        state = ConvergenceState()
        question = "What is the error?"

        # With threshold 3, should trigger after 3 repeats
        for i in range(3):
            state, detected, _ = track_question(state, question, threshold=3)

        assert detected is True, "Should trigger with custom threshold of 3"

    def test_empty_history(self):
        """CONVERGENCE: Empty history produces zero proof."""
        state = ConvergenceState()

        proof = compute_convergence_proof(state)

        assert proof == 0.0
