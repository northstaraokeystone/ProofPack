"""Gate commands: check, history."""
import sys
import time

import click

from .output import error_box, success_box


@click.group()
def gate():
    """Pre-execution confidence gating operations."""
    pass


@gate.command()
@click.argument('action_id')
def check(action_id: str):
    """Show gate decision for an action."""
    t0 = time.perf_counter()
    try:
        from gate.confidence import ActionPlan, ContextState, ReasoningHistory, calculate_confidence
        from gate.decision import GateThresholds, gate_decision

        # Mock action data (would load from ledger in production)
        mock_plan = ActionPlan(
            action_id=action_id,
            action_type="execution",
            target="system",
            parameters={},
            reasoning_chain=["step1", "step2"]
        )

        mock_context = ContextState(
            initial_hash="abc123",
            current_hash="abc123",
            entropy=0.1,
            timestamp=time.time()
        )

        mock_history = ReasoningHistory(
            steps=[{"step": "analyze"}],
            confidence_trajectory=[0.85, 0.87, 0.89],
            question_hashes=[]
        )

        # Calculate confidence
        confidence, _ = calculate_confidence(
            mock_plan, mock_context, mock_history
        )

        # Make gate decision
        thresholds = GateThresholds()
        result, _ = gate_decision(
            confidence,
            thresholds,
            action_id=action_id,
            context_drift=0.05,
            reasoning_entropy=0.1
        )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        decision_color = {
            "GREEN": "EXECUTE",
            "YELLOW": "EXECUTE + WATCH",
            "RED": "BLOCKED"
        }.get(result.decision.value, "UNKNOWN")

        success_box(f"Gate Decision: {result.decision.value}", [
            ("Action ID", action_id),
            ("Confidence", f"{confidence:.3f}"),
            ("Decision", decision_color),
            ("Context Drift", f"{result.context_drift:.3f}"),
            ("Reasoning Entropy", f"{result.reasoning_entropy:.3f}"),
            ("Requires Approval", str(result.requires_approval)),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof gate history")

        exit_code = 0 if result.decision.value == "GREEN" else 1 if result.decision.value == "YELLOW" else 2
        sys.exit(exit_code)

    except Exception as e:
        error_box("Gate Check: ERROR", str(e))
        sys.exit(2)


@gate.command()
@click.option('--limit', default=10, help='Number of recent decisions to show')
@click.option('--filter', 'decision_filter', type=click.Choice(['GREEN', 'YELLOW', 'RED']),
              help='Filter by decision type')
def history(limit: int, decision_filter: str | None):
    """Show recent gate decisions."""
    t0 = time.perf_counter()
    try:
        # Mock history data (would load from ledger in production)
        all_decisions = [
            {"action_id": "act_001", "decision": "GREEN", "confidence": 0.95, "ts": "2024-01-15T10:30:00Z"},
            {"action_id": "act_002", "decision": "YELLOW", "confidence": 0.82, "ts": "2024-01-15T10:29:00Z"},
            {"action_id": "act_003", "decision": "GREEN", "confidence": 0.93, "ts": "2024-01-15T10:28:00Z"},
            {"action_id": "act_004", "decision": "RED", "confidence": 0.58, "ts": "2024-01-15T10:27:00Z"},
            {"action_id": "act_005", "decision": "GREEN", "confidence": 0.97, "ts": "2024-01-15T10:26:00Z"},
        ]

        # Filter if requested
        if decision_filter:
            decisions = [d for d in all_decisions if d["decision"] == decision_filter]
        else:
            decisions = all_decisions

        decisions = decisions[:limit]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        title = f"Gate History (last {len(decisions)})"
        if decision_filter:
            title += f" - {decision_filter} only"

        print(f"\u256d\u2500 {title} " + "\u2500" * 40 + "\u256e")
        print(f"\u2502 {'Action ID':<12}\u2502 {'Decision':<8}\u2502 {'Confidence':<11}\u2502 {'Timestamp':<20}\u2502")
        print("\u251c" + "\u2500" * 12 + "\u253c" + "\u2500" * 8 + "\u253c" + "\u2500" * 11 + "\u253c" + "\u2500" * 20 + "\u2524")
        for d in decisions:
            print(f"\u2502 {d['action_id']:<12}\u2502 {d['decision']:<8}\u2502 {d['confidence']:<11.3f}\u2502 {d['ts']:<20}\u2502")
        print("\u2570" + "\u2500" * 12 + "\u2500" + "\u2500" * 8 + "\u2500" + "\u2500" * 11 + "\u2500" + "\u2500" * 20 + "\u256f")
        print(f"Duration: {elapsed_ms}ms")
        print("Next: proof gate check <action_id>")
        sys.exit(0)

    except Exception as e:
        error_box("Gate History: ERROR", str(e))
        sys.exit(2)
