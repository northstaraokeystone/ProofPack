# Web Fallback (CRAG)

ProofPack v3.1 includes a confidence-gated web fallback system implementing the Corrective RAG (CRAG) pattern for augmenting low-confidence syntheses with external knowledge.

## Overview

When internal evidence synthesis produces low confidence, the system can:
1. **Evaluate** - Score the synthesis confidence
2. **Correct** - Reformulate queries and search the web
3. **Merge** - Combine internal and external results

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Synthesis  │────►│   Evaluate   │────►│   Classify   │
│   (Brief)    │     │  Confidence  │     │  CRAG State  │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                     ┌────────────────────────────┼────────────────────────────┐
                     │                            │                            │
                     ▼                            ▼                            ▼
              ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
              │   CORRECT    │           │  AMBIGUOUS   │           │  INCORRECT   │
              │   (>0.8)     │           │  (0.5-0.8)   │           │   (<0.5)     │
              │              │           │              │           │              │
              │  Use as-is   │           │  Augment     │           │  Reformulate │
              │              │           │  with web    │           │  + Replace   │
              └──────────────┘           └──────────────┘           └──────────────┘
```

## Enabling Web Fallback

```python
# config/features.py
FEATURE_FALLBACK_ENABLED = True
FEATURE_FALLBACK_WEB_SEARCH = True      # Enable web search
FEATURE_FALLBACK_AUTO_TRIGGER = False   # Manual trigger only
```

## CRAG Classifications

| Classification | Confidence | Action |
|----------------|------------|--------|
| **CORRECT** | > 0.8 | Use synthesis as-is |
| **AMBIGUOUS** | 0.5 - 0.8 | Augment with web results |
| **INCORRECT** | < 0.5 | Reformulate query, replace content |

## Confidence Scoring

The `evaluate` module scores synthesis quality based on:

```python
from proofpack.fallback.evaluate import score, Classification

synthesis = {
    "supporting_evidence": [
        {"chunk_id": "c1", "confidence": 0.95},
        {"chunk_id": "c2", "confidence": 0.85}
    ],
    "evidence_count": 10,
    "strength": 0.88,
    "coverage": 0.75
}

classification, confidence = score(synthesis, query="what caused the error?")
# classification: Classification.CORRECT
# confidence: 0.85
```

### Scoring Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Evidence confidence | 0.3 | Average confidence of supporting evidence |
| Evidence count | 0.2 | Number of evidence pieces found |
| Strength | 0.25 | Overall synthesis strength |
| Coverage | 0.15 | Query coverage |
| Gap penalty | -0.1 | Penalty per identified gap |

## Correction Strategies

When classification is AMBIGUOUS or INCORRECT, the `correct` module applies strategies:

### Query Reformulation

```python
from proofpack.fallback.correct import reformulate

reformulations = reformulate("What is the error cause?")
# ["What is the error cause?",
#  "error cause explanation",
#  "why does error occur"]
```

### Query Decomposition

```python
from proofpack.fallback.correct import decompose

sub_queries = decompose("Find the error and fix it")
# ["Find the error", "fix the error"]
```

### Web Search

```python
from proofpack.fallback.correct import with_web

result = with_web(
    query="python connection timeout error",
    max_results=5,
    provider="tavily"
)

print(f"Strategy: {result.strategy}")
print(f"Results: {len(result.web_results)}")
print(f"Time: {result.elapsed_ms}ms")
```

## Web Search Providers

| Provider | API Key Env | Description |
|----------|-------------|-------------|
| `tavily` | `TAVILY_API_KEY` | Primary, AI-optimized |
| `serpapi` | `SERPAPI_KEY` | Google results |
| `brave` | `BRAVE_SEARCH_KEY` | Privacy-focused |
| `mock` | (none) | Testing only |

Configure provider:
```python
# config/features.py
FALLBACK_WEB_PROVIDER = "tavily"
FALLBACK_WEB_MAX_RESULTS = 5
FALLBACK_WEB_TIMEOUT_MS = 3000
```

## Merge Strategies

The `merge` module combines internal and external results:

### AUGMENT

Add web results to existing synthesis. Used when internal confidence is moderate.

```python
from proofpack.fallback.merge import combine, MergeStrategy

result = combine(
    synthesis=synthesis,
    web_results=web_results,
    strategy=MergeStrategy.AUGMENT,
    confidence_before=0.65
)

print(result.merged_content)
print(f"Confidence: {result.confidence_before} -> {result.confidence_after}")
```

### REPLACE

Replace internal content with web results. Used when confidence is very low.

```python
result = combine(
    synthesis=synthesis,
    web_results=web_results,
    strategy=MergeStrategy.REPLACE,
    confidence_before=0.3
)
```

### INTERLEAVE

Mix internal and external evidence by relevance. Used for balanced augmentation.

```python
result = combine(
    synthesis=synthesis,
    web_results=web_results,
    strategy=MergeStrategy.INTERLEAVE,
    confidence_before=0.6
)
```

### Automatic Strategy Selection

```python
from proofpack.fallback.merge import select_strategy, combine_with_auto_strategy

# Automatic selection based on classification and confidence
strategy = select_strategy(
    classification="AMBIGUOUS",
    confidence=0.65,
    web_result_count=5
)

# Or use the convenience function
result = combine_with_auto_strategy(
    synthesis=synthesis,
    web_results=web_results,
    classification="AMBIGUOUS",
    confidence=0.65
)
```

## Full CRAG Flow

```python
from proofpack.fallback.evaluate import score, Classification
from proofpack.fallback.correct import with_web
from proofpack.fallback.merge import combine_with_auto_strategy

# Step 1: Evaluate
classification, confidence = score(synthesis, query)

# Step 2: Correct (if needed)
if classification != Classification.CORRECT:
    correction = with_web(query, max_results=5)

    # Step 3: Merge
    result = combine_with_auto_strategy(
        synthesis,
        correction.web_results,
        classification.value,
        confidence
    )

    print(f"Confidence improved: {confidence} -> {result.confidence_after}")
```

## Receipt Types

### web_retrieval

Emitted when web search is performed:

```json
{
  "receipt_type": "web_retrieval",
  "ts": "2024-01-15T10:30:00Z",
  "query": "python connection timeout",
  "provider": "tavily",
  "results_count": 5,
  "sources": ["https://..."],
  "content_hashes": ["abc123:def456", "..."],
  "latency_ms": 450,
  "triggered_by": "fallback_auto",
  "classification": "AMBIGUOUS",
  "confidence_before": 0.65
}
```

### merge

Emitted when results are merged:

```json
{
  "receipt_type": "merge",
  "ts": "2024-01-15T10:30:01Z",
  "strategy": "AUGMENT",
  "internal_source_count": 3,
  "web_source_count": 5,
  "confidence_before": 0.65,
  "confidence_after": 0.82,
  "merged_hash": "abc123:def456",
  "tokens_added": 1250
}
```

## CLI Commands

```bash
# Test fallback with a query
proof fallback test "what causes connection timeout" --provider tavily

# View statistics
proof fallback stats

# List available providers
proof fallback sources

# Evaluate a synthesis file
proof fallback evaluate synthesis.json --query "test query"
```

## Configuration

### Thresholds

```python
# config/features.py
FALLBACK_THRESHOLD_CORRECT = 0.8    # Above = CORRECT
FALLBACK_THRESHOLD_AMBIGUOUS = 0.5  # Above = AMBIGUOUS, below = INCORRECT
```

### Web Search Settings

```python
FALLBACK_WEB_PROVIDER = "tavily"
FALLBACK_WEB_MAX_RESULTS = 5
FALLBACK_WEB_TIMEOUT_MS = 3000
FALLBACK_WEB_CACHE_TTL = 300  # 5 minutes
```

### Merge Settings

```python
FALLBACK_MERGE_MAX_TOKENS = 2000
FALLBACK_MERGE_DEDUP = True
FALLBACK_MERGE_CITE_SOURCES = True
```

## Integration with Graph

Fallback operations are recorded in the temporal knowledge graph:

```
[brief] --REVISED_BY--> [corrected_brief]
     \
      --MERGED_WITH--> [web_retrieval]
```

Query merged relationships:
```python
from proofpack.graph.query import match

merges = match({"receipt_type": "merge"})
```

## Integration with MCP

MCP clients can trigger fallback via `check_confidence`:

```json
{
  "tool": "check_confidence",
  "params": {
    "action_proposal": {
      "synthesis": {...},
      "query": "test query"
    }
  }
}
```

Response includes fallback recommendation:
```json
{
  "confidence": 0.55,
  "classification": "AMBIGUOUS",
  "fallback_recommended": true
}
```

## Monitoring

```bash
proof fallback stats
```

Output:
```
Fallback Statistics (last 24h):
  Evaluations: 1,234
  CORRECT: 856 (69%)
  AMBIGUOUS: 312 (25%)
  INCORRECT: 66 (5%)

Web Searches: 378
  Average latency: 425ms
  Cache hit rate: 34%
  Provider: tavily

Merges: 378
  AUGMENT: 312
  REPLACE: 45
  INTERLEAVE: 21
  Avg confidence improvement: +0.18
```

## Best Practices

1. **Start with manual trigger** - Set `FEATURE_FALLBACK_AUTO_TRIGGER = False` until tuned
2. **Use mock provider** for testing - Avoid API costs during development
3. **Monitor confidence improvements** - Track whether fallback is helping
4. **Cache aggressively** - Web results are slow to fetch
5. **Cite sources** - Always attribute web content

## Related Documentation

- [MCP Integration](mcp-integration.md) - Triggering fallback via MCP
- [Temporal Graph](temporal-graph.md) - Tracking merge relationships
- [Architecture](architecture.md) - System overview
