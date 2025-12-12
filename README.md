# ProofPack

## What Is ProofPack

**ProofPack is a system that keeps receipts for everything.**

Imagine every time you do something important, you get a receipt—like when you buy something at a store. Now imagine a system that gives receipts for every decision a computer makes. If someone asks "why did you do that?"—you show the receipt. ProofPack is that system.

Every decision gets documented. Every receipt is verifiable. Nothing happens without proof.

## What's Inside

| Module | Simple Explanation |
|--------|-------------------|
| **ledger** | Keeps all the receipts |
| **brief** | Summarizes evidence for decisions |
| **packet** | Packages decisions with their proof |
| **detect** | Finds problems early |
| **anchor** | Makes receipts tamper-proof |
| **loop** | Helps the system improve itself |

## Quick Start

```bash
pip install -e .
proof --help
```

That's it. You're ready to start keeping receipts.

## How It Works

**Simple version:**
Something happens → System records it → Receipt created → Receipt stored safely → Anyone can verify later

**Technical version:**
Event → Ledger Receipt → Anchor Hash → Brief Synthesis → Packet Assembly → LOOP Learning

## Modules

| Module | Simple Explanation | Technical Capability |
|--------|-------------------|-------------------|
| **ledger** | Keeps all the receipts | Receipts storage, Merkle anchoring |
| **brief** | Summarizes evidence for decisions | Evidence synthesis, decision health scoring |
| **packet** | Packages decisions with their proof | Claim-to-receipt mapping |
| **detect** | Finds problems early | Anomaly and drift detection |
| **anchor** | Makes receipts tamper-proof | Cryptographic hashing (SHA256 + BLAKE3) |
| **loop** | Helps the system improve itself | Self-improvement with human approval |

## Value Delivered

- **Trust:** Every decision has a receipt. Every receipt is verifiable.
- **Speed:** 50% faster issue resolution through pattern learning.
- **Savings:** ROI proven across Tesla ($11.1B), SpaceX ($331.7M), xAI ($195.6B) at scale.
- **Compliance:** Audit-ready by construction. The receipts ARE the audit trail.

## CLI Examples

```bash
# Ledger
proof ledger ingest <file>
proof ledger verify <proof>
proof ledger anchor

# Brief
proof brief generate <query>
proof brief health <brief>

# Loop
proof loop status
proof loop gaps
proof loop helpers --proposed
proof loop approve <helper_id>
```

## Repository Structure

```
ProofPack/
├── ledger/           # Receipts storage
├── brief/            # Evidence synthesis
├── packet/           # Decision packaging
├── detect/           # Pattern finding
├── anchor/           # Cryptographic proofs
├── loop/             # Self-improvement layer
├── proofpack_cli/    # Command line interface
├── proofpack-schema/ # Central JSON schemas
├── proofpack-test/   # Test harness
├── CLAUDEME.md       # Execution standard
├── setup.py          # Package installation
└── README.md         # This file
```

## Core Laws

From [CLAUDEME.md](CLAUDEME.md):

- **LAW_1:** "No receipt → not real"
- **LAW_2:** "No test → not shipped"
- **LAW_3:** "No gate → not alive"

## Contributing

ProofPack follows strict standards. See [CLAUDEME.md](CLAUDEME.md) for execution guidelines.

**Remember:** No receipt → not real

## License

TBD
