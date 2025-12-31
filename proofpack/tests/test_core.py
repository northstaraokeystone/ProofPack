"""Tests for proofpack.core.receipt and proofpack.core.schemas."""
import pytest

from proofpack.core.receipt import dual_hash, emit_receipt, merkle, StopRule
from proofpack.core.schemas import validate_receipt


class TestDualHash:
    """Tests for dual_hash function."""

    def test_dual_hash_format(self):
        """Output contains ':' separator, both parts are 64 hex chars."""
        result = dual_hash(b"test")
        parts = result.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 64
        assert len(parts[1]) == 64
        # Verify hex format
        int(parts[0], 16)
        int(parts[1], 16)

    def test_dual_hash_deterministic(self):
        """Same input produces same output."""
        result1 = dual_hash(b"test")
        result2 = dual_hash(b"test")
        assert result1 == result2

    def test_dual_hash_string_input(self):
        """String input is handled correctly."""
        result = dual_hash("test")
        parts = result.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 64

    def test_dual_hash_different_inputs(self):
        """Different inputs produce different hashes."""
        result1 = dual_hash(b"test1")
        result2 = dual_hash(b"test2")
        assert result1 != result2


class TestEmitReceipt:
    """Tests for emit_receipt function."""

    def test_emit_receipt_fields(self, capsys):
        """Output has receipt_type, ts, tenant_id, payload_hash."""
        result = emit_receipt("ingest", {"source_type": "test"})
        assert "receipt_type" in result
        assert "ts" in result
        assert "tenant_id" in result
        assert "payload_hash" in result

    def test_emit_receipt_tenant_default(self, capsys):
        """Missing tenant_id defaults to 'default'."""
        result = emit_receipt("ingest", {"source_type": "test"})
        assert result["tenant_id"] == "default"

    def test_emit_receipt_tenant_from_data(self, capsys):
        """tenant_id from data is used."""
        result = emit_receipt("ingest", {"tenant_id": "custom", "source_type": "test"})
        assert result["tenant_id"] == "custom"

    def test_emit_receipt_prints_json(self, capsys):
        """Receipt is printed to stdout."""
        emit_receipt("ingest", {"source_type": "test"})
        captured = capsys.readouterr()
        assert "receipt_type" in captured.out
        assert "ingest" in captured.out


class TestMerkle:
    """Tests for merkle function."""

    def test_merkle_empty(self):
        """Empty list returns dual_hash(b'empty')."""
        result = merkle([])
        expected = dual_hash(b"empty")
        assert result == expected

    def test_merkle_single(self):
        """Single item returns its hash."""
        item = {"a": 1}
        result = merkle([item])
        # Single item, no combining needed
        assert ":" in result
        assert len(result.split(":")[0]) == 64

    def test_merkle_deterministic(self):
        """Same items produce same root."""
        items = [{"a": 1}, {"b": 2}]
        result1 = merkle(items)
        result2 = merkle(items)
        assert result1 == result2

    def test_merkle_order_matters(self):
        """Different order produces different root."""
        items1 = [{"a": 1}, {"b": 2}]
        items2 = [{"b": 2}, {"a": 1}]
        result1 = merkle(items1)
        result2 = merkle(items2)
        assert result1 != result2

    def test_merkle_odd_count(self):
        """Odd count duplicates last hash."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}]
        result = merkle(items)
        assert ":" in result
        assert len(result.split(":")[0]) == 64


class TestStopRule:
    """Tests for StopRule exception."""

    def test_stoprule_is_exception(self):
        """StopRule is an Exception subclass."""
        assert issubclass(StopRule, Exception)

    def test_stoprule_raises(self):
        """StopRule can be raised and caught."""
        with pytest.raises(StopRule) as exc_info:
            raise StopRule("test error")
        assert "test error" in str(exc_info.value)


class TestValidateReceipt:
    """Tests for validate_receipt function."""

    def test_validate_receipt_pass(self, sample_receipt):
        """Valid receipt returns True."""
        result = validate_receipt(sample_receipt)
        assert result is True

    def test_validate_receipt_missing_field(self):
        """Missing required field raises StopRule."""
        invalid = {
            "receipt_type": "ingest",
            "ts": "2024-01-01T00:00:00Z",
            # Missing tenant_id and payload_hash
        }
        with pytest.raises(StopRule) as exc_info:
            validate_receipt(invalid)
        assert "Missing required field" in str(exc_info.value)

    def test_validate_receipt_unknown_type(self):
        """Unknown receipt_type raises StopRule."""
        invalid = {
            "receipt_type": "unknown_type",
            "ts": "2024-01-01T00:00:00Z",
            "tenant_id": "test",
            "payload_hash": "abc:def",
        }
        with pytest.raises(StopRule) as exc_info:
            validate_receipt(invalid)
        assert "Unknown receipt_type" in str(exc_info.value)

    def test_validate_receipt_not_dict(self):
        """Non-dict raises StopRule."""
        with pytest.raises(StopRule) as exc_info:
            validate_receipt("not a dict")
        assert "must be a dict" in str(exc_info.value)
