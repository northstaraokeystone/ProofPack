"""Loop Module - Self-improving meta-layer for ProofPack.

The Loop Module harvests patterns from manual interventions (wounds),
synthesizes automated solutions (helpers), deploys with human approval,
and measures effectiveness. When L4 receipts inform L0 processing,
the system achieves mathematical self-auditing.

Core insight: The loop doesn't just monitor receipts—it IS receipts
about receipts. The meta-layer measures the system's ability to measure itself.
"""

from typing import List

# Cycle timing (QED Build Strategy v7: "Every 60 seconds")
CYCLE_INTERVAL_S: int = 60

# Wound thresholds (ProofPack v3: "≥5 occurrences", "median resolve >30min")
WOUND_THRESHOLD_COUNT: int = 5
WOUND_THRESHOLD_RESOLVE_MS: int = 1800000  # 30min = 1,800,000ms

# Harvest window (ProofPack v3: "past 30 days")
HARVEST_WINDOW_DAYS: int = 30

# Risk thresholds (ProofPack v3)
RISK_LOW: float = 0.2      # <0.2 auto-approve
RISK_HIGH: float = 0.5     # >0.5 requires HITL
RISK_CRITICAL: float = 0.8  # >0.8 two approvals + observation

# Completeness target (ProofPack v3: "L0-L4 coverage ≥99.9%")
COMPLETENESS_TARGET: float = 0.999

# Effectiveness dormancy (ProofPack v3: "zero effectiveness for 30 days")
EFFECTIVENESS_DORMANT_DAYS: int = 30

# HITL timeout (QED v7: "After 14 days, proposals auto-decline")
HITL_TIMEOUT_DAYS: int = 14

# Fitness weights (ProofPack v3 §7.3)
FITNESS_WEIGHTS: dict = {
    "roi": 0.4,
    "diversity": 0.3,
    "stability": 0.2,
    "recency": 0.1,
}

# Protected components - cannot be modified by helpers (ProofPack v3 §7.1)
PROTECTED: List[str] = [
    "loop.cycle",
    "loop.gate",
    "loop.completeness",
    "ledger.anchor",
    "anchor.dual_hash",
]

# Receipt level mapping
RECEIPT_LEVEL_MAP: dict = {
    # L0 - Telemetry
    "qed_window": 0,
    "qed_manifest": 0,
    "qed_batch": 0,
    "ingest": 0,
    # L1 - Agents
    "anomaly": 1,
    "alert": 1,
    "remediation": 1,
    "pattern_match": 1,
    "analysis": 1,
    "actuation": 1,
    # L2 - Decisions
    "brief": 2,
    "packet": 2,
    "attach": 2,
    "consistency": 2,
    # L3 - Quality
    "health": 3,
    "effectiveness": 3,
    "wound": 3,
    "gap": 3,
    "harvest": 3,
    # L4 - Meta (emitted by loop, not queried in sense)
    "loop_cycle": 4,
    "completeness": 4,
    "helper_blueprint": 4,
    "approval": 4,
    "sense": 4,
}

# Expected receipt types per level
EXPECTED_TYPES_BY_LEVEL: dict = {
    0: ["qed_window", "qed_manifest", "qed_batch", "ingest"],
    1: ["anomaly", "alert", "remediation", "pattern_match"],
    2: ["brief", "packet", "attach", "consistency"],
    3: ["health", "effectiveness", "wound", "gap"],
    4: ["loop_cycle", "completeness", "helper_blueprint", "approval"],
}

# Public API exports
from proofpack.loop.cycle import run_cycle, start_loop  # noqa: E402
from proofpack.loop.completeness import measure_completeness  # noqa: E402
from proofpack.loop.harvest import harvest_wounds  # noqa: E402
from proofpack.loop.entropy import system_entropy, agent_fitness  # noqa: E402

__all__ = [
    # Constants
    "CYCLE_INTERVAL_S",
    "WOUND_THRESHOLD_COUNT",
    "WOUND_THRESHOLD_RESOLVE_MS",
    "HARVEST_WINDOW_DAYS",
    "RISK_LOW",
    "RISK_HIGH",
    "RISK_CRITICAL",
    "COMPLETENESS_TARGET",
    "EFFECTIVENESS_DORMANT_DAYS",
    "HITL_TIMEOUT_DAYS",
    "FITNESS_WEIGHTS",
    "PROTECTED",
    "RECEIPT_LEVEL_MAP",
    "EXPECTED_TYPES_BY_LEVEL",
    # Functions
    "run_cycle",
    "start_loop",
    "measure_completeness",
    "harvest_wounds",
    "system_entropy",
    "agent_fitness",
]
