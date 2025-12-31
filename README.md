# ProofPack

**Research-Grade Proof-of-Concept for Receipts-Native Governance**

ProofPack demonstrates compression-based fraud detection with cryptographic receipts. It validates the receipts-native architecture thesis for systems that can't call home.

**Status:** Research-Grade | **Compliance:** 6/6 Principles | **Claims:** Verified via Receipts

---

## What ProofPack Proves

| Claim | Verification |
|-------|--------------|
| Compression-based fraud detection works | 100% recall, 0% false positives on 147 test cases ([receipt bundle](releases/)) |
| Receipts-native architecture is viable | 6/6 RNES principles pass ([compliance report](compliance/COMPLIANCE_REPORT.md)) |
| Governance without trust | All claims verified via dual-hash receipt chains ([verification guide](docs/CLAIMS_VERIFICATION.md)) |

---

## Quick Start

```bash
# Clone repo
git clone https://github.com/northstaraokeystone/ProofPack
cd ProofPack

# Install
pip install -e .

# Run fraud detection demo
python receipts/generate_fraud_receipts.py

# Verify receipts
./receipts/reproduce_fraud.sh
```

---

## Verification

**Compliance Tests:**
```bash
pip install pytest blake3
pytest tests/test_compliance.py -v
# Expected: 19 passed (6/6 principles)
```

**Receipt Bundle:**
```bash
./receipts/reproduce_fraud.sh
# Expected: Merkle root verified
```

See [CLAIMS_VERIFICATION.md](docs/CLAIMS_VERIFICATION.md) for complete verification guide.

---

## Current State

**What Works:**
- Compression-based fraud detection (100% recall verified)
- Cryptographic receipt emission (dual-hash SHA256:BLAKE3)
- Receipt chain verification
- Merkle anchoring
- Shannon entropy tracking
- SLO enforcement with StopRule

**Known Gaps:** (see [LIMITATIONS.md](LIMITATIONS.md))
- No automated CI/CD pipeline
- Limited test coverage (compliance + unit tests only)
- No monitoring/observability hooks
- Enterprise hardening planned for Q2 2025

**Roadmap:** [ROADMAP.md](ROADMAP.md)

---

## Why Research-Grade?

ProofPack validates the receipts-native thesis—which is exactly what's needed at the category-creation stage. Enterprise hardening (CI/CD, monitoring, security audit, 80%+ test coverage) is planned post-seed funding.

**Historical precedent:** Stripe's first API, Databricks' first Spark demo, HashiCorp's first Terraform weren't enterprise-ready either. They proved their thesis, then scaled.

---

## For Systems That Can't Call Home

- **Off-planet:** Satellites, lunar missions, deep space probes
- **Defense:** RF-denied environments, adversarial conditions
- **Autonomous:** Vehicles in tunnels, drones beyond range
- **Regulated:** FDA devices, financial infrastructure

When your satellite makes an autonomous decision 400km above Earth, it can't ask permission. It generates a receipt locally, builds a Merkle proof in isolation, and syncs when it sees ground station. That's ProofPack.

---

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
| Fraud recall | 100% |

---

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
| **proof** | Unified proof interface | Single entry point for BRIEF/PACKET/DETECT modes |
| **graph** | Temporal knowledge graph | Queryable receipt storage with <300ms SLOs |
| **privacy** | Privacy controls | Redaction and privacy levels |
| **offline** | Disconnected operation | Local queue and sync |
| **economic** | Payment integration | SLO evaluation and payment triggers |

---

## RNES Standard

Receipts-Native Execution Standard - proposed industry standard for auditable receipts:

```python
# RNES-compliant receipt
{
    "receipt_type": "decision",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "satellite-001",
    "payload_hash": "sha256hex:blake3hex",
    "privacy_level": "redacted",
    "slo_status": "met"
}
```

See [standards/RNES_v1.md](standards/RNES_v1.md) for the full specification.

---

## Core Laws

From [CLAUDEME.md](CLAUDEME.md):

- **LAW_1:** "No receipt → not real"
- **LAW_2:** "No test → not shipped"
- **LAW_3:** "No gate → not alive"

---

## Repository Structure

```
ProofPack/
├── proofpack/           # Main package
│   ├── core/            # Receipt primitives (dual_hash, emit_receipt, merkle)
│   ├── ledger/          # Receipts storage
│   ├── anchor/          # Cryptographic proofs
│   ├── detect/          # Pattern finding
│   ├── loop/            # Self-improvement layer (with entropy tracking)
│   ├── proof.py         # Unified proof interface
│   ├── graph/           # Temporal knowledge graph
│   ├── privacy.py       # Privacy controls
│   └── economic.py      # Economic integration
├── tests/               # Compliance tests
├── compliance/          # Compliance reports
├── receipts/            # Receipt bundles
├── releases/            # Downloadable bundles
├── docs/                # Documentation
├── standards/           # RNES specification
├── LIMITATIONS.md       # Known gaps
├── ROADMAP.md           # Path to enterprise-ready
└── README.md            # This file
```

---

## Claims Verification

Every claim in this README is cryptographically verifiable:

| Claim | Verification Method |
|-------|---------------------|
| 100% recall | [Receipt bundle](releases/) + [reproduce_fraud.sh](receipts/reproduce_fraud.sh) |
| RNES-compliant | [Compliance tests](tests/test_compliance.py) + [report](compliance/COMPLIANCE_REPORT.md) |
| Dual-hash chains | Inspect [receipts.jsonl](receipts/fraud_detection_v1.receipts.jsonl) |
| Merkle anchoring | [MANIFEST.anchor](receipts/MANIFEST.anchor) |

**No trust required. Verify everything.**

---

## Contributing

ProofPack is part of the receipts-native working group (launching Feb 2025).

See [standards/CONTRIBUTE.md](standards/CONTRIBUTE.md) for guidelines.

---

## License

Apache 2.0

---

*They build for connectivity. We build for isolation. That's the wedge.*
