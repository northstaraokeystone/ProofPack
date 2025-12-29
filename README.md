# ProofPack

**RNES-compliant governance infrastructure for systems that can't call home.**

## What Makes Us Different

| Competitor | Their Focus | Our Focus |
|------------|-------------|-----------|
| Hackett | Fast substrate | Governance substrate |
| Brevis | Payment proofs | Decision proofs |
| Miden | Gaming/consumer | Extreme environments |
| idOS | Dispute resolution | Compliance resolution |
| MorphLayer | Consumer finance | Industrial autonomy |

## For Systems That Can't Call Home

- **Off-planet:** Satellites, lunar missions, deep space probes
- **Defense:** RF-denied environments, adversarial conditions
- **Autonomous:** Vehicles in tunnels, drones beyond range
- **Regulated:** FDA devices, financial infrastructure

## Core Capabilities

| Capability | Description |
|------------|-------------|
| **Offline mode** | Generate receipts locally, sync when connected |
| **Privacy levels** | Public, redacted, or ZK-ready |
| **Economic triggers** | SLO status enables payment release |
| **RNES-compliant** | Industry-standard receipt format |

## Performance

| Metric | Value |
|--------|-------|
| Receipt generation | <50ms |
| Merkle anchor (1000) | <1s |
| Graph query | <300ms |
| Recall floor | 99.9% |

[Full benchmarks](benchmarks/PERFORMANCE.md)

## Quick Start

```bash
pip install -e .
proof --help
```

## What Is ProofPack

**ProofPack is a system that keeps receipts for everything.**

Every decision gets documented. Every receipt is verifiable. Nothing happens without proof.

When your satellite makes an autonomous decision 400km above Earth, it can't ask permission. It generates a receipt locally, builds a Merkle proof in isolation, and syncs when it sees ground station. That's ProofPack. Governance for systems that can't call home.

## Offline Mode (Extreme Environments)

ProofPack supports disconnected operation for:
- Off-planet systems (satellites, lunar missions)
- Autonomous vehicles (tunnels, remote areas)
- Defense systems (RF-denied environments)
- Edge devices (IoT, constrained power)

Receipts generate locally. Merkle roots compute locally.
Sync happens when connectivity allows.
Governance doesn't stop when WiFi does.

## v3.2 Features

### RNES Standard

Receipts-Native Execution Standard - proposed industry standard for auditable receipts:

```python
# RNES-compliant receipt
{
    "receipt_type": "decision",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "satellite-001",
    "payload_hash": "sha256:blake3...",
    "privacy_level": "redacted",
    "slo_status": "met"
}
```

See [standards/RNES_v1.md](standards/RNES_v1.md) for the full specification.

### Offline Mode

Generate receipts without connectivity:

```python
from proofpack.offline import queue, sync

# Queue receipt while offline
receipt = queue.enqueue_receipt({
    "receipt_type": "decision",
    "action": "course_correction",
    "confidence": 0.95
})

# Sync when connected
if sync.is_connected():
    sync.full_sync()
```

### Privacy Levels

Control field visibility for auditors:

```python
from proofpack.privacy import redact_receipt

# Redact sensitive fields
redacted = redact_receipt(receipt, ["pii_field", "proprietary_data"])
```

### Economic Integration

Tie receipts to payment triggers:

```python
from proofpack.economic import evaluate_slo, calculate_payment

# Check SLO status
status = evaluate_slo(receipt, {"recall_floor": 0.999})

# Calculate payment
payment = calculate_payment(receipt)
```

## Modules

| Module | Simple Explanation | Technical Capability |
|--------|-------------------|-------------------|
| **ledger** | Keeps all the receipts | Receipts storage, Merkle anchoring |
| **brief** | Summarizes evidence for decisions | Evidence synthesis, decision health scoring |
| **packet** | Packages decisions with their proof | Claim-to-receipt mapping |
| **detect** | Finds problems early | Anomaly and drift detection |
| **anchor** | Makes receipts tamper-proof | Cryptographic hashing (SHA256 + BLAKE3) |
| **loop** | Helps the system improve itself | Self-improvement with human approval |
| **gate** | Stops bad decisions before they happen | Pre-execution confidence gating |
| **monte_carlo** | Tests decisions before committing | Statistical variance reduction |
| **spawner** | Creates helpers when uncertain | Agent birthing and lifecycle management |
| **proof** | Unified proof interface | Single entry point for BRIEF/PACKET/DETECT modes |
| **mcp** | MCP server interface | Exposes tools to Claude Desktop, Cursor, Windsurf |
| **graph** | Temporal knowledge graph | Queryable receipt storage with <300ms SLOs |
| **fallback** | Web fallback (CRAG) | Confidence-gated web augmentation |
| **privacy** | Privacy controls (v3.2) | Redaction and privacy levels |
| **offline** | Disconnected operation (v3.2) | Local queue and sync |
| **economic** | Payment integration (v3.2) | SLO evaluation and payment triggers |

## Pre-Execution Safety

ProofPack validates actions BEFORE execution, not after. Three systems work together:

### Gate System

Every action passes through a confidence gate before execution:

| Decision | Confidence | Action |
|----------|------------|--------|
| GREEN | >0.9 | Execute immediately |
| YELLOW | 0.7-0.9 | Execute with monitoring |
| RED | <0.7 | Block, require approval |

### Monte Carlo Variance Reduction

Before committing to an action, run 100 simulated variations. High variance = unstable action = lower confidence score.

### Meta-Loop Detection

Track confidence drops (wounds) over time. When stuck, auto-spawn helper agents.

All three systems emit receipts. Every decision is blockchain-anchored.

## CLI Examples

```bash
# Core operations
proof ledger ingest <file>
proof ledger verify <proof>
proof anchor

# RNES compliance (v3.2)
proof rnes validate <receipt_id>
proof rnes level <receipt_id>

# Privacy (v3.2)
proof privacy redact <receipt_id> --fields "field1,field2"
proof privacy audit <receipt_id>

# Offline (v3.2)
proof offline status
proof offline queue
proof offline sync
proof offline merkle

# Economic (v3.2)
proof economic evaluate <receipt_id>
proof economic export --pending

# Loop
proof loop status
proof loop gaps
proof loop approve <helper_id>

# Gate
proof gate check <action_id>
proof gate history

# Monte Carlo
proof monte status
proof monte simulate <action_id>

# Spawn
proof spawn status
proof spawn patterns

# MCP Server
proof mcp start [--port PORT]
proof mcp status

# Knowledge Graph
proof graph query lineage <node_id>
proof graph query temporal --start ISO --end ISO

# Web Fallback
proof fallback test <query>
proof fallback stats
```

## Repository Structure

```
ProofPack/
├── proofpack/           # Main package
│   ├── core/            # Receipt primitives (dual_hash, emit_receipt, merkle)
│   ├── ledger/          # Receipts storage
│   ├── brief/           # Evidence synthesis
│   ├── packet/          # Decision packaging
│   ├── detect/          # Pattern finding
│   ├── anchor/          # Cryptographic proofs
│   ├── loop/            # Self-improvement layer
│   ├── gate/            # Pre-execution gating
│   ├── monte_carlo/     # Variance reduction
│   ├── spawner/         # Agent birthing and lifecycle
│   ├── proof.py         # Unified proof interface (v3.1)
│   ├── mcp/             # MCP server (v3.1)
│   ├── graph/           # Temporal knowledge graph (v3.1)
│   ├── fallback/        # Web fallback CRAG (v3.1)
│   ├── offline/         # Offline mode (v3.2)
│   ├── privacy.py       # Privacy controls (v3.2)
│   └── economic.py      # Economic integration (v3.2)
├── config/              # Feature flags
├── proofpack_cli/       # Command line interface
├── proofpack-schema/    # Central JSON schemas
├── proofpack-test/      # Test harness
├── standards/           # RNES specification (v3.2)
├── benchmarks/          # Performance benchmarks (v3.2)
├── docs/                # Documentation
├── CLAUDEME.md          # Execution standard
├── setup.py             # Package installation
└── README.md            # This file
```

## Core Laws

From [CLAUDEME.md](CLAUDEME.md):

- **LAW_1:** "No receipt → not real"
- **LAW_2:** "No test → not shipped"
- **LAW_3:** "No gate → not alive"

## Value Delivered

- **Trust:** Every decision has a receipt. Every receipt is verifiable.
- **Speed:** 50% faster issue resolution through pattern learning.
- **Compliance:** Audit-ready by construction. The receipts ARE the audit trail.

## Contributing

ProofPack follows the RNES standard. See [standards/CONTRIBUTE.md](standards/CONTRIBUTE.md) for guidelines.

**Remember:** No receipt → not real

## License

Apache 2.0

---

*They build for connectivity. We build for isolation. That's the wedge.*
