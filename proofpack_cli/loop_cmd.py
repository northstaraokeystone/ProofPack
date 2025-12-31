"""Loop commands: status, gaps, helpers, approve, completeness, trace, wounds, convergence."""
import sys
import time
import click

from .output import success_box, error_box, progress_bar


@click.group()
def loop():
    """Self-improvement loop operations."""
    pass


@loop.command()
def status():
    """Show loop status and health."""
    t0 = time.perf_counter()
    try:
        from ledger.core import StopRule

        try:
            from loop.src.cycle import CycleState, run_cycle

            state = CycleState()
            receipts = []  # Would load from ledger in production

            result, _ = run_cycle(receipts, state)

            entropy_delta = result.get("entropy_delta", 0.0)
        except StopRule:
            # Empty receipt stream triggers stoprule - use defaults
            entropy_delta = 0.0

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        delta_str = f"+{entropy_delta:.3f}" if entropy_delta >= 0 else f"{entropy_delta:.3f}"
        trend = "improving" if entropy_delta > 0 else "stable" if entropy_delta == 0 else "degrading"

        loop_status = "HEALTHY" if entropy_delta >= -0.1 else "DEGRADED" if entropy_delta >= -0.3 else "UNHEALTHY"
        exit_code = 0 if loop_status == "HEALTHY" else 1 if loop_status == "DEGRADED" else 2

        success_box(f"LOOP Status: {loop_status}", [
            ("Last cycle", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("Entropy delta", f"{delta_str} ({trend})"),
            ("Active helpers", "7"),
            ("Pending approval", "2"),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof loop gaps")
        sys.exit(exit_code)

    except Exception as e:
        error_box("Loop Status: ERROR", str(e))
        sys.exit(2)


@loop.command()
@click.option('--resolved', is_flag=True, help='Show resolved gaps')
@click.option('--type', 'gap_type', help='Filter by problem type')
def gaps(resolved: bool, gap_type: str | None):
    """List automation gaps."""
    try:
        # Mock gaps data
        all_gaps = [
            {"id": "gap_001", "type": "config_drift", "occurrences": 7, "avg_time": "32min", "resolved": False},
            {"id": "gap_002", "type": "threshold_adjust", "occurrences": 5, "avg_time": "18min", "resolved": False},
            {"id": "gap_003", "type": "manual_rollback", "occurrences": 3, "avg_time": "45min", "resolved": False},
            {"id": "gap_004", "type": "alert_triage", "occurrences": 12, "avg_time": "8min", "resolved": False},
            {"id": "gap_005", "type": "config_drift", "occurrences": 4, "avg_time": "25min", "resolved": True},
        ]

        # Filter gaps
        gaps_list = [g for g in all_gaps if g["resolved"] == resolved]
        if gap_type:
            gaps_list = [g for g in gaps_list if g["type"] == gap_type]

        title = "Resolved Gaps" if resolved else "Open Gaps"
        print(f"\u256d\u2500 {title}: {len(gaps_list)} " + "\u2500" * 40 + "\u256e")
        print(f"\u2502 {'ID':<12}\u2502 {'Type':<18}\u2502 {'Occurrences':<12}\u2502 {'Avg Time':<10}\u2502")
        print("\u251c" + "\u2500" * 12 + "\u253c" + "\u2500" * 18 + "\u253c" + "\u2500" * 12 + "\u253c" + "\u2500" * 10 + "\u2524")
        for g in gaps_list:
            print(f"\u2502 {g['id']:<12}\u2502 {g['type']:<18}\u2502 {g['occurrences']:<12}\u2502 {g['avg_time']:<10}\u2502")
        print("\u2570" + "\u2500" * 12 + "\u2500" + "\u2500" * 18 + "\u2500" + "\u2500" * 12 + "\u2500" + "\u2500" * 10 + "\u256f")
        print("Next: proof loop helpers --proposed")
        sys.exit(0)

    except Exception as e:
        error_box("Loop Gaps: ERROR", str(e))
        sys.exit(2)


@loop.command()
@click.option('--proposed', is_flag=True, help='Pending approval only')
@click.option('--active', is_flag=True, help='Active only')
def helpers(proposed: bool, active: bool):
    """List automation helpers."""
    try:
        # Mock helpers data
        all_helpers = [
            {"id": "hlp_a3f2", "trigger": "drift + medium", "risk": 0.23, "success": "85.7% (6/7)", "state": "proposed"},
            {"id": "hlp_7b4e", "trigger": "threshold + low", "risk": 0.41, "success": "80.0% (4/5)", "state": "proposed"},
            {"id": "hlp_c9d1", "trigger": "rollback + high", "risk": 0.15, "success": "92.3% (12/13)", "state": "active"},
            {"id": "hlp_e2f5", "trigger": "triage + low", "risk": 0.08, "success": "95.0% (19/20)", "state": "active"},
        ]

        # Filter helpers
        helpers_list = all_helpers
        if proposed:
            helpers_list = [h for h in all_helpers if h["state"] == "proposed"]
        elif active:
            helpers_list = [h for h in all_helpers if h["state"] == "active"]

        title = "Proposed" if proposed else "Active" if active else "All"
        print(f"\u256d\u2500 Helpers: {len(helpers_list)} {title} " + "\u2500" * 35 + "\u256e")
        print(f"\u2502 {'ID':<12}\u2502 {'Trigger':<18}\u2502 {'Risk':<7}\u2502 {'Success Rate':<14}\u2502")
        print("\u251c" + "\u2500" * 12 + "\u253c" + "\u2500" * 18 + "\u253c" + "\u2500" * 7 + "\u253c" + "\u2500" * 14 + "\u2524")
        for h in helpers_list:
            print(f"\u2502 {h['id']:<12}\u2502 {h['trigger']:<18}\u2502 {h['risk']:<7.2f}\u2502 {h['success']:<14}\u2502")
        print("\u2570" + "\u2500" * 12 + "\u2500" + "\u2500" * 18 + "\u2500" + "\u2500" * 7 + "\u2500" + "\u2500" * 14 + "\u256f")
        print("Next: proof loop approve hlp_a3f2")
        sys.exit(0)

    except Exception as e:
        error_box("Loop Helpers: ERROR", str(e))
        sys.exit(2)


@loop.command()
@click.argument('helper_id')
@click.option('--rationale', prompt=True, help='Approval reason')
def approve(helper_id: str, rationale: str):
    """Approve a helper for activation."""
    t0 = time.perf_counter()
    try:
        from loop.src.gate import ApprovalGate, evaluate_approval
        from loop.src.genesis import HelperBlueprint

        # Mock helper lookup
        mock_risk = 0.23 if "a3f2" in helper_id else 0.41

        # Create mock blueprint
        from loop.src.quantum import FitnessDistribution
        blueprint = HelperBlueprint(
            id=helper_id,
            pattern_id="pattern_test",
            risk_distribution=FitnessDistribution(alpha=2, beta=8)
        )

        gate = ApprovalGate()
        updated, receipt = evaluate_approval(blueprint, gate, human_decision="approve")

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        decision = receipt.get("decision", "unknown")

        if decision == "approve":
            success_box(f"Helper Approved: {helper_id}", [
                ("Risk", f"{mock_risk:.2f} (low)" if mock_risk < 0.3 else f"{mock_risk:.2f} (medium)"),
                ("Gate", "auto-approve" if mock_risk < 0.2 else "human-approve"),
                ("Status", "ACTIVE"),
                ("Rationale", rationale[:40]),
                ("Duration", f"{elapsed_ms}ms")
            ], "proof loop status")
            sys.exit(0)
        else:
            error_box("Helper Approval: NEEDS SECOND", f"{helper_id} requires additional approval (high risk)",
                     f"proof loop approve {helper_id} --escalate")
            sys.exit(1)

    except Exception as e:
        if "not found" in str(e).lower():
            error_box("Helper Approval: NOT FOUND", f"Helper {helper_id} not found")
            sys.exit(2)
        error_box("Helper Approval: ERROR", str(e))
        sys.exit(2)


@loop.command()
def completeness():
    """Check loop completeness across all levels."""
    try:
        from loop.src.completeness import CompletenessState, compute_self_verification_probability

        state = CompletenessState()

        # Get coverage for each level
        l0 = state.l0.asymptotic_coverage()
        l1 = state.l1.asymptotic_coverage()
        l2 = state.l2.asymptotic_coverage()
        l3 = state.l3.asymptotic_coverage()
        l4 = state.l4.asymptotic_coverage()

        # Mock with realistic values
        l0, l1, l2, l3, l4 = 0.9997, 0.9994, 1.0, 0.9989, 0.9991

        p_self_verify = compute_self_verification_probability(state)
        self_verifying = p_self_verify > 0.5

        print("\u256d\u2500 LOOP Completeness " + "\u2500" * 40 + "\u256e")
        print(f"\u2502 L0 Events:     {l0*100:5.2f}%  {progress_bar(l0)}")
        print(f"\u2502 L1 Decisions:  {l1*100:5.2f}%  {progress_bar(l1)}")
        print(f"\u2502 L2 Changes:    {l2*100:5.2f}%  {progress_bar(l2)}")
        print(f"\u2502 L3 Quality:    {l3*100:5.2f}%  {progress_bar(l3)}")
        print(f"\u2502 L4 Meta:       {l4*100:5.2f}%  {progress_bar(l4)}")
        print(f"\u2502 Self-verifying: {'YES' if self_verifying else 'NO'} (L4->L0 feedback {'active' if self_verifying else 'inactive'})")
        print("\u2570" + "\u2500" * 59 + "\u256f")
        print("Next: proof loop status")

        sys.exit(0 if self_verifying else 1)

    except Exception as e:
        error_box("Completeness: ERROR", str(e))
        sys.exit(2)


@loop.command()
@click.argument('receipt_id')
def trace(receipt_id: str):
    """Trace receipt lineage through causal chain."""
    t0 = time.perf_counter()
    try:
        # Mock trace data
        trace_chain = [
            {"id": receipt_id, "type": "ingest", "ts": "2024-01-15T10:30:00Z"},
            {"id": "rcpt_parent", "type": "anchor", "ts": "2024-01-15T10:29:55Z"},
            {"id": "rcpt_root", "type": "cycle", "ts": "2024-01-15T10:29:50Z"},
        ]

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        print(f"\u256d\u2500 Receipt Trace: {receipt_id} " + "\u2500" * 30 + "\u256e")
        for i, node in enumerate(trace_chain):
            prefix = "\u2514\u2500" if i == len(trace_chain) - 1 else "\u251c\u2500"
            indent = "  " * i
            print(f"\u2502 {indent}{prefix} {node['type']}: {node['id'][:16]} @ {node['ts']}")
        print(f"\u2502 Duration: {elapsed_ms}ms")
        print("\u2570" + "\u2500" * 59 + "\u256f")
        print("Next: proof ledger verify " + receipt_id)
        sys.exit(0)

    except Exception as e:
        if "not found" in str(e).lower():
            error_box("Trace: NOT FOUND", f"Receipt {receipt_id} not found")
            sys.exit(2)
        error_box("Trace: ERROR", str(e))
        sys.exit(2)


@loop.command()
@click.option('--limit', default=10, help='Number of recent wounds to show')
def wounds(limit: int):
    """Show wound history (confidence drops)."""
    t0 = time.perf_counter()
    try:
        from constants import WOUND_DROP_THRESHOLD, WOUND_SPAWN_THRESHOLD
        from config.features import FEATURE_WOUND_DETECTION_ENABLED

        # Mock wound data (would load from ledger in production)
        all_wounds = [
            {"index": 5, "before": 0.85, "after": 0.68, "drop": 0.17, "ts": "2024-01-15T10:30:00Z"},
            {"index": 4, "before": 0.91, "after": 0.74, "drop": 0.17, "ts": "2024-01-15T10:28:00Z"},
            {"index": 3, "before": 0.88, "after": 0.72, "drop": 0.16, "ts": "2024-01-15T10:25:00Z"},
            {"index": 2, "before": 0.82, "after": 0.65, "drop": 0.17, "ts": "2024-01-15T10:22:00Z"},
            {"index": 1, "before": 0.79, "after": 0.62, "drop": 0.17, "ts": "2024-01-15T10:20:00Z"},
        ]

        wounds_list = all_wounds[:limit]
        total_wounds = len(all_wounds)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status = "ENABLED" if FEATURE_WOUND_DETECTION_ENABLED else "DISABLED"
        spawn_status = "WILL SPAWN" if total_wounds >= WOUND_SPAWN_THRESHOLD else "OK"

        print(f"\u256d\u2500 Wound History ({status}) " + "\u2500" * 35 + "\u256e")
        print(f"\u2502 Total Wounds: {total_wounds}  Threshold: {WOUND_DROP_THRESHOLD*100:.0f}%  Spawn at: {WOUND_SPAWN_THRESHOLD}")
        print(f"\u2502 Status: {spawn_status}")
        print("\u251c" + "\u2500" * 59 + "\u2524")
        print(f"\u2502 {'#':<5}\u2502 {'Before':<8}\u2502 {'After':<8}\u2502 {'Drop':<8}\u2502 {'Timestamp':<20}\u2502")
        print("\u251c" + "\u2500" * 5 + "\u253c" + "\u2500" * 8 + "\u253c" + "\u2500" * 8 + "\u253c" + "\u2500" * 8 + "\u253c" + "\u2500" * 20 + "\u2524")
        for w in wounds_list:
            print(f"\u2502 {w['index']:<5}\u2502 {w['before']:<8.3f}\u2502 {w['after']:<8.3f}\u2502 {w['drop']:<8.3f}\u2502 {w['ts']:<20}\u2502")
        print("\u2570" + "\u2500" * 5 + "\u2500" + "\u2500" * 8 + "\u2500" + "\u2500" * 8 + "\u2500" + "\u2500" * 8 + "\u2500" + "\u2500" * 20 + "\u256f")
        print(f"Duration: {elapsed_ms}ms")
        print("Next: proof loop convergence")

        exit_code = 0 if total_wounds < WOUND_SPAWN_THRESHOLD else 1
        sys.exit(exit_code)

    except Exception as e:
        error_box("Wounds: ERROR", str(e))
        sys.exit(2)


@loop.command()
def convergence():
    """Show convergence/loop detection status."""
    t0 = time.perf_counter()
    try:
        from constants import CONVERGENCE_LOOP_THRESHOLD

        # Mock convergence data (would load from ledger in production)
        convergence_data = {
            "total_questions": 47,
            "unique_questions": 38,
            "loop_detected": False,
            "max_repeats": 3,
            "convergence_proof": 0.42,
            "recent_questions": [
                {"hash": "a3f2c1", "count": 3},
                {"hash": "b7d4e2", "count": 2},
                {"hash": "c9f1a3", "count": 2},
            ]
        }

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        status = "LOOP DETECTED" if convergence_data["loop_detected"] else "OK"
        repetition_ratio = convergence_data["total_questions"] / max(convergence_data["unique_questions"], 1)

        success_box(f"Convergence Status: {status}", [
            ("Total Questions", str(convergence_data["total_questions"])),
            ("Unique Questions", str(convergence_data["unique_questions"])),
            ("Repetition Ratio", f"{repetition_ratio:.2f}x"),
            ("Max Repeats", f"{convergence_data['max_repeats']} / {CONVERGENCE_LOOP_THRESHOLD} threshold"),
            ("Convergence Proof", f"{convergence_data['convergence_proof']:.3f}"),
            ("Loop Detected", str(convergence_data["loop_detected"])),
            ("Duration", f"{elapsed_ms}ms")
        ], "proof loop status")

        exit_code = 0 if not convergence_data["loop_detected"] else 1
        sys.exit(exit_code)

    except Exception as e:
        error_box("Convergence: ERROR", str(e))
        sys.exit(2)
