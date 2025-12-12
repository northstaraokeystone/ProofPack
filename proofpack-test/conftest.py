"""Test configuration and fixtures for Monte Carlo simulation harness.

SimConfig: simulation configuration parameters
SimState: simulation state tracking
Fixtures: pytest fixtures for unit and scenario tests
"""
import random
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest


@dataclass
class SimConfig:
    """Simulation configuration parameters."""
    n_cycles: int = 1000
    gap_rate: float = 0.1  # probability per cycle
    resource_budget: float = 1.0  # 0.0-1.0 scale
    random_seed: int = 42  # deterministic
    timeout_seconds: int = 300


@dataclass
class SimState:
    """Simulation state tracking."""
    cycle: int = 0
    active_helpers: list[dict] = field(default_factory=list)
    gap_history: list[dict] = field(default_factory=list)
    receipt_ledger: list[dict] = field(default_factory=list)
    completeness_trace: list[dict] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def checkpoint(self) -> dict:
        """Serialize state for checkpoint/resume."""
        return {
            "cycle": self.cycle,
            "active_helpers": list(self.active_helpers),
            "gap_history": list(self.gap_history),
            "receipt_ledger": list(self.receipt_ledger),
            "completeness_trace": list(self.completeness_trace),
            "violations": list(self.violations)
        }

    @classmethod
    def from_checkpoint(cls, data: dict) -> "SimState":
        """Restore state from checkpoint."""
        return cls(
            cycle=data["cycle"],
            active_helpers=data["active_helpers"],
            gap_history=data["gap_history"],
            receipt_ledger=data["receipt_ledger"],
            completeness_trace=data["completeness_trace"],
            violations=data["violations"]
        )


@pytest.fixture
def sim_config() -> SimConfig:
    """Provide default SimConfig."""
    return SimConfig()


@pytest.fixture
def sim_state() -> SimState:
    """Provide fresh SimState."""
    return SimState()


@pytest.fixture
def mock_ledger() -> MagicMock:
    """Mock ledger for unit tests."""
    ledger = MagicMock()
    ledger.ingest.return_value = {"receipt_type": "ingest", "ts": 0.0}
    ledger.anchor.return_value = {"receipt_type": "anchor", "merkle_root": "abc123"}
    ledger.verify.return_value = True
    ledger.compact.return_value = {"receipt_type": "compaction", "counts": {"before": 10, "after": 5}}
    return ledger


@pytest.fixture
def mock_loop() -> MagicMock:
    """Mock loop for scenarios."""
    loop = MagicMock()
    loop.run_cycle.return_value = ({"receipt_type": "cycle"}, None)
    loop.harvest.return_value = ({"receipt_type": "harvest"}, {})
    loop.genesis.return_value = (None, {"receipt_type": "genesis_check"})
    loop.effectiveness.return_value = {"receipt_type": "effectiveness"}
    loop.gate.return_value = (None, {"receipt_type": "approval"})
    loop.completeness.return_value = (None, {"receipt_type": "completeness"})
    return loop


@pytest.fixture(autouse=True)
def seed_random(sim_config: SimConfig):
    """Seed random for deterministic tests."""
    random.seed(sim_config.random_seed)
