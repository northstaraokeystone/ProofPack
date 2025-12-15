"""Cycle Module - Main loop orchestrator.

Executes SENSE→EMIT cycle every 60 seconds:
1. SENSE    - Query L0-L3 receipts
2. ANALYZE  - Pattern detection (HUNTER)
3. HARVEST  - Collect wounds
4. HYPOTHESIZE - Synthesize helpers (ARCHITECT)
5. GATE     - Route to approval
6. ACTUATE  - Deploy approved
7. EMIT     - Emit loop_cycle receipt (L4)
"""

import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Callable

from proofpack.core.receipt import emit_receipt, StopRule

from .sense import sense
from .analyze import analyze
from .harvest import harvest_wounds
from .genesis import synthesize_helper, validate_blueprint
from .gate import request_approval, check_approval_status, auto_decline_stale
from .actuate import execute_action, get_active_helpers
from .completeness import measure_completeness
from .entropy import system_entropy, entropy_delta, entropy_conservation

# Constants
CYCLE_INTERVAL_S = 60
CYCLE_TIMEOUT_MS = 60000  # 60 seconds max per cycle


def run_cycle(
    ledger_query_fn: Callable,
    tenant_id: str = "default",
) -> dict:
    """Execute a full SENSE→EMIT cycle.

    Args:
        ledger_query_fn: Function to query receipts
            Signature: (tenant_id: str, since: str) -> list[dict]
        tenant_id: Tenant identifier

    Returns:
        Cycle metrics dict with phase results and status
    """
    cycle_id = str(uuid.uuid4())
    cycle_start = time.perf_counter()

    # Initialize phase metrics
    phases = {
        "sense": {"receipts_found": 0, "duration_ms": 0, "status": "pending"},
        "analyze": {"anomalies": 0, "patterns": 0, "drift_signals": 0, "duration_ms": 0, "status": "pending"},
        "harvest": {"wounds_found": 0, "candidates": 0, "duration_ms": 0, "status": "pending"},
        "hypothesize": {"blueprints_proposed": 0, "duration_ms": 0, "status": "pending"},
        "gate": {"approved": 0, "deferred": 0, "rejected": 0, "duration_ms": 0, "status": "pending"},
        "actuate": {"deployed": 0, "failed": 0, "duration_ms": 0, "status": "pending"},
    }

    status = "complete"
    emitted_receipts = []

    try:
        # Check ledger availability first
        try:
            test_receipts = ledger_query_fn(tenant_id=tenant_id, since="2000-01-01T00:00:00Z")
        except Exception as e:
            emit_receipt(
                "anomaly",
                {
                    "tenant_id": tenant_id,
                    "type": "ledger_unavailable",
                    "error": str(e),
                    "severity": "high",
                },
            )
            raise StopRule(f"Ledger unavailable: {e}")

        # Phase 1: SENSE
        phase_start = time.perf_counter()
        sensed = sense(ledger_query_fn, tenant_id, since_ms=CYCLE_INTERVAL_S * 1000)
        phases["sense"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["sense"]["receipts_found"] = sum(
            len(sensed.get(f"L{i}", [])) for i in range(4)
        )
        phases["sense"]["status"] = "complete"

        # Check timeout after each phase
        if _check_timeout(cycle_start):
            status = "partial"
            raise StopRule("Cycle timeout after sense phase")

        # Phase 2: ANALYZE
        phase_start = time.perf_counter()
        analysis = analyze(sensed, tenant_id)
        phases["analyze"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["analyze"]["anomalies"] = len(analysis.get("anomalies", []))
        phases["analyze"]["patterns"] = len(analysis.get("patterns", []))
        phases["analyze"]["drift_signals"] = len(analysis.get("drift_signals", []))
        phases["analyze"]["status"] = "complete"

        if _check_timeout(cycle_start):
            status = "partial"
            raise StopRule("Cycle timeout after analyze phase")

        # Phase 3: HARVEST
        phase_start = time.perf_counter()
        wounds = harvest_wounds(ledger_query_fn, tenant_id)
        phases["harvest"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["harvest"]["wounds_found"] = len(wounds)
        phases["harvest"]["candidates"] = sum(1 for w in wounds if w.get("automation_score", 0) > 0.5)
        phases["harvest"]["status"] = "complete"

        if _check_timeout(cycle_start):
            status = "partial"
            raise StopRule("Cycle timeout after harvest phase")

        # Phase 4: HYPOTHESIZE (only if wounds found)
        phase_start = time.perf_counter()
        blueprints = []
        for wound in wounds[:3]:  # Limit to top 3 candidates per cycle
            if wound.get("automation_score", 0) > 0.5:
                # Get wound receipts for this pattern
                wound_receipts = _get_wound_receipts(ledger_query_fn, tenant_id, wound)
                if wound_receipts:
                    blueprint = synthesize_helper(wound, wound_receipts)
                    if validate_blueprint(blueprint):
                        blueprints.append(blueprint)

        phases["hypothesize"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["hypothesize"]["blueprints_proposed"] = len(blueprints)
        phases["hypothesize"]["status"] = "complete"

        if _check_timeout(cycle_start):
            status = "partial"
            raise StopRule("Cycle timeout after hypothesize phase")

        # Phase 5: GATE
        phase_start = time.perf_counter()
        gate_results = {"approved": 0, "deferred": 0, "rejected": 0}
        approved_blueprints = []

        for blueprint in blueprints:
            result = request_approval(blueprint, tenant_id)
            decision = result.get("decision", "deferred")
            gate_results[decision] = gate_results.get(decision, 0) + 1

            if decision == "approved":
                approved_blueprints.append(blueprint)

        # Auto-decline stale proposals
        declined = auto_decline_stale()
        gate_results["auto_declined"] = len(declined)

        phases["gate"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["gate"]["approved"] = gate_results["approved"]
        phases["gate"]["deferred"] = gate_results["deferred"]
        phases["gate"]["rejected"] = gate_results["rejected"]
        phases["gate"]["status"] = "complete"

        if _check_timeout(cycle_start):
            status = "partial"
            raise StopRule("Cycle timeout after gate phase")

        # Phase 6: ACTUATE
        phase_start = time.perf_counter()
        deployed = 0
        failed = 0

        for blueprint in approved_blueprints:
            try:
                result = execute_action(
                    {**blueprint, "action_type": "deploy"},
                    tenant_id,
                )
                if result.get("status") == "success":
                    deployed += 1
                else:
                    failed += 1
            except StopRule:
                failed += 1

        phases["actuate"]["duration_ms"] = int((time.perf_counter() - phase_start) * 1000)
        phases["actuate"]["deployed"] = deployed
        phases["actuate"]["failed"] = failed
        phases["actuate"]["status"] = "complete"

    except StopRule as e:
        # Emit anomaly for stoprule
        emit_receipt(
            "anomaly",
            {
                "tenant_id": tenant_id,
                "type": "cycle_stoprule",
                "message": str(e),
                "cycle_id": cycle_id,
                "severity": "medium",
            },
        )
        if status == "complete":
            status = "partial"

    except Exception as e:
        # Unexpected error
        emit_receipt(
            "anomaly",
            {
                "tenant_id": tenant_id,
                "type": "cycle_error",
                "error": str(e),
                "cycle_id": cycle_id,
                "severity": "high",
            },
        )
        status = "failed"

    # Calculate cycle duration
    cycle_duration_ms = int((time.perf_counter() - cycle_start) * 1000)

    # Measure completeness
    try:
        completeness = measure_completeness(ledger_query_fn, tenant_id, window_hours=1)
        completeness_levels = {
            f"L{i}": completeness["levels"][f"L{i}"]["coverage"]
            for i in range(5)
        }
    except Exception:
        completeness_levels = {f"L{i}": 0.0 for i in range(5)}

    # Calculate entropy delta
    all_receipts = sensed.get("all_receipts", []) if 'sensed' in dir() else []
    entropy_before = analysis.get("entropy_before", 0.0) if 'analysis' in dir() else 0.0
    entropy_after = analysis.get("entropy_after", 0.0) if 'analysis' in dir() else 0.0
    entropy_d = entropy_after - entropy_before

    # Build result
    result = {
        "receipt_type": "loop_cycle",
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant_id": tenant_id,
        "cycle_id": cycle_id,
        "phases": phases,
        "completeness": completeness_levels,
        "entropy_delta": entropy_d,
        "cycle_duration_ms": cycle_duration_ms,
        "status": status,
    }

    # Emit loop_cycle receipt (L4)
    emit_receipt("loop_cycle", result)

    return result


def start_loop(
    ledger_query_fn: Callable,
    tenant_id: str = "default",
) -> None:
    """Start daemon loop running run_cycle() every CYCLE_INTERVAL_S.

    Handles interrupts gracefully.

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
    """
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        running = False

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while running:
        cycle_start = time.time()

        try:
            run_cycle(ledger_query_fn, tenant_id)
        except Exception as e:
            # Log but don't crash
            emit_receipt(
                "anomaly",
                {
                    "tenant_id": tenant_id,
                    "type": "loop_error",
                    "error": str(e),
                    "severity": "high",
                },
            )

        # Sleep until next cycle
        elapsed = time.time() - cycle_start
        sleep_time = max(0, CYCLE_INTERVAL_S - elapsed)
        if sleep_time > 0 and running:
            time.sleep(sleep_time)


def _check_timeout(start_time: float) -> bool:
    """Check if cycle has exceeded timeout.

    Args:
        start_time: Cycle start time (perf_counter)

    Returns:
        True if timeout exceeded
    """
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return elapsed_ms > CYCLE_TIMEOUT_MS


def _get_wound_receipts(
    ledger_query_fn: Callable,
    tenant_id: str,
    wound_pattern: dict,
) -> list:
    """Get wound receipts matching a pattern.

    Args:
        ledger_query_fn: Function to query receipts
        tenant_id: Tenant identifier
        wound_pattern: Pattern dict with problem_type

    Returns:
        List of matching wound receipts
    """
    # Query recent wound receipts
    now = datetime.now(timezone.utc)
    since = (now - __import__("datetime").timedelta(days=30)).isoformat().replace("+00:00", "Z")

    all_receipts = ledger_query_fn(tenant_id=tenant_id, since=since)

    # Filter to wounds matching the pattern
    problem_type = wound_pattern.get("problem_type", "")
    wounds = [
        r
        for r in all_receipts
        if r.get("receipt_type") in ("wound", "gap", "manual_intervention")
        and r.get("problem_type", "") == problem_type
    ]

    return wounds


def _cycle_phases(
    sensed: dict,
    tenant_id: str,
    ledger_query_fn: Callable,
) -> dict:
    """Execute phases 2-6 of the cycle.

    Internal helper for testing.

    Args:
        sensed: Output from sense()
        tenant_id: Tenant identifier
        ledger_query_fn: Function to query receipts

    Returns:
        Dict with phase outputs
    """
    # Phase 2: ANALYZE
    analysis = analyze(sensed, tenant_id)

    # Phase 3: HARVEST
    wounds = harvest_wounds(ledger_query_fn, tenant_id)

    # Phase 4: HYPOTHESIZE
    blueprints = []
    for wound in wounds[:3]:
        if wound.get("automation_score", 0) > 0.5:
            wound_receipts = _get_wound_receipts(ledger_query_fn, tenant_id, wound)
            if wound_receipts:
                blueprint = synthesize_helper(wound, wound_receipts)
                if validate_blueprint(blueprint):
                    blueprints.append(blueprint)

    # Phase 5: GATE
    approved = []
    for blueprint in blueprints:
        result = request_approval(blueprint, tenant_id)
        if result.get("decision") == "approved":
            approved.append(blueprint)

    # Phase 6: ACTUATE
    deployed = []
    for blueprint in approved:
        try:
            result = execute_action(
                {**blueprint, "action_type": "deploy"},
                tenant_id,
            )
            if result.get("status") == "success":
                deployed.append(blueprint)
        except StopRule:
            pass

    return {
        "analysis": analysis,
        "wounds": wounds,
        "blueprints": blueprints,
        "approved": approved,
        "deployed": deployed,
    }
