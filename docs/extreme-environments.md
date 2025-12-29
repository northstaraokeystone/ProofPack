# Extreme Environments Guide

ProofPack is designed for systems that operate in extreme environments where connectivity is unreliable, intermittent, or impossible.

## Target Environments

### Off-Planet Systems

**Satellites**
- Low Earth Orbit (LEO): 90-minute orbital periods
- Geostationary: 22,000 miles from ground stations
- Deep space probes: Light-minutes to hours of latency

**Lunar Missions**
- 1.3 second one-way communication delay
- Periodic Earth-facing windows
- Extended dark-side operations

**Use Case:** When a satellite detects an anomaly and needs to make an autonomous course correction, it can't wait for ground control approval. It generates a receipt locally, builds a Merkle proof, and syncs when it next sees a ground station.

### Defense Systems

**RF-Denied Environments**
- Electronic warfare zones
- Adversarial jamming
- Communication blackouts

**Autonomous Platforms**
- Unmanned aerial systems (UAS)
- Autonomous ground vehicles
- Naval autonomous systems

**Use Case:** A drone operating beyond the forward line of troops loses communication. Every decision it makes during the blackout is receipted locally. When it returns to base, the full decision chain is syncable and auditable.

### Autonomous Vehicles

**Connectivity Gaps**
- Tunnels and underground parking
- Remote highways
- Dense urban canyons

**Edge Cases**
- High-speed rail (frequent handoffs)
- Maritime vessels (satellite gaps)
- Aircraft (polar routes)

**Use Case:** An autonomous vehicle entering a 2-mile tunnel continues making navigation decisions. Each decision generates a local receipt. When it exits, the receipts sync to demonstrate the vehicle's decision-making during the connectivity gap.

### Industrial Edge

**Constrained Devices**
- IoT sensors with limited bandwidth
- SCADA systems with periodic check-ins
- Remote oil/gas installations

**Regulated Industries**
- FDA medical devices
- Nuclear plant monitors
- Financial transaction systems

**Use Case:** A medical device operating in a patient's home generates receipts for every dosing decision. When it connects to the hospital network, the receipts provide a complete audit trail.

## Offline Mode Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     OFFLINE MODE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│   │ Generate│───>│  Queue  │───>│ Merkle  │───>│  Store  │ │
│   │ Receipt │    │ Locally │    │ Locally │    │ Locally │ │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                     RECONNECTION                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│   │ Detect  │───>│ Resolve │───>│  Sync   │───>│ Verify  │ │
│   │ Connect │    │Conflicts│    │  Queue  │    │  Sync   │ │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```python
from proofpack.offline import queue, sync

# Generate receipts while offline
for decision in autonomous_decisions:
    receipt = queue.enqueue_receipt({
        "receipt_type": "autonomous_decision",
        "decision": decision.action,
        "confidence": decision.confidence,
        "sensor_state": decision.sensors
    })

# Check connectivity periodically
if sync.is_connected():
    result = sync.full_sync()
    print(f"Synced {result['synced_count']} receipts")
```

## Conflict Resolution

When reconnecting after extended offline operation:

1. **Sequence gaps**: Noted but not blocking
2. **Duplicates**: Automatically skipped
3. **Merkle mismatches**: Flagged for review
4. **Timestamp conflicts**: Logged with explanation

## Storage Requirements

| Offline Duration | Receipts/Hour | Storage Needed |
|------------------|---------------|----------------|
| 1 hour | 100 | ~500 KB |
| 24 hours | 2,400 | ~12 MB |
| 7 days | 16,800 | ~84 MB |
| 30 days | 72,000 | ~360 MB |

Receipts compress well (avg 500 bytes each).

## Best Practices

1. **Set reasonable queue limits** - Prevent unbounded growth
2. **Sync on every connectivity window** - Don't let queues grow
3. **Monitor queue depth** - Alert when approaching limits
4. **Test offline scenarios** - Validate before deployment
5. **Include local Merkle roots** - Enable integrity verification

## See Also

- [RNES Standard](../standards/RNES_v1.md)
- [Privacy Levels](privacy-levels.md)
- [Economic Integration](economic-integration.md)
