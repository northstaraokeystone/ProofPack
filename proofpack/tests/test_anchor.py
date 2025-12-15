"""Tests for proofpack.anchor module."""
import time

import pytest

from proofpack.anchor import merkle_root, merkle_proof, verify_proof, hash_to_position
from proofpack.core.receipt import merkle as core_merkle


class TestMerkleRoot:
    """Tests for merkle_root function."""

    def test_merkle_root_matches_core(self):
        """anchor.merkle_root() == core.merkle()."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}]
        anchor_result = merkle_root(items)
        core_result = core_merkle(items)
        assert anchor_result == core_result

    def test_merkle_root_empty(self):
        """Empty list returns consistent hash."""
        result = merkle_root([])
        assert ":" in result
        assert len(result.split(":")[0]) == 64

    def test_merkle_root_deterministic(self):
        """Same items produce same root."""
        items = [{"x": 1}, {"y": 2}]
        result1 = merkle_root(items)
        result2 = merkle_root(items)
        assert result1 == result2


class TestMerkleProof:
    """Tests for merkle_proof function."""

    def test_merkle_proof_generates_path(self):
        """merkle_proof() returns dict with path, indices."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}]
        proof = merkle_proof(items[0], items)

        assert "item_hash" in proof
        assert "path" in proof
        assert "indices" in proof
        assert "root" in proof
        assert isinstance(proof["path"], list)
        assert isinstance(proof["indices"], list)
        assert len(proof["path"]) == len(proof["indices"])

    def test_merkle_proof_single_item(self):
        """Single item tree has empty path."""
        items = [{"a": 1}]
        proof = merkle_proof(items[0], items)
        assert proof["path"] == []
        assert proof["indices"] == []

    def test_merkle_proof_item_not_found(self):
        """Missing item raises ValueError."""
        items = [{"a": 1}, {"b": 2}]
        with pytest.raises(ValueError) as exc_info:
            merkle_proof({"c": 3}, items)
        assert "not in tree" in str(exc_info.value)


class TestVerifyProof:
    """Tests for verify_proof function."""

    def test_verify_proof_valid(self):
        """verify_proof(item, proof, root) returns True for valid proof."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}]
        item = items[1]
        proof = merkle_proof(item, items)
        root = merkle_root(items)

        result = verify_proof(item, proof, root)
        assert result is True

    def test_verify_proof_invalid_item(self):
        """Modified item returns False."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}]
        item = items[1]
        proof = merkle_proof(item, items)
        root = merkle_root(items)

        # Modify the item
        modified_item = {"b": 999}
        result = verify_proof(modified_item, proof, root)
        assert result is False

    def test_verify_proof_invalid_root(self):
        """Wrong root returns False."""
        items = [{"a": 1}, {"b": 2}]
        item = items[0]
        proof = merkle_proof(item, items)

        result = verify_proof(item, proof, "wrong:root")
        assert result is False

    def test_verify_proof_slo_latency(self):
        """verify_proof() completes in <= 2s (p95 target)."""
        items = [{"x": i} for i in range(100)]
        item = items[50]
        proof = merkle_proof(item, items)
        root = merkle_root(items)

        start = time.perf_counter()
        verify_proof(item, proof, root)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0  # SLO target

    def test_verify_proof_all_items(self):
        """Verify proof works for all items in tree."""
        items = [{"value": i} for i in range(8)]
        root = merkle_root(items)

        for item in items:
            proof = merkle_proof(item, items)
            assert verify_proof(item, proof, root) is True


class TestHashToPosition:
    """Tests for hash_to_position function."""

    def test_hash_to_position_length(self):
        """hash_to_position(h, 8) returns string of length 8."""
        from proofpack.core.receipt import dual_hash
        h = dual_hash(b"test")
        result = hash_to_position(h, 8)
        assert len(result) == 8

    def test_hash_to_position_binary(self):
        """Result contains only 0s and 1s."""
        from proofpack.core.receipt import dual_hash
        h = dual_hash(b"test")
        result = hash_to_position(h, 16)
        assert all(c in "01" for c in result)

    def test_hash_to_position_deterministic(self):
        """Same hash produces same position."""
        from proofpack.core.receipt import dual_hash
        h = dual_hash(b"test")
        result1 = hash_to_position(h, 10)
        result2 = hash_to_position(h, 10)
        assert result1 == result2

    def test_hash_to_position_different_depths(self):
        """Different depths return different length strings."""
        from proofpack.core.receipt import dual_hash
        h = dual_hash(b"test")
        result8 = hash_to_position(h, 8)
        result16 = hash_to_position(h, 16)
        assert len(result8) == 8
        assert len(result16) == 16
        assert result16.startswith(result8)  # Longer includes shorter
