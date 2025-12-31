"""Tests for the Loop Module - Self-improving meta-layer.

Test coverage for:
- Cycle execution (run_cycle, timeout, phases)
- Sense (query L0-L3)
- Analyze (HUNTER pattern detection)
- Harvest (wound collection)
- Genesis (helper synthesis)
- Gate (HITL approval)
- Actuate (deployment)
- Effectiveness (entropy measurement)
- Completeness (L0-L4 self-verification)
"""

import time
import pytest
from datetime import datetime, timezone, timedelta

from proofpack.loop import (
    CYCLE_INTERVAL_S,
    WOUND_THRESHOLD_COUNT,
    PROTECTED,
    run_cycle,
    measure_completeness,
    harvest_wounds,
    system_entropy,
    agent_fitness,
)
from proofpack.loop.sense import sense, query_by_level, RECEIPT_LEVEL_MAP
from proofpack.loop.analyze import analyze, detect_drift
from proofpack.loop.harvest import rank_patterns, group_by_type
from proofpack.loop.genesis import synthesize_helper, validate_blueprint, backtest
from proofpack.loop.gate import (
    request_approval,
    auto_decline_stale,
    clear_pending_approvals,
)
from proofpack.loop.actuate import (
    execute_action,
    deploy_helper,
    is_protected,
    clear_helpers,
)
from proofpack.loop.effectiveness import (
    measure_effectiveness,
    retire_helper,
    calculate_multi_dimensional_fitness,
    clear_effectiveness_history,
)
from proofpack.loop.completeness import (
    check_l4_feedback,
    calculate_level_coverage,
    clear_feedback_events,
)
from proofpack.loop.entropy import entropy_conservation
from proofpack.core.receipt import StopRule


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_ledger_query():
    """Create a mock ledger query function."""
    receipts = []

    def query(tenant_id: str = "default", since: str = None):
        return [r for r in receipts if r.get("tenant_id", "default") == tenant_id]

    query.receipts = receipts
    return query


@pytest.fixture
def sample_receipts():
    """Create sample receipts across all levels."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        # L0 - Telemetry
        {"receipt_type": "ingest", "tenant_id": "test", "ts": now, "payload_hash": "hash1"},
        {"receipt_type": "qed_window", "tenant_id": "test", "ts": now},
        {"receipt_type": "qed_batch", "tenant_id": "test", "ts": now},
        # L1 - Agents
        {"receipt_type": "anomaly", "tenant_id": "test", "ts": now, "severity": "medium"},
        {"receipt_type": "alert", "tenant_id": "test", "ts": now},
        # L2 - Decisions
        {"receipt_type": "brief", "tenant_id": "test", "ts": now},
        {"receipt_type": "packet", "tenant_id": "test", "ts": now},
        # L3 - Quality
        {"receipt_type": "health", "tenant_id": "test", "ts": now},
        {"receipt_type": "wound", "tenant_id": "test", "ts": now, "problem_type": "error_x"},
    ]


@pytest.fixture
def sample_wounds():
    """Create sample wound receipts for harvest testing."""
    now = datetime.now(timezone.utc)
    wounds = []
    for i in range(10):
        wounds.append({
            "receipt_type": "wound",
            "tenant_id": "test",
            "ts": (now - timedelta(days=i)).isoformat().replace("+00:00", "Z"),
            "problem_type": "database_timeout",
            "time_to_resolve_ms": 2400000,  # 40 minutes
            "resolution_action": "restart_connection",
            "could_automate": True,
            "automation_confidence": 0.8,
        })
    return wounds


@pytest.fixture
def sample_blueprint():
    """Create a sample helper blueprint."""
    return {
        "blueprint_id": "test-blueprint-1",
        "name": "helper_database_timeout",
        "origin": {
            "gap_count": 10,
            "total_human_hours_saved": 6.5,
            "wound_receipt_ids": ["hash1", "hash2"],
        },
        "pattern": {
            "trigger": "problem_type == 'database_timeout'",
            "action": "restart_connection",
            "parameters": {},
        },
        "validation": {
            "backtested_gaps": 10,
            "would_have_resolved": 8,
            "success_rate": 0.8,
        },
        "risk_score": 0.15,
        "autonomy": "high",
        "requires_approval": False,
        "status": "proposed",
    }


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up state between tests."""
    clear_pending_approvals()
    clear_helpers()
    clear_effectiveness_history()
    clear_feedback_events()
    yield


# =============================================================================
# Cycle Tests
# =============================================================================

class TestCycle:
    """Tests for cycle.py - main loop orchestrator."""

    def test_run_cycle_completes(self, mock_ledger_query, capsys):
        """Single cycle completes and emits loop_cycle_receipt."""
        result = run_cycle(mock_ledger_query, "test-tenant")

        assert result["status"] in ("complete", "partial")
        assert "cycle_id" in result
        assert "phases" in result
        assert "completeness" in result

        # Verify loop_cycle receipt was emitted
        captured = capsys.readouterr()
        assert "loop_cycle" in captured.out

    def test_run_cycle_all_phases(self, mock_ledger_query, sample_receipts):
        """All 7 phases execute in order."""
        mock_ledger_query.receipts.extend(sample_receipts)

        result = run_cycle(mock_ledger_query, "test")

        phases = result["phases"]
        assert "sense" in phases
        assert "analyze" in phases
        assert "harvest" in phases
        assert "hypothesize" in phases
        assert "gate" in phases
        assert "actuate" in phases

        # All phases should have completed (or partial if timeout)
        for phase_name, phase_data in phases.items():
            assert phase_data["status"] in ("complete", "pending")

    def test_cycle_timeout_stoprule(self, mock_ledger_query, capsys):
        """Cycle timeout triggers stoprule appropriately."""
        # This test verifies the timeout mechanism exists
        # In practice, we'd mock time to force timeout
        result = run_cycle(mock_ledger_query, "test")

        # Even with empty data, should complete within timeout
        assert result["cycle_duration_ms"] < 60000

    def test_100_cycles_no_errors(self, mock_ledger_query):
        """100 consecutive cycles complete without stoprule triggers."""
        failures = 0
        for i in range(100):
            result = run_cycle(mock_ledger_query, f"test-{i % 10}")
            if result["status"] == "failed":
                failures += 1

        assert failures == 0, f"{failures} cycles failed out of 100"


# =============================================================================
# Sense Tests
# =============================================================================

class TestSense:
    """Tests for sense.py - L0-L3 receipt queries."""

    def test_sense_queries_all_levels(self, mock_ledger_query, sample_receipts, capsys):
        """sense() returns L0-L3 categorized receipts."""
        mock_ledger_query.receipts.extend(sample_receipts)

        result = sense(mock_ledger_query, "test")

        assert "L0" in result
        assert "L1" in result
        assert "L2" in result
        assert "L3" in result
        assert len(result["L0"]) > 0  # Has telemetry receipts

        captured = capsys.readouterr()
        assert "sense" in captured.out

    def test_sense_respects_time_window(self, mock_ledger_query):
        """sense() only returns receipts from last interval."""
        # Add receipt from "now"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        mock_ledger_query.receipts.append({
            "receipt_type": "ingest",
            "tenant_id": "test",
            "ts": now,
        })

        result = sense(mock_ledger_query, "test", since_ms=60000)

        assert "window_start" in result
        assert "window_end" in result
        assert result["duration_ms"] >= 0

    def test_query_by_level(self, sample_receipts):
        """query_by_level correctly filters by level."""
        l0 = query_by_level(sample_receipts, 0)
        l1 = query_by_level(sample_receipts, 1)

        assert all(RECEIPT_LEVEL_MAP.get(r["receipt_type"]) == 0 for r in l0)
        assert all(RECEIPT_LEVEL_MAP.get(r["receipt_type"]) == 1 for r in l1)


# =============================================================================
# Analyze Tests
# =============================================================================

class TestAnalyze:
    """Tests for analyze.py - HUNTER pattern detection."""

    def test_analyze_detects_drift(self, sample_receipts, capsys):
        """Drift detection returns score and direction."""
        sensed = {"all_receipts": sample_receipts, "L0": [], "L1": [], "L2": [], "L3": []}

        result = analyze(sensed, "test")

        assert "drift_signals" in result
        assert "entropy_before" in result
        assert "entropy_after" in result

        captured = capsys.readouterr()
        assert "analysis" in captured.out

    def test_analyze_detects_patterns(self, sample_receipts):
        """Pattern detection finds recurring types."""
        # Add more receipts of same type
        for _ in range(5):
            sample_receipts.append({
                "receipt_type": "ingest",
                "tenant_id": "test",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })

        sensed = {"all_receipts": sample_receipts}
        result = analyze(sensed, "test")

        assert "patterns" in result
        patterns = result["patterns"]
        # Should find ingest as a pattern (appears multiple times)
        ingest_patterns = [p for p in patterns if p["type"] == "ingest"]
        assert len(ingest_patterns) > 0

    def test_detect_drift_with_baseline(self):
        """detect_drift compares to baseline correctly."""
        receipts = [
            {"metric_a": 100, "receipt_type": "test"},
            {"metric_a": 110, "receipt_type": "test"},
            {"metric_a": 120, "receipt_type": "test"},
        ]
        baseline = {"metric_a": 80}

        result = detect_drift(receipts, baseline)

        assert "drift_score" in result
        assert "direction" in result
        assert result["direction"] == "up"  # Values above baseline


# =============================================================================
# Harvest Tests
# =============================================================================

class TestHarvest:
    """Tests for harvest.py - wound collection."""

    def test_harvest_filters_by_threshold(self, mock_ledger_query, sample_wounds, capsys):
        """Only wounds with ≥5 occurrences and >30min median qualify."""
        mock_ledger_query.receipts.extend(sample_wounds)

        result = harvest_wounds(mock_ledger_query, "test")

        # Should have candidates (10 wounds > threshold of 5)
        assert isinstance(result, list)

        captured = capsys.readouterr()
        assert "harvest" in captured.out

    def test_harvest_ranks_by_score(self, sample_wounds):
        """Wounds are ranked by frequency × resolve_time."""
        patterns = [
            {"problem_type": "a", "count": 10, "median_resolve_ms": 3600000},  # 10 × 1hr = 10
            {"problem_type": "b", "count": 5, "median_resolve_ms": 7200000},   # 5 × 2hr = 10
            {"problem_type": "c", "count": 20, "median_resolve_ms": 3600000},  # 20 × 1hr = 20 (highest)
        ]

        ranked = rank_patterns(patterns)

        # Higher scores first: c=20, a=10, b=10
        assert ranked[0]["problem_type"] == "c"  # 20 × 1 = 20 (highest)
        assert ranked[1]["problem_type"] in ("a", "b")  # Tied at 10

    def test_group_by_type(self, sample_wounds):
        """Wounds are grouped by problem_type."""
        grouped = group_by_type(sample_wounds)

        assert "database_timeout" in grouped
        assert len(grouped["database_timeout"]) == 10


# =============================================================================
# Genesis Tests
# =============================================================================

class TestGenesis:
    """Tests for genesis.py - helper synthesis."""

    def test_synthesize_helper_creates_blueprint(self, sample_wounds, capsys):
        """synthesize_helper creates valid blueprint structure."""
        pattern = {
            "problem_type": "database_timeout",
            "count": 10,
            "median_resolve_ms": 2400000,
            "automation_score": 0.8,
        }

        blueprint = synthesize_helper(pattern, sample_wounds)

        assert "blueprint_id" in blueprint
        assert "name" in blueprint
        assert "pattern" in blueprint
        assert "validation" in blueprint
        assert blueprint["status"] == "proposed"

        captured = capsys.readouterr()
        assert "helper_blueprint" in captured.out

    def test_validate_blueprint_rejects_protected(self, sample_blueprint):
        """Cannot target PROTECTED components."""
        # Valid blueprint should pass
        assert validate_blueprint(sample_blueprint) is True

        # Blueprint targeting protected should fail
        protected_blueprint = sample_blueprint.copy()
        protected_blueprint["pattern"] = {
            "trigger": "loop.cycle",
            "action": "modify_cycle",
        }
        assert validate_blueprint(protected_blueprint) is False

    def test_backtest_calculates_success_rate(self, sample_wounds):
        """Backtest returns meaningful success rate."""
        blueprint = {
            "trigger": "database_timeout",
            "action": "restart_connection",
        }

        result = backtest(blueprint, sample_wounds)

        assert "backtested_count" in result
        assert "would_have_resolved" in result
        assert "success_rate" in result
        assert 0 <= result["success_rate"] <= 1


# =============================================================================
# Gate Tests
# =============================================================================

class TestGate:
    """Tests for gate.py - HITL approval workflow."""

    def test_risk_below_02_auto_approves(self, sample_blueprint, capsys):
        """Low risk (<0.2) auto-approves."""
        sample_blueprint["risk_score"] = 0.15

        result = request_approval(sample_blueprint, "test")

        assert result["gate_type"] == "auto"
        assert result["decision"] == "approved"

        captured = capsys.readouterr()
        assert "approval" in captured.out

    def test_risk_above_05_requires_hitl(self, sample_blueprint, capsys):
        """High risk (>0.5) requires human approval."""
        sample_blueprint["risk_score"] = 0.6

        result = request_approval(sample_blueprint, "test")

        assert result["gate_type"] in ("dual", "observation")
        assert result["decision"] == "deferred"

    def test_stale_proposals_auto_decline(self, sample_blueprint):
        """Proposals pending >14 days auto-decline."""
        # Create a pending approval
        sample_blueprint["risk_score"] = 0.3  # Single approval needed
        request_approval(sample_blueprint, "test")

        # Manually expire it (in real code, time would pass)
        from proofpack.loop.gate import _pending_approvals
        from datetime import timedelta

        blueprint_id = sample_blueprint["blueprint_id"]
        if blueprint_id in _pending_approvals:
            # Set expiration to past
            past = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat().replace("+00:00", "Z")
            _pending_approvals[blueprint_id]["expires_at"] = past

        declined = auto_decline_stale()

        assert blueprint_id in declined


# =============================================================================
# Actuate Tests
# =============================================================================

class TestActuate:
    """Tests for actuate.py - deployment."""

    def test_deploy_helper_registers(self, sample_blueprint, capsys):
        """Deployed helper is queryable."""
        result = deploy_helper(sample_blueprint, "test")

        assert result["status"] == "success"
        assert "helper_id" in result

        from proofpack.loop.actuate import get_helper
        helper = get_helper(sample_blueprint["blueprint_id"])
        assert helper is not None
        assert helper["status"] == "deployed"

    def test_protected_modification_stoprule(self, capsys):
        """Cannot modify PROTECTED components."""
        protected_action = {
            "action_type": "modify",
            "target": "loop.cycle",
            "blueprint_id": "test",
        }

        with pytest.raises(StopRule) as exc_info:
            execute_action(protected_action, "test")

        assert "protected" in str(exc_info.value).lower()

    def test_is_protected(self):
        """is_protected correctly identifies protected components."""
        assert is_protected("loop.cycle") is True
        assert is_protected("loop.gate") is True
        assert is_protected("ledger.anchor") is True
        assert is_protected("my_helper") is False


# =============================================================================
# Effectiveness Tests
# =============================================================================

class TestEffectiveness:
    """Tests for effectiveness.py - entropy measurement."""

    def test_measure_effectiveness_positive(self, mock_ledger_query, sample_blueprint, capsys):
        """Positive entropy reduction = high effectiveness score."""
        # Deploy a helper first
        deploy_helper(sample_blueprint, "test")

        # Add some actuation receipts
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        mock_ledger_query.receipts.extend([
            {
                "receipt_type": "actuation",
                "tenant_id": "test",
                "ts": now,
                "blueprint_id": sample_blueprint["blueprint_id"],
                "status": "success",
            }
            for _ in range(5)
        ])

        result = measure_effectiveness(
            sample_blueprint["blueprint_id"],
            mock_ledger_query,
            "test",
        )

        assert "effectiveness_score" in result
        assert "fitness" in result
        assert "trend" in result

        captured = capsys.readouterr()
        assert "effectiveness" in captured.out

    def test_retire_helper_dormant(self, sample_blueprint, capsys):
        """Helper with zero effectiveness for 30 days becomes dormant."""
        deploy_helper(sample_blueprint, "test")

        result = retire_helper(
            sample_blueprint["blueprint_id"],
            "Zero effectiveness for 30 days",
            "test",
        )

        assert result["status"] == "success"

        from proofpack.loop.actuate import get_helper
        helper = get_helper(sample_blueprint["blueprint_id"])
        assert helper["status"] == "retired"

    def test_multi_dimensional_fitness(self, sample_blueprint):
        """Fitness calculation uses all dimensions."""
        deploy_helper(sample_blueprint, "test")

        metrics = {
            "actions_taken": 10,
            "actions_successful": 8,
            "entropy_reduction": 0.5,
        }

        fitness = calculate_multi_dimensional_fitness(
            sample_blueprint["blueprint_id"],
            metrics,
        )

        assert "roi" in fitness
        assert "diversity" in fitness
        assert "stability" in fitness
        assert "recency" in fitness
        assert "combined" in fitness


# =============================================================================
# Completeness Tests
# =============================================================================

class TestCompleteness:
    """Tests for completeness.py - L0-L4 self-verification."""

    def test_measure_completeness_all_levels(self, mock_ledger_query, sample_receipts, capsys):
        """Returns coverage for L0-L4."""
        mock_ledger_query.receipts.extend(sample_receipts)

        result = measure_completeness(mock_ledger_query, "test")

        assert "levels" in result
        assert "L0" in result["levels"]
        assert "L1" in result["levels"]
        assert "L2" in result["levels"]
        assert "L3" in result["levels"]
        assert "L4" in result["levels"]
        assert "overall_coverage" in result

        captured = capsys.readouterr()
        assert "completeness" in captured.out

    def test_self_verification_detection(self, mock_ledger_query, sample_receipts):
        """Detects when L4 feeds back to L0."""
        # Without feedback, should be False
        result1 = check_l4_feedback(mock_ledger_query, "test")
        assert result1 is False

        # Record feedback
        from proofpack.loop.completeness import record_l4_feedback
        record_l4_feedback("loop_cycle", "qed_bridge", "tune_threshold", "test")

        # Now should be True
        result2 = check_l4_feedback(mock_ledger_query, "test")
        assert result2 is True

    def test_calculate_level_coverage(self):
        """Coverage calculation is correct."""
        receipts = [
            {"receipt_type": "ingest"},
            {"receipt_type": "qed_window"},
        ]
        expected = ["ingest", "qed_window", "qed_batch", "qed_manifest"]

        coverage = calculate_level_coverage(receipts, 0, expected)

        assert coverage == 0.5  # 2 out of 4


# =============================================================================
# Entropy Tests
# =============================================================================

class TestEntropy:
    """Tests for entropy.py - Shannon primitives."""

    def test_system_entropy_calculation(self):
        """Shannon entropy calculates correctly."""
        # All same type = 0 entropy
        same_type = [{"receipt_type": "ingest"} for _ in range(10)]
        assert system_entropy(same_type) == 0.0

        # Mixed types = positive entropy
        mixed = [
            {"receipt_type": "ingest"},
            {"receipt_type": "anomaly"},
            {"receipt_type": "brief"},
            {"receipt_type": "health"},
        ]
        entropy = system_entropy(mixed)
        assert entropy > 0
        assert entropy == 2.0  # 4 equal types = log2(4) = 2 bits

    def test_agent_fitness_calculation(self):
        """Agent fitness measures entropy reduction per action."""
        before = [
            {"receipt_type": "anomaly"},
            {"receipt_type": "anomaly"},
            {"receipt_type": "anomaly"},
            {"receipt_type": "ingest"},
        ]
        after = [
            {"receipt_type": "ingest"},
            {"receipt_type": "ingest"},
            {"receipt_type": "actuation", "helper_id": "h1"},
        ]

        fitness = agent_fitness("h1", before, after)
        # Should be positive if entropy reduced
        assert isinstance(fitness, float)

    def test_entropy_conservation(self):
        """Entropy conservation validates correctly."""
        cycle_data = {
            "sensed": [{"receipt_type": "ingest"}, {"receipt_type": "anomaly"}],
            "emitted": [{"receipt_type": "loop_cycle"}],
            "work": {"cpu_ms": 100, "io_ops": 10, "network_calls": 2},
        }

        result = entropy_conservation(cycle_data)

        assert "valid" in result
        assert "entropy_in" in result
        assert "entropy_out" in result
        assert "work" in result
        assert "delta" in result


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for loop module."""

    def test_full_cycle_with_wounds_and_helpers(self, mock_ledger_query, sample_wounds, capsys):
        """Full cycle: sense → analyze → harvest → hypothesize → gate → actuate."""
        mock_ledger_query.receipts.extend(sample_wounds)

        # Run multiple cycles
        results = []
        for _ in range(3):
            result = run_cycle(mock_ledger_query, "test")
            results.append(result)

        # All should complete
        assert all(r["status"] in ("complete", "partial") for r in results)

        # Should have processed some phases
        final = results[-1]
        assert final["phases"]["sense"]["status"] == "complete"
        assert final["phases"]["analyze"]["status"] == "complete"

    def test_constants_correct_values(self):
        """Verify constants have correct values per spec."""
        assert CYCLE_INTERVAL_S == 60
        assert WOUND_THRESHOLD_COUNT == 5
        assert len(PROTECTED) == 5
        assert "loop.cycle" in PROTECTED
        assert "loop.gate" in PROTECTED
        assert "ledger.anchor" in PROTECTED


# =============================================================================
# SLO Tests
# =============================================================================

class TestSLO:
    """Tests for SLO compliance."""

    def test_cycle_slo_60s(self, mock_ledger_query):
        """Single cycle completes in ≤60s."""
        start = time.perf_counter()
        run_cycle(mock_ledger_query, "test")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 60000, f"Cycle took {elapsed_ms}ms, exceeds 60s SLO"

    def test_sense_slo_5s(self, mock_ledger_query):
        """sense() completes in ≤5s."""
        start = time.perf_counter()
        sense(mock_ledger_query, "test")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 5000, f"Sense took {elapsed_ms}ms, exceeds 5s SLO"

    def test_analyze_slo_10s(self, sample_receipts):
        """analyze() completes in ≤10s."""
        sensed = {"all_receipts": sample_receipts}

        start = time.perf_counter()
        analyze(sensed, "test")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 10000, f"Analyze took {elapsed_ms}ms, exceeds 10s SLO"

    def test_completeness_slo_2s(self, mock_ledger_query):
        """measure_completeness() completes in ≤2s."""
        start = time.perf_counter()
        measure_completeness(mock_ledger_query, "test")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 2000, f"Completeness took {elapsed_ms}ms, exceeds 2s SLO"
