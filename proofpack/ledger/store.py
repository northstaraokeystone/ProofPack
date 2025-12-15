"""Append-only receipt storage per CLAUDEME Section 9.

Uses content-addressable storage where receipt_id = payload_hash.
Thread-safe with file locking on write.
"""
import fcntl
import json
from pathlib import Path
from typing import Callable


class LedgerStore:
    """Append-only receipt storage backed by JSONL file.

    Attributes:
        path: Path to the JSONL file
    """

    def __init__(self, path: str = "receipts.jsonl"):
        """Initialize LedgerStore.

        Args:
            path: Path to JSONL file for receipt storage
        """
        self.path = Path(path)
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch file to ensure it exists
        if not self.path.exists():
            self.path.touch()

    def append(self, receipt: dict) -> str:
        """Append receipt to ledger.

        Thread-safe with file locking.

        Args:
            receipt: Receipt dict to append

        Returns:
            receipt_id (the payload_hash)
        """
        receipt_id = receipt.get("payload_hash", "")
        line = json.dumps(receipt, sort_keys=True) + "\n"

        with open(self.path, "a") as f:
            # Acquire exclusive lock for thread safety
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return receipt_id

    def read_all(self) -> list[dict]:
        """Read all receipts from ledger.

        Returns:
            List of receipt dicts
        """
        receipts = []
        if not self.path.exists():
            return receipts

        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    receipts.append(json.loads(line))

        return receipts

    def query(self, predicate: Callable[[dict], bool]) -> list[dict]:
        """Query receipts matching predicate.

        Args:
            predicate: Function that returns True for matching receipts

        Returns:
            List of matching receipt dicts
        """
        return [r for r in self.read_all() if predicate(r)]
