# Agent Lifecycle Documentation

## Overview

ProofPack's agent birthing architecture creates specialized helper agents when the system encounters uncertainty. These agents work in parallel to solve problems, with winners graduating to permanent patterns and losers being pruned.

## Spawning Flow

```
Gate Decision
     │
     ├── GREEN (>0.9) ──────────► Spawn 1 success_learner
     │                            TTL: 60 seconds
     │
     ├── YELLOW (0.7-0.9) ──────► Spawn 3 watchers
     │                            - drift_watcher
     │                            - wound_watcher
     │                            - success_watcher
     │                            TTL: action_duration + 30s
     │
     └── RED (<0.7) ────────────► Spawn (wounds/2)+1 helpers
                                  Min: 1, Max: 6
                                  TTL: 300 seconds
```

## Agent States

```
    ┌───────────┐
    │  SPAWNED  │
    └─────┬─────┘
          │ activate
          ▼
    ┌───────────┐
    │  ACTIVE   │
    └─────┬─────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌───────────┐ ┌───────────┐
│ GRADUATED │ │  PRUNED   │
└───────────┘ └───────────┘
```

### State Descriptions

| State | Description |
|-------|-------------|
| SPAWNED | Agent created, awaiting activation |
| ACTIVE | Agent working on problem |
| GRADUATED | Agent promoted to permanent pattern |
| PRUNED | Agent terminated |

## Spawning Rules

### GREEN Gate

When confidence > 0.9, spawn 1 **success_learner**:
- Records what inputs led to high confidence
- Captures successful patterns for reuse
- TTL: 60 seconds (quick capture)

### YELLOW Gate

When confidence 0.7-0.9, spawn 3 **watchers**:
- **drift_watcher**: Monitors context drift during execution
- **wound_watcher**: Monitors confidence changes
- **success_watcher**: Monitors outcome vs prediction
- TTL: action duration + 30 seconds

### RED Gate

When confidence < 0.7, spawn helpers using formula:
```
helpers = (wound_count // 2) + 1
```

Constraints:
- Minimum: 1 helper
- Maximum: 6 helpers
- High variance (>0.3) adds +1 helper
- TTL: 300 seconds (5 minutes)

## Depth Limits

Agents can spawn child agents, but depth is limited:

```
Root (depth 0)
  └── Child (depth 1)
        └── Grandchild (depth 2)
              └── BLOCKED (depth 3 not allowed)
```

Maximum depth: 3 levels

## Population Limits

- Maximum active agents: 50
- When at capacity, spawn requests are rejected
- Oldest agents may be force-pruned to make room

## Pruning Reasons

| Reason | Description |
|--------|-------------|
| TTL_EXPIRED | Agent exceeded time-to-live |
| SIBLING_SOLVED | Another agent in group solved problem |
| DEPTH_LIMIT | Attempted to spawn beyond max depth |
| RESOURCE_CAP | Population limit reached |
| LOW_EFFECTIVENESS | Agent performing poorly |
| MANUAL | Manually terminated by user |

## Sibling Coordination

When multiple helpers work on same problem:

1. First helper to reach confidence > 0.8 "wins"
2. Winning solution triggers graduation evaluation
3. All sibling helpers receive termination signal
4. Siblings are pruned with reason: SIBLING_SOLVED

## Topology Classification

Agents are classified using META-LOOP topology rules:

| Topology | Condition | Action |
|----------|-----------|--------|
| OPEN | effectiveness >= 0.85 AND autonomy > 0.75 | Graduate |
| CLOSED | effectiveness < 0.85 | Prune, extract learnings |
| HYBRID | transfer_score > 0.70 | Transfer to subsystem |

## Graduation Path

When agent classified as OPEN:

1. Extract solution pattern from agent's approach
2. Store pattern in permanent helper registry
3. Future RED gates check registry before spawning
4. If matching pattern exists, apply pattern instead

## Pattern Storage

Graduated patterns stored in `patterns.jsonl`:
- Pattern ID
- Agent type and gate color
- Decomposition angle
- Solution approach
- Match criteria
- Effectiveness score
- Use count

## CLI Commands

```bash
# Show active agents
proof spawn status

# Show spawn/prune/graduate history
proof spawn history

# Manually terminate agent
proof spawn kill <agent_id>

# List graduated patterns
proof spawn patterns

# Simulate spawning without execution
proof spawn simulate --gate RED --wounds 5
```

## Feature Flags

All features start disabled (shadow mode):

```python
FEATURE_AGENT_SPAWNING_ENABLED = False
FEATURE_GREEN_LEARNERS_ENABLED = False
FEATURE_YELLOW_WATCHERS_ENABLED = False
FEATURE_RED_HELPERS_ENABLED = False
FEATURE_RECURSIVE_GATING_ENABLED = False
FEATURE_TOPOLOGY_CLASSIFICATION_ENABLED = False
FEATURE_PATTERN_GRADUATION_ENABLED = False
FEATURE_SIBLING_COORDINATION_ENABLED = False
```

Deployment sequence:
1. All OFF (shadow mode, log what would spawn)
2. GREEN_LEARNERS only (lowest risk)
3. YELLOW_WATCHERS (monitoring without intervention)
4. RED_HELPERS (active problem solving)
5. RECURSIVE_GATING (full depth)
6. TOPOLOGY + GRADUATION (self-improvement loop)

## SLO Thresholds

| Operation | Target |
|-----------|--------|
| Agent spawn | < 50ms |
| Sibling coordination | < 100ms |
| Graduation evaluation | < 200ms |
| Maximum depth | 3 |
| Maximum population | 50 |

## Receipt Types

Every operation emits a receipt:

- **spawn**: Agent(s) created
- **graduation**: Agent promoted to pattern
- **pruning**: Agent(s) terminated
- **topology**: Agent classification result
- **coordination**: Sibling group resolution

## The Chef's Kiss

Traffic lights that birth agents. Agents that compete to solve problems. Winners that graduate to permanent helpers. Losers that get pruned. All with receipts.

Self-improvement through natural selection, not arbitrary tuning.

*No receipt → not real. No spawn → no learning. No graduation → no improvement.*
