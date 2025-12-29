# RNES - Receipts-Native Execution Standard

## What is RNES?

RNES (Receipts-Native Execution Standard) is an open standard for systems that need auditable, tamper-evident records of every decision and action. Any system can emit RNES-compliant receipts, enabling interoperability across different governance infrastructures.

## Core Principles

1. **No receipt, not real** - Every action must emit a receipt
2. **Dual-hash integrity** - SHA256 + BLAKE3 for collision resistance
3. **Tenant isolation** - Multi-tenant by design
4. **Merkle-anchored** - Batch receipts into tamper-evident trees

## Compliance Levels

| Level | Fields | Use Case |
|-------|--------|----------|
| RNES-CORE | receipt_type, ts, payload_hash | Minimal logging |
| RNES-AUDIT | + tenant_id, lineage_id, merkle_anchor | Compliance systems |
| RNES-FULL | + privacy_level, slo_status, economic_trigger | Enterprise governance |

## Quick Start

A minimal RNES-compliant receipt:

```json
{
    "receipt_type": "action",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "org-123",
    "payload_hash": "abc...64chars...:def...64chars..."
}
```

## Why RNES?

- **Interoperability**: Exchange receipts across different systems
- **Auditability**: Every decision has cryptographic proof
- **Privacy-ready**: Built-in support for redaction and ZK proofs
- **Offline-capable**: Generate receipts without connectivity
- **Economic integration**: SLO status enables payment triggers

## Implementations

- **ProofPack** - Reference implementation (Python)
- **QED** - Telemetry compression with RNES receipts
- **AXIOM** - Knowledge graph with RNES anchoring

## Resources

- [RNES_v1.md](RNES_v1.md) - Full specification
- [ADOPTERS.md](ADOPTERS.md) - Organizations using RNES
- [CONTRIBUTE.md](CONTRIBUTE.md) - How to propose changes
- [schemas/](schemas/) - JSON Schema definitions

## License

Apache 2.0 - Use freely, contribute openly.

---

*Maintained by Keystone Research Lab*
