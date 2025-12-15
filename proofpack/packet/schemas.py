"""Receipt schema definitions for packet module.

Schemas: attach_receipt, consistency_receipt, halt_receipt, packet_receipt
"""

PACKET_SCHEMAS = {
    "attach": {
        "receipt_type": "attach",
        "ts": "ISO8601 timestamp",
        "tenant_id": "string",
        "payload_hash": "dual-hash format",
        "claim_count": "integer - total claims processed",
        "receipt_count": "integer - total receipts available",
        "attached_count": "integer - claims with ≥1 supporting receipt",
        "unattached_claims": "list of claim_id strings with zero receipts",
        "attach_map": "dict mapping claim_id → list of receipt_hash strings",
    },
    "consistency": {
        "receipt_type": "consistency",
        "ts": "ISO8601 timestamp",
        "tenant_id": "string",
        "payload_hash": "dual-hash format",
        "match_score": "float 0-1",
        "threshold": "float (0.999 per CLAUDEME §6)",
        "passed": "boolean",
        "mismatches": "list of {claim_id, reason} dicts",
        "escalation_hours": "integer 4 if failed, null if passed",
    },
    "halt": {
        "receipt_type": "halt",
        "ts": "ISO8601 timestamp",
        "tenant_id": "string",
        "payload_hash": "dual-hash format",
        "reason": "string description",
        "match_score": "float - actual score",
        "threshold": "float - required threshold",
        "escalation_deadline": "ISO8601 - now + 4 hours",
        "requires_human": "boolean true",
    },
    "packet": {
        "receipt_type": "packet",
        "ts": "ISO8601 timestamp",
        "tenant_id": "string",
        "payload_hash": "dual-hash format",
        "packet_id": "UUID string",
        "brief_hash": "dual-hash of brief content",
        "attachment_count": "integer - unique receipts attached",
        "consistency_score": "float from audit",
        "decision_health": "dict with strength, coverage, efficiency floats",
    },
}
