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

## Modules

| Module | Purpose |
|--------|---------|
| `core/` | Receipt primitives (dual_hash, emit_receipt, merkle, StopRule) |
| `gate/` | Pre-execution gating (GREEN/YELLOW/RED) |
| `monte_carlo/` | Variance reduction via simulation |
| `ledger/` | Receipt storage + Merkle anchoring |
| `proof.py` | Unified interface (BRIEF/PACKET/DETECT) |
| `enterprise/` | Workflow DAG, sandbox, inference, plan approval |
| `offline/` | Disconnected operation + sync |

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

---

## Usage

```python
from core.receipt import dual_hash, emit_receipt, StopRule
from gate import gate_decision
from proof import proof, ProofMode

# Gate a decision
result, receipt = gate_decision(confidence_score=0.85)

# Unified proof
brief = proof(ProofMode.BRIEF, {"operation": "compose", "evidence": chunks})
```

---

## Laws

1. **No receipt → not real**
2. **No test → not shipped**
3. **No gate → not alive**

---

## Structure

```
ProofPack/
├── core/           # Receipt primitives
├── gate/           # Pre-execution gating
├── monte_carlo/    # Variance reduction
├── ledger/         # Storage + anchoring
├── proof.py        # Unified interface
├── enterprise/     # Workflow, sandbox, inference, plan approval
├── offline/        # Disconnected operation
├── proofpack_cli/  # CLI
└── tests/          # Compliance tests
```

---

## Verify

```bash
pip install pytest blake3
pytest tests/test_compliance.py -v
```

[Receipt bundles](receipts/) | [RNES spec](standards/RNES_v1.md) | [CLAUDEME](CLAUDEME.md)

---

Apache 2.0
