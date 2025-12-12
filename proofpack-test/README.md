# ProofPack Test Harness

Monte Carlo test harness for validating LOOP dynamics before production deployment.

## Directory Structure

```
proofpack-test/
├── conftest.py              # SimConfig, SimState dataclasses, fixtures
├── sim.py                   # Monte Carlo simulation engine
├── scenarios/
│   ├── __init__.py
│   ├── test_baseline.py     # 1000 cycles, zero violations
│   ├── test_stress.py       # gap_rate=0.5, resources=0.3, recovery
│   ├── test_learning.py     # Recurring gaps → helper proposal
│   ├── test_completeness.py # 10000 cycles, L0-L4 ≥99.9%
│   ├── test_approval.py     # Gate at all risk levels
│   └── test_recovery.py     # Checkpoint/resume continuity
├── test_modules/
│   ├── __init__.py
│   ├── test_ledger.py       # ingest, anchor, verify, compact
│   ├── test_brief.py        # retrieve, compose, health, dialectic
│   ├── test_packet.py       # attach, audit, build
│   ├── test_detect.py       # scan, classify, alert
│   ├── test_anchor.py       # dual_hash, merkle, prove, verify
│   └── test_loop.py         # run_cycle, harvest, genesis, gate
├── test_integration.py      # Cross-module pipeline validation
└── README.md
```

## Configuration

### SimConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `n_cycles` | int | 1000 | Number of simulation cycles |
| `gap_rate` | float | 0.1 | Probability of gap per cycle |
| `resource_budget` | float | 1.0 | Resource constraint (0.0-1.0) |
| `random_seed` | int | 42 | Deterministic seed |
| `timeout_seconds` | int | 300 | Maximum runtime |

### SimState

| Field | Type | Description |
|-------|------|-------------|
| `cycle` | int | Current cycle number |
| `active_helpers` | list | Active helper configurations |
| `gap_history` | list | Gap receipt history |
| `receipt_ledger` | list | All emitted receipts |
| `completeness_trace` | list | L0-L4 snapshots per cycle |
| `violations` | list | Violation strings |

## 6 Mandatory Scenarios

| Scenario | File | Config Overrides | Pass Criteria |
|----------|------|------------------|---------------|
| BASELINE | test_baseline.py | n_cycles=1000 | Zero violations, receipts populated |
| STRESS | test_stress.py | gap_rate=0.5, resource_budget=0.3 | Stabilize ≥1 helper, recover in final 100 cycles |
| LEARNING | test_learning.py | Pre-inject 7 recurring gaps | ≥1 helper_blueprint proposed within 500 cycles |
| COMPLETENESS | test_completeness.py | n_cycles=10000, timeout=600 | L0-L4 all ≥99.9%, self_verifying=True |
| APPROVAL | test_approval.py | Test each risk tier | Gates function correctly at all 4 risk levels |
| RECOVERY | test_recovery.py | Run 500, checkpoint, resume 500 | Total 1000 cycles, ledger continuity preserved |

## Module SLOs

| Module | Functions | SLO |
|--------|-----------|-----|
| ledger | ingest, anchor, verify, compact | ingest ≤50ms p95 |
| brief | retrieve, compose, health, dialectic | brief ≤1000ms p95 |
| packet | attach, audit, build | consistency ≥99.9% |
| detect | scan, classify, alert | scan ≤100ms p95 |
| anchor | dual_hash, merkle, prove, verify | dual_hash returns {sha256}:{blake3} |
| loop | run_cycle, harvest, genesis, gate, completeness | cycle completes all 7 phases |

## Running Tests

### Phase 1 — Quick Verification

```bash
# Import check
python -c "from conftest import SimConfig, SimState; print('OK')"

# 100-cycle smoke test
pytest scenarios/test_baseline.py::TestBaseline::test_baseline_zero_violations -v --tb=short

# Fast scenarios
pytest scenarios/test_baseline.py scenarios/test_approval.py -v
```

### Phase 2 — Full Verification

```bash
# All 6 scenarios
pytest scenarios/ -v

# Module unit tests with coverage
pytest test_modules/ -v --cov=../ledger --cov=../brief --cov=../packet --cov=../detect --cov=../anchor --cov=../loop

# Integration tests
pytest test_integration.py -v

# Full suite
pytest . -v --timeout=600
```

## Approval Gate Thresholds

| Risk Score | Action |
|------------|--------|
| < 0.2 | Auto-approve |
| 0.2 ≤ risk < 0.5 | Single approval |
| 0.5 ≤ risk < 0.8 | Two approvals |
| ≥ 0.8 | Two approvals + observation period |

## Genesis Trigger

Helper blueprint is proposed when:
- ≥5 occurrences of same `problem_type`
- AND median `resolve_time` > 30 minutes

## Verification Protocol

1. **Phase 1 (Quick)**: Import check, 100-cycle smoke, fast scenarios
2. **⏸️ CHECKPOINT**: Review results, wait for approval
3. **Phase 2 (Full)**: All 6 scenarios, coverage ≥80%, COMPLETENESS scenario

## Constraints

- **Framework**: pytest only
- **Deterministic**: random_seed=42 by default
- **Every test has assert** (T+24h gate fails otherwise)
- **Timeout guards**: 300s default, 600s for COMPLETENESS
- **Exit codes**: pytest default (0 pass, 1 fail)

## Commit Message Format

```
feat(proofpack-test): Monte Carlo test harness with 6 mandatory scenarios

conftest.py: SimConfig/SimState dataclasses, fixtures
sim.py: run_simulation, simulate_cycle, check_completeness
scenarios/: BASELINE, STRESS, LEARNING, COMPLETENESS, APPROVAL, RECOVERY
test_modules/: unit tests for all 6 core modules
test_integration.py: cross-module pipeline validation
Coverage: ≥80% per module
Gate: t48h
```
