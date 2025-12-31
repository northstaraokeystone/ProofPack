# RNES Compliance Guide

How to emit RNES-compliant receipts from any system.

## What is RNES?

RNES (Receipts-Native Execution Standard) is an open standard for auditable, tamper-evident records. Any system can emit RNES-compliant receipts, enabling interoperability across governance infrastructures.

## Compliance Levels

| Level | Requirements | Use Case |
|-------|--------------|----------|
| **RNES-CORE** | receipt_type, ts, payload_hash | Minimal logging |
| **RNES-AUDIT** | + tenant_id, lineage_id, merkle_anchor | Compliance systems |
| **RNES-FULL** | + privacy_level, slo_status, economic_trigger | Enterprise governance |

## RNES-CORE

Minimum viable receipt:

```json
{
    "receipt_type": "event",
    "ts": "2024-01-01T12:00:00Z",
    "payload_hash": "a1b2c3d4...64chars...:e5f6g7h8...64chars..."
}
```

### Requirements

1. `receipt_type` - Non-empty string identifying the receipt type
2. `ts` - ISO8601 timestamp with Z suffix
3. `payload_hash` - Dual-hash in SHA256:BLAKE3 format

### Dual-Hash Format

```
<sha256_hex_64chars>:<blake3_hex_64chars>
```

Python implementation:

```python
import hashlib
try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

def dual_hash(data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    b3 = blake3.blake3(data).hexdigest() if HAS_BLAKE3 else sha
    return f"{sha}:{b3}"
```

## RNES-AUDIT

Adds tenant isolation and lineage:

```json
{
    "receipt_type": "decision",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "org-123",
    "payload_hash": "abc123...:def456...",
    "lineage_id": "uuid-of-parent-receipt",
    "merkle_anchor": "root-hash-of-batch"
}
```

### Additional Requirements

4. `tenant_id` - Non-empty string for tenant isolation
5. `lineage_id` (optional) - UUID linking to parent receipt
6. `merkle_anchor` (optional) - Merkle root of containing batch

## RNES-FULL

Complete governance receipt:

```json
{
    "receipt_type": "decision",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "org-123",
    "payload_hash": "abc123...:def456...",
    "lineage_id": "uuid-parent",
    "merkle_anchor": "root-hash",
    "privacy_level": "redacted",
    "redacted_fields": ["pii_field"],
    "economic_metadata": {
        "slo_status": "met",
        "payment_eligible": true,
        "payment_amount_usd": 0.001
    },
    "offline_metadata": {
        "generated_offline": false
    }
}
```

### Additional Fields

7. `privacy_level` - "public", "redacted", or "zk_stub"
8. `redacted_fields` - List of redacted field names
9. `economic_metadata` - SLO and payment information
10. `offline_metadata` - Offline generation details

## Validation

### Using ProofPack

```python
from proofpack.privacy import check_rnes_compliance

receipt = {"receipt_type": "test", "ts": "2024-01-01T00:00:00Z", ...}
level, violations = check_rnes_compliance(receipt)

if violations:
    print(f"Non-compliant: {violations}")
else:
    print(f"Compliant at {level}")
```

### Manual Validation

```python
import re

def validate_rnes_core(receipt: dict) -> list[str]:
    violations = []

    if not receipt.get("receipt_type"):
        violations.append("missing receipt_type")

    if not receipt.get("ts"):
        violations.append("missing ts")
    elif not receipt["ts"].endswith("Z"):
        violations.append("ts must end with Z")

    payload_hash = receipt.get("payload_hash", "")
    pattern = r"^[a-f0-9]{64}:[a-f0-9]{64}$"
    if not re.match(pattern, payload_hash):
        violations.append("invalid payload_hash format")

    return violations
```

## Generating Compliant Receipts

### Python

```python
import json
import hashlib
from datetime import datetime

def emit_rnes_receipt(receipt_type: str, data: dict, tenant_id: str = "default") -> dict:
    payload = json.dumps(data, sort_keys=True)
    sha = hashlib.sha256(payload.encode()).hexdigest()
    # Use sha twice if blake3 not available
    payload_hash = f"{sha}:{sha}"

    return {
        "receipt_type": receipt_type,
        "ts": datetime.utcnow().isoformat() + "Z",
        "tenant_id": tenant_id,
        "payload_hash": payload_hash,
        **data
    }
```

### JavaScript/TypeScript

```typescript
import { createHash } from 'crypto';

function emitRnesReceipt(receiptType: string, data: object, tenantId = 'default') {
    const payload = JSON.stringify(data, Object.keys(data).sort());
    const sha = createHash('sha256').update(payload).digest('hex');
    const payloadHash = `${sha}:${sha}`;

    return {
        receipt_type: receiptType,
        ts: new Date().toISOString(),
        tenant_id: tenantId,
        payload_hash: payloadHash,
        ...data
    };
}
```

### Go

```go
import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "time"
)

func EmitRnesReceipt(receiptType string, data map[string]interface{}, tenantId string) map[string]interface{} {
    payload, _ := json.Marshal(data)
    hash := sha256.Sum256(payload)
    sha := hex.EncodeToString(hash[:])
    payloadHash := sha + ":" + sha

    receipt := map[string]interface{}{
        "receipt_type": receiptType,
        "ts":           time.Now().UTC().Format(time.RFC3339),
        "tenant_id":    tenantId,
        "payload_hash": payloadHash,
    }
    for k, v := range data {
        receipt[k] = v
    }
    return receipt
}
```

## Common Mistakes

| Mistake | Correction |
|---------|------------|
| Missing Z suffix on timestamp | Use `datetime.utcnow().isoformat() + "Z"` |
| Single hash instead of dual | Always use SHA256:BLAKE3 format |
| Empty tenant_id | Provide meaningful tenant identifier |
| Non-deterministic payload_hash | Sort keys before hashing |
| Redacting protected fields | Never redact receipt_type, ts, tenant_id, payload_hash |

## Testing Compliance

```bash
# Validate receipt file
proof rnes validate receipt.json

# Check compliance level
proof rnes level receipt.json

# Batch validation
proof rnes validate receipts.jsonl --format jsonl
```

## Enterprise Receipt Types (RNES v1.1)

RNES v1.1 adds receipt types for enterprise governance (CLAUDEME §12-14):

### workflow_receipt
Tracks execution DAG traversal with deviation detection:
```json
{
    "receipt_type": "workflow",
    "graph_hash": "sha256:blake3",
    "planned_path": ["ledger", "brief", "packet"],
    "actual_path": ["ledger", "brief", "packet"],
    "deviations": []
}
```

### sandbox_execution_receipt
Records containerized tool execution:
```json
{
    "receipt_type": "sandbox_execution",
    "tool_name": "http_fetch",
    "container_id": "sandbox-abc123",
    "network_calls": [{"domain": "api.usaspending.gov", "allowed": true}]
}
```

### inference_receipt
Tracks ML model calls with version hashing:
```json
{
    "receipt_type": "inference",
    "model_id": "llm-v3",
    "model_version": "v1.2.3",
    "model_hash": "sha256:blake3",
    "input_hash": "sha256:blake3",
    "output_hash": "sha256:blake3"
}
```

### plan_proposal_receipt
Records plan generation for HITL approval:
```json
{
    "receipt_type": "plan_proposal",
    "plan_id": "uuid",
    "steps": [{"step_id": "1", "action": "fetch", "tool": "http"}],
    "risk_assessment": {"score": 0.75, "level": "high"}
}
```

### plan_approval_receipt
Records human approval decisions:
```json
{
    "receipt_type": "plan_approval",
    "plan_id": "uuid",
    "decision": "approved",
    "modifier_id": "human_reviewer_1"
}
```

## See Also

- [RNES Specification v1.1](../standards/RNES_v1.md)
- [Privacy Levels](privacy-levels.md)
- [Economic Integration](economic-integration.md)
- [Architecture - Enterprise Systems](architecture.md#system-4-workflow-visibility-claudeme-12)
