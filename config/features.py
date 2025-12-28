"""Feature flags for ProofPack.

All new features start DISABLED. Deployment sequence:
1. All OFF (shadow mode, log only)
2. YELLOW gate only
3. Full RED gate
4. Monte Carlo
5. Auto-spawn
"""

# Gate: pre-execution confidence gating
FEATURE_GATE_ENABLED = False
FEATURE_GATE_YELLOW_ONLY = False  # Enable YELLOW before RED

# Monte Carlo: statistical confidence via simulation
FEATURE_MONTE_CARLO_ENABLED = False

# Wounds: track confidence drops
FEATURE_WOUND_DETECTION_ENABLED = False

# Auto-spawn: spawn helpers when stuck
FEATURE_AUTO_SPAWN_ENABLED = False
