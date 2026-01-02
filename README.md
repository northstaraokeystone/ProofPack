# ProofPack

**Receipts all the way down.**

Pre-execution safety + cryptographic proof for AI agents.

```bash
pip install -e .
proof anchor hash "test data"   # Emit SHA256:BLAKE3 receipt
```

---

## Quick Start

```bash
git clone https://github.com/northstaraokeystone/ProofPack && cd ProofPack
pip install -e .
python receipts/generate_fraud_receipts.py
./receipts/reproduce_fraud.sh
```

---

## Core Modules

| Module | Purpose |
|--------|---------|
| `core/` | Receipt primitives (dual_hash, emit_receipt, merkle, StopRule) |
| `gate/` | Pre-execution gating (GREEN/YELLOW/RED decisions) |
| `loop/` | Self-improving meta-layer (quantum cycles, wounds, spawn) |
| `ledger/` | Receipt storage, compaction, verification |
| `anchor/` | Merkle proof generation and verification |
| `monte_carlo/` | Variance reduction via simulation |
| `brief/` | Evidence synthesis and retrieval |
| `detect/` | Anomaly and drift detection |

## Extended Modules

| Module | Purpose |
|--------|---------|
| `proof.py` | Unified interface (BRIEF/PACKET/DETECT modes) |
| `graph/` | Episodic memory graph with sync |
| `mcp/` | Model Context Protocol server integration |
| `offline/` | Disconnected operation + local sync |
| `enterprise/` | Workflow DAG, sandbox, inference, plan approval |
| `fallback/` | LLM fallback chain with receipts |
| `qed_bridge/` | QED formal verification bridge |
| `privacy.py` | Differential privacy primitives |
| `economic.py` | Economic simulation and resource tracking |

---

## Architecture

```
Action → Monte Carlo → Gate Decision
                          ↓
              ┌───────────┼───────────┐
            GREEN      YELLOW       RED
              ↓          ↓            ↓
           Execute   Execute+      Block +
                     Watch         Approval
              └──────────┴────────────┘
                         ↓
               Receipt emitted + anchored
```

### Loop Meta-Layer (Quantum Edition)

```
Sense → Emit → Harvest → Genesis
  ↑                        ↓
  └──── Cycle (entropy) ───┘

Wounds accumulate → Spawn helpers → Convergence proof
```

The `loop/` module provides self-improvement capabilities:
- **cycle.py**: Thermodynamic cycle management
- **quantum.py**: Shannon entropy calculations
- **wounds.py**: Confidence drop tracking (>15% = wound)
- **spawn.py**: Auto-spawn helpers when stuck
- **convergence.py**: Detect reasoning loops
- **genesis.py**: Helper creation

---

## Usage

```python
from core.receipt import dual_hash, emit_receipt, StopRule
from gate import gate_decision
from proof import proof, ProofMode
from loop import META_LOOP

# Gate a decision
result, receipt = gate_decision(confidence_score=0.85)

# Unified proof
brief = proof(ProofMode.BRIEF, {"operation": "compose", "evidence": chunks})

# Run meta-loop cycle
cycle_result = META_LOOP.run_cycle(context)
```

---

## Structure

```
ProofPack/
├── core/           # Receipt primitives (dual_hash, emit_receipt, merkle)
├── gate/           # Pre-execution gating (confidence, decision, drift)
├── loop/           # Self-improving meta-layer
│   └── src/        # Quantum cycles, wounds, spawn, convergence
├── ledger/         # Receipt storage + compaction
├── anchor/         # Merkle proof generation
├── monte_carlo/    # Variance reduction (simulate, threshold)
├── brief/          # Evidence synthesis (compose, dialectic, retrieve)
├── detect/         # Anomaly detection
├── graph/          # Episodic memory (ingest, query, sync)
├── mcp/            # MCP server integration
├── offline/        # Disconnected operation + sync
├── enterprise/     # Workflow DAG, sandbox, inference
├── fallback/       # LLM fallback chains
├── qed_bridge/     # QED formal verification
├── proof.py        # Unified interface
├── privacy.py      # Differential privacy
├── economic.py     # Economic simulation
├── proofpack_cli/  # CLI tools
└── tests/          # Compliance tests
```

---

## Laws

1. **No receipt → not real**
2. **No test → not shipped**
3. **No gate → not alive**

---

## Key Concepts

### Dual Hash
Every receipt uses SHA256:BLAKE3 dual hashing for integrity.

### StopRule
Exception that halts execution. Never catch silently.

### Entropy Conservation
The loop module enforces thermodynamic laws - entropy cannot decrease without work.

---

## Verify

```bash
pip install pytest blake3
pytest tests/test_compliance.py -v
```

---

## Documentation

- [Receipt bundles](receipts/)
- [RNES spec](standards/RNES_v1.md)
- [CLAUDEME](CLAUDEME.md)
- [Architecture details](docs/architecture.md)
- [Roadmap](ROADMAP.md)
- [Limitations](LIMITATIONS.md)

---

Apache 2.0
