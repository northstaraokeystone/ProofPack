"""Fallback (CRAG) configuration.

Configuration for confidence-gated web fallback using the
Corrective RAG pattern.
"""

# Feature toggle
FALLBACK_ENABLED = False

# Confidence threshold for triggering fallback
FALLBACK_CONFIDENCE_THRESHOLD = 0.8

# Web search provider: "tavily", "serpapi", "brave", or "mock"
FALLBACK_WEB_PROVIDER = "tavily"

# Maximum web results to fetch
FALLBACK_MAX_WEB_RESULTS = 5

# Web search timeout in milliseconds
FALLBACK_WEB_TIMEOUT_MS = 2000

# Merge strategy defaults
FALLBACK_DEFAULT_STRATEGY = "AUGMENT"  # AUGMENT, REPLACE, or INTERLEAVE

# Auto-trigger thresholds
FALLBACK_AUTO_TRIGGER_THRESHOLD = 0.5  # Below this, always trigger
FALLBACK_SKIP_THRESHOLD = 0.9  # Above this, never trigger
