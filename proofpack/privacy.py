"""Privacy module for RNES-compliant receipt redaction.

Provides field-level redaction while maintaining cryptographic integrity.
Redaction is ONE-WAY - cannot un-redact without original data.

Usage:
    from proofpack.privacy import redact_receipt, verify_redaction

    # Redact sensitive fields
    redacted = redact_receipt(receipt, ["pii_field", "proprietary_data"])

    # Verify redaction maintains integrity
    is_valid = verify_redaction(original_hash, redacted)

Privacy Levels:
    - public: All fields visible
    - redacted: Specified fields replaced with hashes
    - zk_stub: Placeholder for future ZK proof integration
"""
import copy
import json
from datetime import datetime
from typing import Optional

from proofpack.core.receipt import dual_hash, emit_receipt


# Fields that must NEVER be redacted (required for RNES compliance)
PROTECTED_FIELDS = frozenset([
    "receipt_type",
    "ts",
    "tenant_id",
    "payload_hash",
])

# Fields always included in public view
DEFAULT_PUBLIC_FIELDS = frozenset([
    "receipt_type",
    "ts",
    "tenant_id",
    "payload_hash",
    "privacy_level",
    "redacted_fields",
])


def redact_receipt(
    receipt: dict,
    fields_to_redact: list[str],
    reason: str = "proprietary",
    tenant_id: str = "default"
) -> dict:
    """Replace specified fields with hashes, maintaining receipt integrity.

    Args:
        receipt: Original receipt to redact
        fields_to_redact: List of field names to redact
        reason: Why redaction occurred (proprietary|pii|classified|regulatory)
        tenant_id: Tenant performing redaction

    Returns:
        Redacted receipt with original fields replaced by hashes

    Raises:
        ValueError: If attempting to redact protected fields
    """
    # Validate no protected fields
    protected_violation = set(fields_to_redact) & PROTECTED_FIELDS
    if protected_violation:
        emit_receipt("anomaly", {
            "tenant_id": tenant_id,
            "metric": "redaction_violation",
            "baseline": 0,
            "delta": len(protected_violation),
            "classification": "violation",
            "action": "reject"
        })
        raise ValueError(f"Cannot redact protected fields: {protected_violation}")

    # Store original hash before redaction
    original_hash = receipt.get("payload_hash", dual_hash(json.dumps(receipt, sort_keys=True)))

    # Create redacted copy
    redacted = copy.deepcopy(receipt)
    actually_redacted = []

    for field in fields_to_redact:
        if field in redacted:
            # Replace field value with hash of original value
            original_value = redacted[field]
            field_hash = dual_hash(json.dumps(original_value, sort_keys=True))
            redacted[field] = f"[REDACTED:{field_hash[:32]}]"
            actually_redacted.append(field)

    # Update privacy metadata
    redacted["privacy_level"] = "redacted"
    redacted["redacted_fields"] = actually_redacted
    redacted["public_fields"] = list(DEFAULT_PUBLIC_FIELDS)

    # Emit redaction receipt for audit trail
    emit_receipt("redaction", {
        "tenant_id": tenant_id,
        "original_receipt_id": receipt.get("payload_hash", "unknown"),
        "original_hash": original_hash,
        "redacted_fields": actually_redacted,
        "redaction_reason": reason,
        "redacted_by": tenant_id
    })

    return redacted


def verify_redaction(original_hash: str, redacted_receipt: dict) -> bool:
    """Confirm redacted receipt is valid transformation of original.

    Args:
        original_hash: Dual-hash of original (unredacted) receipt
        redacted_receipt: Receipt after redaction

    Returns:
        True if redaction appears valid (has required structure)

    Note:
        This verifies structure, not content. Without the original,
        we cannot verify the redacted values are correct - only that
        the redaction format is valid.
    """
    # Check required fields present
    if "privacy_level" not in redacted_receipt:
        return False
    if redacted_receipt.get("privacy_level") != "redacted":
        return False

    # Check redacted_fields list exists
    redacted_fields = redacted_receipt.get("redacted_fields", [])
    if not isinstance(redacted_fields, list):
        return False

    # Verify each redacted field has proper format
    for field in redacted_fields:
        if field not in redacted_receipt:
            continue
        value = redacted_receipt[field]
        if not isinstance(value, str):
            return False
        if not value.startswith("[REDACTED:"):
            return False

    return True


def get_public_view(receipt: dict, tenant_id: str = "default") -> dict:
    """Return only public fields from receipt.

    Args:
        receipt: Full receipt (may be redacted or public)

    Returns:
        Receipt with only public fields included
    """
    privacy_level = receipt.get("privacy_level", "public")

    if privacy_level == "public":
        # All fields visible for public receipts
        return copy.deepcopy(receipt)

    # For redacted/zk_stub, return only public fields
    public_fields = set(receipt.get("public_fields", DEFAULT_PUBLIC_FIELDS))
    public_view = {}

    for field in public_fields:
        if field in receipt:
            public_view[field] = receipt[field]

    # Always include redacted field markers (but not their values)
    if "redacted_fields" in receipt:
        public_view["redacted_fields"] = receipt["redacted_fields"]

    return public_view


def prepare_for_audit(
    receipt: dict,
    audit_level: str = "RNES-AUDIT",
    tenant_id: str = "default"
) -> dict:
    """Format receipt for compliance disclosure.

    Args:
        receipt: Receipt to prepare
        audit_level: RNES-CORE, RNES-AUDIT, or RNES-FULL
        tenant_id: Tenant requesting audit

    Returns:
        Receipt formatted for specified audit level
    """
    audit_receipt = copy.deepcopy(receipt)

    if audit_level == "RNES-CORE":
        # Minimal: just receipt_type, ts, payload_hash
        return {
            "receipt_type": audit_receipt.get("receipt_type"),
            "ts": audit_receipt.get("ts"),
            "payload_hash": audit_receipt.get("payload_hash"),
        }

    elif audit_level == "RNES-AUDIT":
        # Add tenant, lineage, merkle
        core = {
            "receipt_type": audit_receipt.get("receipt_type"),
            "ts": audit_receipt.get("ts"),
            "tenant_id": audit_receipt.get("tenant_id"),
            "payload_hash": audit_receipt.get("payload_hash"),
        }
        if "lineage_id" in audit_receipt:
            core["lineage_id"] = audit_receipt["lineage_id"]
        if "merkle_anchor" in audit_receipt:
            core["merkle_anchor"] = audit_receipt["merkle_anchor"]
        return core

    elif audit_level == "RNES-FULL":
        # Include privacy and economic metadata
        if "privacy_level" not in audit_receipt:
            audit_receipt["privacy_level"] = "public"
        return audit_receipt

    else:
        raise ValueError(f"Unknown audit level: {audit_level}")


def check_rnes_compliance(receipt: dict) -> tuple[str, list[str]]:
    """Check receipt compliance level and any violations.

    Args:
        receipt: Receipt to check

    Returns:
        Tuple of (compliance_level, list_of_violations)
        compliance_level: "RNES-CORE", "RNES-AUDIT", "RNES-FULL", or "NON-COMPLIANT"
    """
    violations = []

    # Check RNES-CORE requirements
    if "receipt_type" not in receipt:
        violations.append("missing receipt_type")
    if "ts" not in receipt:
        violations.append("missing ts")
    if "payload_hash" not in receipt:
        violations.append("missing payload_hash")

    if violations:
        return "NON-COMPLIANT", violations

    # Check payload_hash format
    payload_hash = receipt.get("payload_hash", "")
    if not _is_valid_dual_hash(payload_hash):
        violations.append("invalid payload_hash format (expected SHA256:BLAKE3)")
        return "NON-COMPLIANT", violations

    # At minimum RNES-CORE compliant
    level = "RNES-CORE"

    # Check RNES-AUDIT requirements
    has_audit = all([
        "tenant_id" in receipt,
        "lineage_id" in receipt or "merkle_anchor" in receipt
    ])
    if has_audit:
        level = "RNES-AUDIT"

    # Check RNES-FULL requirements
    has_full = all([
        has_audit,
        "privacy_level" in receipt or "economic_metadata" in receipt
    ])
    if has_full:
        level = "RNES-FULL"

    return level, violations


def _is_valid_dual_hash(hash_str: str) -> bool:
    """Check if string is valid dual-hash format."""
    if not isinstance(hash_str, str):
        return False
    parts = hash_str.split(":")
    if len(parts) != 2:
        return False
    return all(len(p) == 64 and all(c in "0123456789abcdef" for c in p) for p in parts)


def create_zk_stub(receipt: dict, constraints: list[str], tenant_id: str = "default") -> dict:
    """Create ZK stub receipt for future ZK proof integration.

    Args:
        receipt: Original receipt
        constraints: List of constraints the ZK proof will verify
        tenant_id: Tenant creating stub

    Returns:
        Receipt with zk_stub privacy level and disclosure_proof placeholder
    """
    stub = copy.deepcopy(receipt)
    stub["privacy_level"] = "zk_stub"
    stub["disclosure_proof"] = f"PENDING_ZK_PROOF:constraints={len(constraints)}"
    stub["zk_constraints"] = constraints

    emit_receipt("zk_stub_created", {
        "tenant_id": tenant_id,
        "original_receipt_id": receipt.get("payload_hash", "unknown"),
        "constraints": constraints,
        "status": "pending"
    })

    return stub
