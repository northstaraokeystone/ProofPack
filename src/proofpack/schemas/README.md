# ProofPack Schema

Central JSON Schema definitions for ProofPack v3 receipts, configuration, and module interfaces.

## Structure

```
proofpack-schema/
├── receipts/           # Receipt type schemas
│   ├── _base.schema.json
│   └── *.schema.json   # 16 receipt types
├── config/
│   └── proofpack.config.schema.json
├── interface/
│   └── module.interface.schema.json
└── VERSION
```

## Receipt Types

All receipts extend `_base.schema.json` with required fields:
- `receipt_type`: Type identifier
- `ts`: ISO8601 timestamp
- `tenant_id`: Tenant isolation
- `payload_hash`: Dual hash (`SHA256:BLAKE3` format)

### Available Schemas

| Schema | Receipt Type | Purpose |
|--------|--------------|---------|
| ingest | ingest | Data ingestion with redaction tracking |
| anchor | anchor | Merkle tree anchoring |
| verify | verify | Proof verification |
| compaction | compaction | Data compaction with continuity |
| brief | brief | Executive brief generation |
| health | decision_health | Decision health metrics |
| packet | packet | Evidence packet assembly |
| attach | attach | Receipt attachment to claims |
| consistency | consistency | Cross-packet consistency |
| alert | anomaly | Anomaly detection alerts |
| resource | resource | Resource usage tracking |
| gap | gap | Gap identification |
| helper_blueprint | helper_blueprint | Automation blueprint |
| effectiveness | effectiveness | Helper effectiveness tracking |
| approval | approval | Human approval decisions |
| completeness | completeness | System completeness levels |
| cycle | cycle | Self-improvement cycle |

## Hash Strategy

All hashes use dual-algorithm format: `{SHA256}:{BLAKE3}`

Pattern: `^[a-f0-9]{64}:[a-f0-9]{64}$`

## Usage

```python
import json
from jsonschema import validate, Draft7Validator

# Load schema
with open('receipts/ingest.schema.json') as f:
    schema = json.load(f)

# Validate receipt
validate(instance=receipt, schema=schema)
```

## Version

Current: 3.0.0 (see VERSION file)

## Schema Standard

JSON Schema draft-07
