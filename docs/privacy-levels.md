# Privacy Levels Guide

ProofPack supports three privacy levels for receipts, enabling compliance with various regulatory requirements while maintaining cryptographic integrity.

## Privacy Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| **public** | All fields visible | Standard audit trail |
| **redacted** | Specified fields replaced with hashes | PII protection, proprietary data |
| **zk_stub** | Placeholder for future ZK proofs | Maximum privacy, pending ZK integration |

## Public Receipts

The default privacy level. All fields are visible to anyone with access to the receipt.

```python
{
    "receipt_type": "decision",
    "ts": "2024-01-01T12:00:00Z",
    "tenant_id": "org-123",
    "payload_hash": "abc...def...",
    "privacy_level": "public",
    "decision_data": "visible to all"
}
```

## Redacted Receipts

Sensitive fields are replaced with their hashes, maintaining integrity while hiding content.

```python
from proofpack.privacy import redact_receipt

# Original receipt
receipt = {
    "receipt_type": "patient_decision",
    "patient_id": "P12345",           # PII - needs redaction
    "treatment_plan": "confidential", # Proprietary - needs redaction
    "outcome": "positive"             # Can remain public
}

# Redact sensitive fields
redacted = redact_receipt(
    receipt,
    fields_to_redact=["patient_id", "treatment_plan"],
    reason="pii"
)

# Result:
# {
#     "receipt_type": "patient_decision",
#     "patient_id": "[REDACTED:abc123...]",
#     "treatment_plan": "[REDACTED:def456...]",
#     "outcome": "positive",
#     "privacy_level": "redacted",
#     "redacted_fields": ["patient_id", "treatment_plan"]
# }
```

### Redaction Reasons

| Reason | Description |
|--------|-------------|
| `proprietary` | Trade secrets, competitive data |
| `pii` | Personally identifiable information |
| `classified` | Security classification |
| `regulatory` | Regulatory compliance requirement |

### Protected Fields

These fields can NEVER be redacted (required for RNES compliance):
- `receipt_type`
- `ts`
- `tenant_id`
- `payload_hash`

## ZK Stub Receipts

Placeholder for future ZK proof integration. Indicates that full privacy will be available when ZK infrastructure is deployed.

```python
from proofpack.privacy import create_zk_stub

stub = create_zk_stub(
    receipt,
    constraints=["value > 0", "category in ['A', 'B', 'C']"]
)

# Result includes:
# {
#     "privacy_level": "zk_stub",
#     "disclosure_proof": "PENDING_ZK_PROOF:constraints=2",
#     "zk_constraints": ["value > 0", "category in ['A', 'B', 'C']"]
# }
```

## Audit Views

### Get Public View

Returns only fields safe for public disclosure:

```python
from proofpack.privacy import get_public_view

public = get_public_view(redacted_receipt)
# Only includes: receipt_type, ts, tenant_id, payload_hash, privacy_level, redacted_fields
```

### Prepare for Audit

Format receipt for specific audit levels:

```python
from proofpack.privacy import prepare_for_audit

# RNES-CORE: minimal fields
core = prepare_for_audit(receipt, "RNES-CORE")

# RNES-AUDIT: + tenant, lineage, merkle
audit = prepare_for_audit(receipt, "RNES-AUDIT")

# RNES-FULL: everything including privacy/economic metadata
full = prepare_for_audit(receipt, "RNES-FULL")
```

## Compliance Checking

```python
from proofpack.privacy import check_rnes_compliance

level, violations = check_rnes_compliance(receipt)

if violations:
    print(f"Non-compliant: {violations}")
else:
    print(f"Compliant at level: {level}")
```

## Verification

Verify that a redacted receipt is structurally valid:

```python
from proofpack.privacy import verify_redaction

is_valid = verify_redaction(original_hash, redacted_receipt)
# Returns True if redaction format is correct
```

Note: Without the original data, we can only verify structure, not content correctness.

## Best Practices

1. **Redact at creation** - Don't store unredacted receipts if not needed
2. **Document redaction reason** - Always specify why redaction occurred
3. **Keep original hashes** - Enable future verification if needed
4. **Use appropriate level** - Don't over-redact public data
5. **Test with auditors** - Verify redacted views meet compliance needs

## Regulatory Considerations

| Regulation | Recommended Approach |
|------------|---------------------|
| GDPR | Redact PII fields, keep processing records |
| HIPAA | Redact PHI, maintain audit trail |
| SOX | Redact proprietary, keep financial decisions |
| ITAR | Use zk_stub for classified data |

## See Also

- [RNES Standard](../standards/RNES_v1.md)
- [Extreme Environments](extreme-environments.md)
- [Economic Integration](economic-integration.md)
