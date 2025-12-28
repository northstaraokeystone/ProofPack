"""Feature flags for ProofPack.

All new features start DISABLED. Deployment sequence:
1. All OFF (shadow mode, log only)
2. GREEN_LEARNERS only (lowest risk)
3. YELLOW_WATCHERS (monitoring without intervention)
4. RED_HELPERS (active problem solving)
5. RECURSIVE_GATING (full depth)
6. TOPOLOGY + GRADUATION (self-improvement loop)
"""

# Gate: pre-execution confidence gating
FEATURE_GATE_ENABLED = False
FEATURE_GATE_YELLOW_ONLY = False  # Enable YELLOW before RED

# Monte Carlo: statistical confidence via simulation
FEATURE_MONTE_CARLO_ENABLED = False

# Wounds: track confidence drops
FEATURE_WOUND_DETECTION_ENABLED = False

# Auto-spawn: spawn helpers when stuck (legacy)
FEATURE_AUTO_SPAWN_ENABLED = False

# Agent Spawning: confidence-triggered agent birthing
FEATURE_AGENT_SPAWNING_ENABLED = False

# GREEN gate learners: capture success patterns
FEATURE_GREEN_LEARNERS_ENABLED = False

# YELLOW gate watchers: monitor execution
FEATURE_YELLOW_WATCHERS_ENABLED = False

# RED gate helpers: active problem solving
FEATURE_RED_HELPERS_ENABLED = False

# Recursive gating: agents have their own gates
FEATURE_RECURSIVE_GATING_ENABLED = False

# Topology classification: OPEN/CLOSED/HYBRID for agents
FEATURE_TOPOLOGY_CLASSIFICATION_ENABLED = False

# Pattern graduation: promote successful agents to permanent patterns
FEATURE_PATTERN_GRADUATION_ENABLED = False

# Sibling coordination: coordinate parallel helpers
FEATURE_SIBLING_COORDINATION_ENABLED = False
