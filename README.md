# ProofPack

**Receipts-Native Accountability Infrastructure**

ProofPack is a system that keeps cryptographic receipts for everything. Every operation emits proof. Every decision is verifiable. No receipt → not real.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

## The Three Laws

```python
LAW_1 = "No receipt → not real"
LAW_2 = "No test → not shipped"
LAW_3 = "No gate → not alive"
```

## Installation

```bash
pip install proofpack
```

Or from source:
```bash
git clone https://github.com/northstaraokeystone/ProofPack.git
cd ProofPack
pip install -e ".[dev]"
```

## Quick Start

```python
from proofpack import dual_hash, emit_receipt, StopRule

# Hash data with dual SHA256:BLAKE3
hash_value = dual_hash(b"my data")
print(hash_value)  # sha256_hex:blake3_hex

# Emit a receipt
receipt = emit_receipt("ingest", {
    "tenant_id": "my_tenant",
    "payload": {"key": "value"}
})
print(receipt)
```

## CLI Usage

```bash
# Show available commands
proofpack --help

# Ledger operations
proofpack ledger ingest data.json --tenant my_tenant
proofpack ledger verify receipt_123

# Gate decisions
proofpack gate check --confidence 0.85

# Monte Carlo simulation
proofpack monte run --scenario BASELINE

# Anchor operations
proofpack anchor prove --data "test"

# MCP server
proofpack mcp serve
```

Or run as a module:
```bash
python -m proofpack --help
```

## Architecture

```
src/proofpack/
├── core/           # Receipt primitives (dual_hash, emit_receipt, merkle, StopRule)
├── ledger/         # Receipt storage, verification, compaction
├── anchor/         # Cryptographic proofs with dual-hash Merkle trees
├── detect/         # Anomaly detection, drift, resource monitoring
├── gate/           # Pre-execution gating (GREEN/YELLOW/RED decisions)
├── loop/           # Self-improving meta-layer (quantum cycles, wounds, spawn)
├── spawner/        # Agent lifecycle (birth, graduation, pruning)
├── simulation/     # Monte Carlo scenarios and variance reduction
├── mcp/            # Model Context Protocol server integration
├── enterprise/     # Workflow DAG, sandbox, inference, compliance
├── graph/          # Temporal knowledge graph with episodic memory
├── brief/          # Evidence synthesis and decision health
├── packet/         # Claim-to-receipt mapping and audit
├── fallback/       # LLM fallback chain with receipts
├── bridges/        # External integrations (QED)
├── offline/        # Disconnected operation + local sync
├── config/         # Feature flags and allowlists
├── schemas/        # JSON schemas and receipt definitions
├── cli/            # Command-line interface
├── proof.py        # Unified interface (BRIEF/PACKET/DETECT modes)
├── privacy.py      # Differential privacy primitives
└── economic.py     # Economic simulation and resource tracking
```

## Flow

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

### Loop Meta-Layer

```
Sense → Emit → Harvest → Genesis
  ↑                        ↓
  └──── Cycle (entropy) ───┘

Wounds accumulate → Spawn helpers → Convergence proof
```

## Key Concepts

### Dual Hash
Every receipt uses SHA256:BLAKE3 dual hashing for integrity.

### StopRule
Exception that halts execution. Never catch silently.

### Entropy Conservation
The loop module enforces thermodynamic laws - entropy cannot decrease without work.

## Enterprise Features

- **RACI Accountability**: Every receipt tracks Responsible, Accountable, Consulted, Informed
- **Model Provenance**: Version tracking for all decision models
- **Reason Codes**: Structured human intervention capture
- **Compliance Reports**: DOD 3000.09, EU AI Act, FDA TPLC ready
- **Workflow DAG**: Explicit execution visibility with 7-node graph
- **Sandbox Execution**: Docker isolation with network allowlist

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run compliance tests
pytest tests/test_compliance.py -v
```

## Documentation

- [CLAUDEME](CLAUDEME.md) - Self-describing execution standard
- [LIMITATIONS](LIMITATIONS.md) - Known limitations
- [Architecture](docs/architecture.md) - Detailed architecture
- [RNES Spec](docs/RNES_v1.md) - Receipts-Native specification

## License

Apache 2.0

---

*Built by Northstar AO Keystone Research Lab*

*No receipt → not real. No test → not shipped. No gate → not alive.*
