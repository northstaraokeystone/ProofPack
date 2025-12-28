"""Feature flags for ProofPack.

All new features start DISABLED. Deployment sequence:
1. All OFF (shadow mode, log only)
2. GREEN_LEARNERS only (lowest risk)
3. YELLOW_WATCHERS (monitoring without intervention)
4. RED_HELPERS (active problem solving)
5. RECURSIVE_GATING (full depth)
6. TOPOLOGY + GRADUATION (self-improvement loop)

v3.1 additions:
7. PROOF_UNIFIED (module consolidation)
8. GRAPH (temporal knowledge graph)
9. MCP_SERVER (external interface)
10. FALLBACK (CRAG web augmentation)
"""

# =============================================================================
# v3.0 Features
# =============================================================================

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

# =============================================================================
# v3.1 Features - Module Consolidation
# =============================================================================

# Use unified proof.py instead of separate brief/packet/detect modules
FEATURE_PROOF_UNIFIED_ENABLED = False

# =============================================================================
# v3.1 Features - MCP Server
# =============================================================================

# MCP server: expose tools to external clients
FEATURE_MCP_SERVER_ENABLED = False

# Require authentication for MCP clients
FEATURE_MCP_AUTH_REQUIRED = True

# Allow external clients to trigger spawning
FEATURE_MCP_SPAWN_ALLOWED = False

# =============================================================================
# v3.1 Features - Temporal Knowledge Graph
# =============================================================================

# Enable temporal knowledge graph
FEATURE_GRAPH_ENABLED = False

# Auto-add receipts to graph on emit
FEATURE_GRAPH_AUTO_INGEST = False

# Backfill historical receipts to graph
FEATURE_GRAPH_BACKFILL = False

# =============================================================================
# v3.1 Features - Web Fallback (CRAG)
# =============================================================================

# Enable confidence evaluation for CRAG
FEATURE_FALLBACK_ENABLED = False

# Enable web search for low-confidence answers
FEATURE_FALLBACK_WEB_SEARCH = False

# Auto-trigger fallback on low confidence
FEATURE_FALLBACK_AUTO_TRIGGER = False

# =============================================================================
# Deployment Sequence (v3.1)
# =============================================================================
# 1. PROOF_UNIFIED - test consolidation in isolation
# 2. GRAPH_ENABLED - start building graph without affecting main flow
# 3. GRAPH_AUTO_INGEST - receipts flow to graph automatically
# 4. MCP_SERVER_ENABLED - expose tools to external clients
# 5. MCP_SPAWN_ALLOWED - allow external spawning (after confidence in controls)
# 6. FALLBACK_ENABLED - confidence evaluation active
# 7. FALLBACK_WEB_SEARCH - web augmentation live
# 8. FALLBACK_AUTO_TRIGGER - fully automated CRAG loop
