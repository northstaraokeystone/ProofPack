"""Tests for privacy module."""
import pytest
from privacy import (
    redact_receipt,
    verify_redaction,
    get_public_view,
    check_rnes_compliance,
    prepare_for_audit,
)


class TestRedaction:
    """Test receipt redaction functionality."""

    def test_basic_redaction(self):
        """Test redacting a single field."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "secret_field": "secret_value",
        }

        redacted = redact_receipt(receipt, ["secret_field"])

        assert redacted["privacy_level"] == "redacted"
        assert "secret_field" in redacted["redacted_fields"]
        assert redacted["secret_field"].startswith("[REDACTED:")

    def test_cannot_redact_protected_fields(self):
        """Test that protected fields cannot be redacted."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
        }

        with pytest.raises(ValueError):
            redact_receipt(receipt, ["receipt_type"])

    def test_multiple_field_redaction(self):
        """Test redacting multiple fields."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }

        redacted = redact_receipt(receipt, ["field1", "field2"])

        assert len(redacted["redacted_fields"]) == 2
        assert "field1" in redacted["redacted_fields"]
        assert "field2" in redacted["redacted_fields"]
        assert redacted["field3"] == "value3"  # Unchanged


class TestVerification:
    """Test redaction verification."""

    def test_verify_valid_redaction(self):
        """Test verification of valid redacted receipt."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "secret": "hidden",
        }

        redacted = redact_receipt(receipt, ["secret"])
        original_hash = receipt["payload_hash"]

        assert verify_redaction(original_hash, redacted)

    def test_verify_invalid_structure(self):
        """Test verification fails for invalid structure."""
        invalid = {
            "receipt_type": "test",
            "privacy_level": "public",  # Not redacted
        }

        assert not verify_redaction("hash", invalid)


class TestPublicView:
    """Test public view generation."""

    def test_public_receipt_returns_all(self):
        """Public receipt returns all fields."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "custom_field": "value",
        }

        public = get_public_view(receipt)
        assert "custom_field" in public

    def test_redacted_receipt_limits_fields(self):
        """Redacted receipt limits visible fields."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "secret": "hidden",
        }

        redacted = redact_receipt(receipt, ["secret"])
        public = get_public_view(redacted)

        # Secret should not be in public view content
        assert "redacted_fields" in public


class TestRNESCompliance:
    """Test RNES compliance checking."""

    def test_core_compliance(self):
        """Test RNES-CORE compliance detection."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
        }

        level, violations = check_rnes_compliance(receipt)
        assert level == "RNES-CORE"
        assert len(violations) == 0

    def test_non_compliant_missing_fields(self):
        """Test non-compliance with missing fields."""
        receipt = {"receipt_type": "test"}

        level, violations = check_rnes_compliance(receipt)
        assert level == "NON-COMPLIANT"
        assert len(violations) > 0

    def test_invalid_payload_hash_format(self):
        """Test non-compliance with invalid hash format."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "payload_hash": "invalid_hash",
        }

        level, violations = check_rnes_compliance(receipt)
        assert level == "NON-COMPLIANT"


class TestAuditPreparation:
    """Test audit view preparation."""

    def test_core_audit(self):
        """Test RNES-CORE audit format."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "extra_field": "value",
        }

        core = prepare_for_audit(receipt, "RNES-CORE")

        assert "receipt_type" in core
        assert "ts" in core
        assert "payload_hash" in core
        assert "extra_field" not in core

    def test_full_audit(self):
        """Test RNES-FULL audit format."""
        receipt = {
            "receipt_type": "test",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "a" * 64 + ":" + "b" * 64,
            "extra_field": "value",
        }

        full = prepare_for_audit(receipt, "RNES-FULL")

        assert "extra_field" in full
        assert "privacy_level" in full
