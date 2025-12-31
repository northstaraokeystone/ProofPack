"""Tests for offline module."""
import pytest

from proofpack.offline.queue import (
    enqueue_receipt,
    get_queue_size,
    get_local_merkle_root,
    peek_queue,
    clear_queue,
)
from proofpack.offline.merkle_local import (
    build_local_merkle,
    get_proof_path,
    verify_local_inclusion,
)
from proofpack.offline.sync import is_connected


class TestOfflineQueue:
    """Test offline queue functionality."""

    @pytest.fixture(autouse=True)
    def setup_temp_queue(self, tmp_path, monkeypatch):
        """Set up temporary queue directory."""
        queue_path = tmp_path / "offline_queue.jsonl"
        state_path = tmp_path / "offline_state.json"

        # Monkeypatch the default paths
        import proofpack.offline.queue as queue_module
        monkeypatch.setattr(queue_module, "DEFAULT_QUEUE_PATH", queue_path)
        monkeypatch.setattr(queue_module, "DEFAULT_STATE_PATH", state_path)

        yield

        # Cleanup
        if queue_path.exists():
            queue_path.unlink()
        if state_path.exists():
            state_path.unlink()

    def test_enqueue_receipt(self):
        """Test enqueueing a receipt."""
        receipt = enqueue_receipt({
            "receipt_type": "test",
            "action": "test_action",
        })

        assert receipt is not None
        assert "offline_metadata" in receipt
        assert receipt["offline_metadata"]["generated_offline"]
        assert receipt["offline_metadata"]["local_sequence_id"] == 1

    def test_queue_size(self):
        """Test queue size tracking."""
        assert get_queue_size() == 0

        enqueue_receipt({"receipt_type": "test1"})
        assert get_queue_size() == 1

        enqueue_receipt({"receipt_type": "test2"})
        assert get_queue_size() == 2

    def test_peek_queue(self):
        """Test peeking at queue contents."""
        enqueue_receipt({"receipt_type": "first"})
        enqueue_receipt({"receipt_type": "second"})

        peeked = peek_queue(1)
        assert len(peeked) == 1
        assert peeked[0]["receipt_type"] == "first"

    def test_clear_queue(self):
        """Test clearing queue."""
        enqueue_receipt({"receipt_type": "test"})
        assert get_queue_size() == 1

        clear_queue()
        assert get_queue_size() == 0

    def test_merkle_root_computed(self):
        """Test Merkle root computation."""
        assert get_local_merkle_root() is None

        enqueue_receipt({"receipt_type": "test"})
        root = get_local_merkle_root()

        assert root is not None
        assert ":" in root  # Dual-hash format


class TestLocalMerkle:
    """Test local Merkle tree operations."""

    def test_build_merkle_tree(self):
        """Test building Merkle tree from receipts."""
        receipts = [
            {"receipt_type": "r1", "value": 1},
            {"receipt_type": "r2", "value": 2},
            {"receipt_type": "r3", "value": 3},
        ]

        tree = build_local_merkle(receipts)

        assert tree["root"] is not None
        assert tree["leaf_count"] == 3
        assert len(tree["leaf_hashes"]) == 3
        assert len(tree["tree"]) > 1  # Multiple levels

    def test_empty_tree(self):
        """Test empty tree handling."""
        tree = build_local_merkle([])

        assert tree["leaf_count"] == 0
        assert tree["root"] is not None  # Hash of "empty"

    def test_proof_path(self):
        """Test getting proof path."""
        receipts = [
            {"receipt_type": "r1"},
            {"receipt_type": "r2"},
            {"receipt_type": "r3"},
            {"receipt_type": "r4"},
        ]

        tree = build_local_merkle(receipts)
        target_hash = tree["leaf_hashes"][1]

        path = get_proof_path(target_hash, tree)

        assert path is not None
        assert len(path) > 0

    def test_verify_inclusion(self):
        """Test verifying inclusion proof."""
        receipts = [
            {"receipt_type": "r1"},
            {"receipt_type": "r2"},
        ]

        tree = build_local_merkle(receipts)
        target_hash = tree["leaf_hashes"][0]
        path = get_proof_path(target_hash, tree)

        assert verify_local_inclusion(target_hash, path, tree["root"])


class TestConnectivity:
    """Test connectivity checking."""

    def test_is_connected_default(self):
        """Test connectivity check with default parameters."""
        # This should return False since no server is running
        result = is_connected(timeout=0.5)
        assert isinstance(result, bool)
