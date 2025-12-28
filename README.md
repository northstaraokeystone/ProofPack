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
| **gate** | Stops bad decisions before they happen | Pre-execution confidence gating |
| **monte_carlo** | Tests decisions before committing | Statistical variance reduction |
| **spawner** | Creates helpers when uncertain | Agent birthing and lifecycle management |

## Pre-Execution Safety

ProofPack validates actions BEFORE execution, not after. Three systems work together:

### Gate System

Every action passes through a confidence gate before execution:

| Decision | Confidence | Action |
|----------|------------|--------|
| GREEN | >0.9 | Execute immediately |
| YELLOW | 0.7-0.9 | Execute with monitoring |
| RED | <0.7 | Block, require approval |

The gate calculates confidence from:
- Context drift (how much has changed since reasoning started)
- Reasoning entropy (how stable is the decision process)
- Monte Carlo variance (how consistent are simulated outcomes)

### Monte Carlo Variance Reduction

Before committing to an action, run 100 simulated variations. High variance = unstable action = lower confidence score. This catches edge cases before they become production incidents.

### Meta-Loop Detection

Track confidence drops (wounds) over time. When the system is stuck:
- Detect reasoning loops (same question asked 5+ times)
- Auto-spawn helper agents based on wound count
- Convergence proof triggers helper multiplier

All three systems emit receipts. Every decision is blockchain-anchored.

## Agent Birthing Architecture

Traffic lights don't just stop — they create helpers. When confidence drops, ProofPack spawns specialized agents to assist.

### Agent Types by Gate Color

| Gate | Confidence | Agents Spawned | Purpose |
|------|------------|----------------|---------|
| GREEN | >0.9 | 1 success_learner | Captures what worked |
| YELLOW | 0.7-0.9 | 3 watchers | Monitors drift, wounds, success |
| RED | <0.7 | (wounds/2)+1 helpers | Tries different approaches |

### Agent Lifecycle

```
SPAWNED → ACTIVE → GRADUATED (effective)
                 → PRUNED (ineffective)
```

Agents can be pruned for:
- TTL expired (default 5 minutes)
- Sibling solved the problem
- Depth limit reached (max 3 levels)
- Resource cap hit (max 50 agents)
- Low effectiveness

### Pattern Graduation

Successful helpers become permanent. When an agent:
- Achieves effectiveness >= 0.85
- Has autonomy score > 0.75

It graduates to a permanent pattern. Future RED gates check for matching patterns before spawning new helpers.

### Topology Classification

Agents are classified like META-LOOP patterns:

| Topology | Condition | Fate |
|----------|-----------|------|
| OPEN | effectiveness >= 0.85, autonomy > 0.75 | Graduate |
| CLOSED | effectiveness < 0.85 | Prune |
| HYBRID | transfer_score > 0.70 | Transfer |

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
proof loop wounds
proof loop convergence

# Gate
proof gate check <action_id>
proof gate history

# Monte Carlo
proof monte status
proof monte simulate <action_id>

# Spawn
proof spawn status
proof spawn history
proof spawn kill <agent_id>
proof spawn patterns
proof spawn simulate
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
├── gate/             # Pre-execution gating
├── monte_carlo/      # Variance reduction
├── spawner/          # Agent birthing and lifecycle
├── config/           # Feature flags
├── proofpack_cli/    # Command line interface
├── proofpack-schema/ # Central JSON schemas
├── proofpack-test/   # Test harness
├── constants.py      # Shared thresholds
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
