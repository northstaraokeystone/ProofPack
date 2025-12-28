# ProofPack Architecture: Pre-Execution Safety

This document describes the pre-execution safety architecture that validates actions BEFORE execution.

---

## System 1: Pre-Execution Gate

### Purpose

Block catastrophic actions BEFORE they execute, not after.

### Components

| Component | Location | Function |
|-----------|----------|----------|
| confidence.py | gate/ | Calculate interpretation stability score |
| decision.py | gate/ | Three-tier gate decision (GREEN/YELLOW/RED) |
| drift.py | gate/ | Measure context change since reasoning started |

### Decision Thresholds

```python
GATE_GREEN_THRESHOLD = 0.9   # Execute immediately
GATE_YELLOW_THRESHOLD = 0.7  # Execute + spawn watchers
# Below 0.7 = RED           # Block, require approval
```

### Confidence Score Calculation

The confidence score combines:

1. **Context Drift** - How much has changed since reasoning started
2. **Reasoning Entropy** - Shannon entropy of the decision process
3. **Reasoning Stability** - Variance in confidence trajectory
4. **Loop Detection** - Penalty for repeated questions
5. **Monte Carlo Variance** - Stability across simulations

### Integration

Every gate decision:
- Emits a `gate_decision` receipt (GREEN/YELLOW) or `block` receipt (RED)
- Calls `anchor/dual_hash` for blockchain anchoring
- YELLOW decisions spawn watchers via `loop/`
- RED decisions require human approval via `loop/gate.py`

---

## System 2: Meta-Loop Detector

### Purpose

Detect when reasoning is stuck and auto-spawn helpers.

### Components

| Component | Location | Function |
|-----------|----------|----------|
| wounds.py | loop/src/ | Track confidence drops >15% |
| spawn.py | loop/src/ | Auto-spawn helpers when stuck |
| convergence.py | loop/src/ | Detect reasoning loops |

### Wound Detection

A "wound" is a significant confidence drop:

```python
WOUND_DROP_THRESHOLD = 0.15  # 15% drop triggers wound
WOUND_SPAWN_THRESHOLD = 5    # 5 wounds triggers spawn
```

### Spawn Formula

```python
helpers = (wounds // 2) + 1

# Convergence bonus
if convergence_proof >= 0.95:
    helpers = ceil(helpers * 1.5)
```

### Loop Detection

```python
CONVERGENCE_LOOP_THRESHOLD = 5  # Same question 5x = loop
```

When the same question appears 5+ times, loop detection triggers:
- Emit `convergence` receipt
- Calculate convergence proof score
- Apply spawn multiplier if proof >0.95

---

## System 3: Monte Carlo Variance Reduction

### Purpose

Test action variations before committing. Statistical confidence, not single-shot.

### Components

| Component | Location | Function |
|-----------|----------|----------|
| simulate.py | monte_carlo/ | Run N simulated variations |
| variance.py | monte_carlo/ | Calculate variance across outcomes |
| threshold.py | monte_carlo/ | Determine if variance acceptable |

### Parameters

```python
MONTE_CARLO_DEFAULT_SIMS = 100
MONTE_CARLO_DEFAULT_NOISE = 0.05
MONTE_CARLO_VARIANCE_THRESHOLD = 0.2
MONTE_CARLO_LATENCY_BUDGET_MS = 200
```

### Performance Constraint

100 simulations MUST complete in <200ms.

---

## Integration Flow

```
Agent proposes action
        |
        v
monte_carlo/simulate.py runs 100 variations
        |
        v
monte_carlo/variance.py calculates stability
        |
        v
    [HIGH VARIANCE?]
        | yes
        v
loop/convergence.py checks for reasoning loops
        |
        v
    [LOOP DETECTED?]
        | yes
        v
loop/spawn.py spawns helpers -> loop/genesis.py
        |
        v
    [VARIANCE ACCEPTABLE]
        |
        v
gate/confidence.py calculates score
        |
        v
gate/decision.py makes GREEN/YELLOW/RED decision
        |
        +--[GREEN]---> Execute + ledger/ingest receipt
        |
        +--[YELLOW]--> Execute + loop/ spawns watchers
        |
        +--[RED]-----> Block + block_receipt + require approval
        |
        v
anchor/dual_hash on ALL decisions
```

---

## Receipt Types

### gate_decision

Emitted on GREEN or YELLOW decisions.

```json
{
  "receipt_type": "gate_decision",
  "action_id": "string",
  "confidence_score": 0.92,
  "decision": "GREEN|YELLOW",
  "context_drift": 0.05,
  "reasoning_entropy": 0.12
}
```

### block

Emitted on RED decisions.

```json
{
  "receipt_type": "block",
  "action_id": "string",
  "reason": "confidence_score 0.58 < 0.7",
  "requires_approval": true,
  "blocked_at": 1705320600.0
}
```

### monte_carlo

Emitted after simulation batch.

```json
{
  "receipt_type": "monte_carlo",
  "action_id": "string",
  "n_simulations": 100,
  "variance": 0.15,
  "mean_outcome": 0.82,
  "is_stable": true
}
```

### wound

Emitted when confidence drop detected.

```json
{
  "receipt_type": "wound",
  "wound_index": 3,
  "confidence_before": 0.85,
  "confidence_after": 0.68,
  "drop_magnitude": 0.17
}
```

### spawn

Emitted when helpers are spawned.

```json
{
  "receipt_type": "spawn",
  "wound_count": 5,
  "helpers_spawned": 3,
  "convergence_proof": 0.42,
  "merkle_root": "abc123..."
}
```

---

## SLO Thresholds

| SLO | Threshold | Stoprule Action |
|-----|-----------|-----------------|
| Gate Latency | <50ms | alert |
| Monte Carlo Latency | <200ms for 100 sims | alert |
| Wound Detection | real-time | escalate at 10 wounds |
| Convergence | 5 repeats | halt at 10 repeats |

---

## Feature Flags

All features start DISABLED (shadow mode):

```python
FEATURE_GATE_ENABLED = False
FEATURE_GATE_YELLOW_ONLY = False
FEATURE_MONTE_CARLO_ENABLED = False
FEATURE_WOUND_DETECTION_ENABLED = False
FEATURE_AUTO_SPAWN_ENABLED = False
```

### Deployment Sequence

1. All OFF (shadow mode, log only)
2. YELLOW gate only
3. Full RED gate
4. Monte Carlo
5. Auto-spawn

---

## Backward Compatibility

- All existing APIs unchanged
- New systems are additive
- Feature flags ensure safe rollout
- Dual-hash pattern extended, not replaced

---

## Key Insight

Current agent frameworks validate AFTER action completes.

ProofPack validates BEFORE execution.

Every decision emits a receipt. Every receipt is anchored. The proof proves itself.
