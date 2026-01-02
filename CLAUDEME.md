# CLAUDEME v3.1 — Self-Describing Execution Standard

```json
{
  "glyph_type": "anchor",
  "id": "claudeme-v3.1",
  "ts": "2024-01-01T00:00:00Z",
  "purpose": "This document IS an AnchorGlyph. It describes itself.",
  "hash": "COMPUTE_ON_READ",
  "verification": "If you can read this, the standard is active."
}
```

> **Read top-to-bottom. Type code. Ship.**
>
> Every statement is a schema, signature, assertion, or gate.
> No prose survives. No exceptions.

---

# §0 LAWS (3)

```python
LAW_1 = "No receipt → not real"
LAW_2 = "No test → not shipped"
LAW_3 = "No gate → not alive"
```

These three statements govern all that follows.

---

# §1 THE PIPELINE

```
┌─────────┐    ┌────────────┐    ┌───────────┐    ┌────────┐    ┌────────────┐
│  INPUT  │───▶│ PROVENANCE │───▶│ REASONING │───▶│ FUSION │───▶│   OUTPUT   │
│  bytes  │    │  ingest_r  │    │ routing_r │    │ verify │    │ AnchorGlyph│
└─────────┘    │  anchor_r  │    │    dh_r   │    │ attach │    └────────────┘
               └────────────┘    └───────────┘    └────────┘
```

Your code fits ONE place. Know where before you type.

---

# §2 THE STACK

```python
# LANGUAGES - choose ONE per file
LANG = {
    "hotpath": "Rust",      # crypto, streaming
    "cli":     "TypeScript", # adapters
    "offline": "Python",    # research, NEVER hotpath
    "ops":     "Shell"      # runbooks
}

# STORAGE - no alternatives
STORE = {
    "state":   "PostgreSQL",
    "vectors": "pgvector",   # or FAISS, hash(id)%N
    "queues":  "RabbitMQ",   # or NATS, NEVER Redis for audit
    "blobs":   "S3"
}

# CRYPTO - no alternatives
HASH = "SHA256 + BLAKE3"  # ALWAYS dual-hash
MERKLE = "BLAKE3"         # tree algorithm
```

---

# §3 TIMELINE GATES

## Gate T+2h: SKELETON
```bash
#!/bin/bash
# gate_t2h.sh - RUN THIS OR KILL PROJECT
[ -f spec.md ]            || { echo "FAIL: no spec"; exit 1; }
[ -f ledger_schema.json ] || { echo "FAIL: no schema"; exit 1; }
[ -f cli.py ]             || { echo "FAIL: no cli"; exit 1; }
python cli.py --test 2>&1 | grep -q '"receipt_type"' || { echo "FAIL: no receipt"; exit 1; }
echo "PASS: T+2h gate"
```

**Required files:**
```
spec.md              # inputs, outputs, receipts, SLOs, stoprules, rollback
ledger_schema.json   # {"hash_strategy": {"algorithm": ["SHA256","BLAKE3"]}}
cli.py               # emits valid receipt JSON to stdout
```

## Gate T+24h: MVP
```bash
#!/bin/bash
# gate_t24h.sh - RUN THIS OR KILL PROJECT
python -m pytest tests/ -q       || { echo "FAIL: tests"; exit 1; }
grep -rq "emit_receipt" src/*.py || { echo "FAIL: no receipts in src"; exit 1; }
grep -rq "assert" tests/*.py     || { echo "FAIL: no assertions"; exit 1; }
echo "PASS: T+24h gate"
```

**Required:**
- Pipeline runs: ingest → process → emit
- Tests exist with receipt verification
- SLO assertions present

## Gate T+48h: HARDENED
```bash
#!/bin/bash
# gate_t48h.sh - RUN THIS OR KILL PROJECT
grep -rq "anomaly" src/*.py      || { echo "FAIL: no anomaly detection"; exit 1; }
grep -rq "bias" src/*.py         || { echo "FAIL: no bias check"; exit 1; }
grep -rq "stoprule" src/*.py     || { echo "FAIL: no stoprules"; exit 1; }
python watchdog.py --check       || { echo "FAIL: watchdog unhealthy"; exit 1; }
echo "PASS: T+48h gate — SHIP IT"
```

**Required:**
- Anomaly detection active
- Bias checks with disparity < 0.5%
- Stoprules on all error paths
- Watchdog daemon healthy

---

# §4 RECEIPT BLOCKS

> **Pattern:** Every receipt type = SCHEMA + EMIT + TEST + STOPRULE

## 4.1 ingest_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "ingest",
    "ts": "ISO8601",
    "tenant_id": "str",      # REQUIRED ON EVERY RECEIPT
    "payload_hash": "str",   # SHA256:BLAKE3 format
    "redactions": ["str"],
    "source_type": "str"
}

# --- EMIT ---
def ingest(payload: bytes, tenant_id: str, source: str) -> dict:
    return emit_receipt("ingest", {
        "tenant_id": tenant_id,
        "payload_hash": dual_hash(payload),
        "redactions": [],
        "source_type": source
    })

# --- TEST ---
def test_ingest_slo():
    t0 = time.time()
    r = ingest(b"x", "t", "test")
    assert (time.time()-t0)*1000 <= 50, "Latency > 50ms"
    assert "tenant_id" in r, "Missing tenant_id"

# --- STOPRULE ---
def stoprule_ingest(e): 
    emit_receipt("anomaly", {"metric":"ingest","delta":-1,"action":"halt"})
    raise StopRule(f"Ingest failed: {e}")
```

## 4.2 anchor_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "anchor",
    "merkle_root": "hex",
    "hash_algos": ["SHA256", "BLAKE3"],
    "batch_size": "int",
    "proof_path": "str|null"
}

# --- EMIT ---
def anchor(receipts: list) -> dict:
    return emit_receipt("anchor", {
        "merkle_root": merkle(receipts),
        "hash_algos": ["SHA256", "BLAKE3"],
        "batch_size": len(receipts)
    })

# --- TEST ---
def test_anchor_integrity():
    rs = [emit_receipt("ingest",{"tenant_id":"t"}) for _ in range(10)]
    a = anchor(rs)
    assert a["merkle_root"] == merkle(rs), "Root mismatch"

# --- STOPRULE ---
def stoprule_anchor_mismatch(exp, act):
    emit_receipt("anomaly", {"metric":"merkle","delta":-1,"action":"halt"})
    rehydrate()
    raise StopRule(f"Merkle: {exp} != {act}")
```

## 4.3 routing_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "routing",
    "query_complexity": "atomic|focused|broad|comparative",
    "chosen_index_level": "sentence|chunk|section",
    "k": "int",
    "budget": {"tokens": "int", "ms": "int"},
    "reason": "str"
}

# --- EMIT ---
def route(query: str, budget: dict) -> tuple:
    cx = classify(query)
    lvl = select_index(cx)
    k = min(budget["tokens"]//100, 50)
    r = emit_receipt("routing", {
        "query_complexity": cx,
        "chosen_index_level": lvl,
        "k": k,
        "budget": budget,
        "reason": f"{cx}→{lvl}→k={k}"
    })
    return (lvl, k), r

# --- TEST ---
def test_routing_budget():
    (_, k), r = route("test", {"tokens":500,"ms":100})
    assert k <= 5, f"k={k} exceeds budget"

# --- STOPRULE ---
def stoprule_budget(actual, limit):
    emit_receipt("anomaly", {"metric":"budget","delta":actual-limit,"action":"reject"})
    raise StopRule(f"Budget: {actual} > {limit}")
```

## 4.4 bias_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "bias",
    "groups": ["str"],
    "disparity": "float 0-1",
    "thresholds": {"max_disparity": 0.005},
    "mitigation_action": "none|rebalance|halt"
}

# --- EMIT ---
def check_bias(groups: list, outcomes: list) -> dict:
    d = disparity(groups, outcomes)
    action = "halt" if d >= 0.005 else "none"
    r = emit_receipt("bias", {
        "groups": groups, "disparity": d,
        "thresholds": {"max_disparity": 0.005},
        "mitigation_action": action
    })
    if action == "halt": stoprule_bias(d)
    return r

# --- TEST ---
def test_bias_slo():
    r = check_bias(["A","B"], [0.5, 0.5])
    assert r["disparity"] < 0.005, f"Disparity {r['disparity']} >= 0.5%"

# --- STOPRULE ---
def stoprule_bias(d):
    emit_receipt("anomaly", {"metric":"bias","delta":d-0.005,"action":"halt"})
    page_human()
    raise StopRule(f"Bias: {d} >= 0.5%")
```

## 4.5 dh_receipt (decision_health)
```python
# --- SCHEMA ---
{
    "receipt_type": "decision_health",
    "strength": "float 0-1",
    "coverage": "float 0-1",
    "efficiency": "float",
    "thresholds": {"min_strength": "float"},
    "policy_diffs": ["str"]
}

# --- EMIT ---
def score(evidence: list, thresh: dict) -> dict:
    s, c, e = strength(evidence), coverage(evidence), efficiency(evidence)
    r = emit_receipt("decision_health", {
        "strength": s, "coverage": c, "efficiency": e,
        "thresholds": thresh, "policy_diffs": []
    })
    if s < thresh.get("min_strength", 0.8): stoprule_weak(s)
    return r

# --- TEST ---
def test_dh_slo():
    r = score([{"s":0.9}], {"min_strength":0.8})
    assert r["strength"] >= 0.8

# --- STOPRULE ---
def stoprule_weak(s):
    emit_receipt("anomaly", {"metric":"strength","delta":s-0.8,"action":"escalate"})
    raise StopRule(f"Weak: {s} < 0.8")
```

## 4.6 impact_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "impact",
    "pre_metrics": {"latency_p95_ms": "int", "error_rate": "float"},
    "post_metrics": {"latency_p95_ms": "int", "error_rate": "float"},
    "cost": {"compute": "float", "storage": "float"},
    "VIH_decision": "approve|reject|shadow"
}

# --- EMIT ---
def impact(pre: dict, post: dict, cost: dict) -> dict:
    inf = post["latency_p95_ms"] / pre["latency_p95_ms"]
    dec = "approve" if inf <= 1.2 else "reject"
    r = emit_receipt("impact", {
        "pre_metrics": pre, "post_metrics": post,
        "cost": cost, "VIH_decision": dec
    })
    if dec == "reject": stoprule_inflation(inf)
    return r

# --- TEST ---
def test_impact_slo():
    r = impact({"latency_p95_ms":100,"error_rate":0.01},
               {"latency_p95_ms":110,"error_rate":0.01}, {})
    assert r["VIH_decision"] == "approve"

# --- STOPRULE ---
def stoprule_inflation(i):
    emit_receipt("anomaly", {"metric":"inflation","delta":i-1.2,"action":"reject"})
    raise StopRule(f"Inflation: {i} > 1.2x")
```

## 4.7 anomaly_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "anomaly",
    "metric": "str",
    "baseline": "float",
    "delta": "float",
    "classification": "drift|degradation|violation|deviation|anti_pattern",
    "action": "alert|escalate|halt|auto_fix"
}

# --- EMIT --- (used by all stoprules)
def emit_anomaly(metric: str, baseline: float, delta: float, 
                 classification: str, action: str) -> dict:
    return emit_receipt("anomaly", {
        "metric": metric, "baseline": baseline, "delta": delta,
        "classification": classification, "action": action
    })
```

## 4.8 compaction_receipt
```python
# --- SCHEMA ---
{
    "receipt_type": "compaction",
    "input_span": {"start": "ISO8601", "end": "ISO8601"},
    "output_span": {"start": "ISO8601", "end": "ISO8601"},
    "counts": {"before": "int", "after": "int"},
    "sums": {"before": "float", "after": "float"},
    "hash_continuity": "bool"
}

# --- EMIT ---
def compact(receipts: list, span: tuple) -> dict:
    before_hash = merkle(receipts)
    compacted = do_compact(receipts)
    after_hash = merkle(compacted)
    return emit_receipt("compaction", {
        "input_span": {"start": span[0], "end": span[1]},
        "output_span": {"start": span[0], "end": span[1]},
        "counts": {"before": len(receipts), "after": len(compacted)},
        "sums": {"before": sum_values(receipts), "after": sum_values(compacted)},
        "hash_continuity": verify_continuity(before_hash, after_hash)
    })
```

---

# §5 GLYPHS (State Objects)

```python
# All glyphs: signed, timestamped, Merkle-addressable

INTENT_GLYPH = {
    "glyph_type": "intent",
    "id": "uuid", "ts": "ISO8601",
    "goal": "str", "constraints": ["str"],
    "risk_bounds": {"max_latency_ms": "int", "max_cost": "float"},
    "ownership": {"creator": "str", "approver": "str|null"},
    "signature": "hex", "merkle_anchor": "hex"
}

EVIDENCE_GLYPH = {
    "glyph_type": "evidence",
    "id": "uuid", "ts": "ISO8601",
    "retrieval_state": {"index_version": "str", "query": "str"},
    "sbsd_params": {"model_hash": "str", "threshold": "float"},
    "entanglement_score": "float 0-1",
    "signature": "hex", "merkle_anchor": "hex"
}

DECISION_GLYPH = {
    "glyph_type": "decision",
    "id": "uuid", "ts": "ISO8601",
    "brief": "str",
    "decision_health": {"strength": "float", "coverage": "float", "efficiency": "float"},
    "dialectical_record": {"pro": [], "con": [], "gaps": []},
    "attached_receipts": ["receipt_hash"],
    "signature": "hex", "merkle_anchor": "hex"
}

ANCHOR_GLYPH = {
    "glyph_type": "anchor",
    "id": "uuid", "ts": "ISO8601",
    "config": {}, "code_hashes": {}, "dataset_hashes": {},
    "receipts_jsonl": "path", "metrics": {}, "slo_deltas": {},
    "signature": "hex", "merkle_anchor": "hex"
}
```

---

# §6 SLO THRESHOLDS

| SLO | Threshold | Test Assertion | Stoprule Action |
|-----|-----------|----------------|-----------------|
| Latency | varies by op | `assert ms <= TARGET` | reject if inflation > 1.2x |
| Entanglement | ≥ 0.92 | `assert score >= 0.92` | escalate |
| Forgetting | < 1% | `assert rate < 0.01` | halt |
| Bias | < 0.5% | `assert disparity < 0.005` | halt + page human |
| Acceptance | ≥ 95% | `assert rate >= 0.95` | rollback |
| Fusion Match | ≥ 99.9% | `assert match >= 0.999` | halt + escalate 4h |

---

# §7 ANTI-PATTERNS (Hard Blocks)

| If you write... | Stop. Write this instead... |
|-----------------|----------------------------|
| Function without `return emit_receipt()` | Add receipt to return |
| `class Agent:` with state | Pure function with ledger I/O |
| `hashlib.sha256()` alone | `dual_hash()` with SHA256+BLAKE3 |
| `except: pass` | `except: stoprule_X(e)` |
| Global variable | Ledger entry |
| `print(result)` | `emit_receipt("...", result)` |
| Test without `assert` | Add SLO assertion |
| File write without receipt | Add storage_receipt |

---

# §8 CORE FUNCTIONS

```python
# === REQUIRED IN EVERY PROJECT ===

import hashlib
import json
from datetime import datetime

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

def dual_hash(data: bytes | str) -> str:
    """SHA256:BLAKE3 - ALWAYS use this, never single hash."""
    if isinstance(data, str):
        data = data.encode()
    sha = hashlib.sha256(data).hexdigest()
    b3 = blake3.blake3(data).hexdigest() if HAS_BLAKE3 else sha
    return f"{sha}:{b3}"

def emit_receipt(receipt_type: str, data: dict) -> dict:
    """Every function calls this. No exceptions."""
    receipt = {
        "receipt_type": receipt_type,
        "ts": datetime.utcnow().isoformat() + "Z",
        "tenant_id": data.get("tenant_id", "default"),
        "payload_hash": dual_hash(json.dumps(data, sort_keys=True)),
        **data
    }
    # Append to ledger (stdout in dev, file in prod)
    print(json.dumps(receipt), flush=True)
    return receipt

class StopRule(Exception):
    """Raised when stoprule triggers. Never catch silently."""
    pass

def merkle(items: list) -> str:
    """Compute Merkle root of items."""
    if not items:
        return dual_hash(b"empty")
    hashes = [dual_hash(json.dumps(i, sort_keys=True)) for i in items]
    while len(hashes) > 1:
        if len(hashes) % 2:
            hashes.append(hashes[-1])
        hashes = [dual_hash(hashes[i] + hashes[i+1]) 
                  for i in range(0, len(hashes), 2)]
    return hashes[0]
```

---

# §9 FILE STRUCTURE

```
ProofPack/
├── core/                 # Receipt primitives (dual_hash, emit_receipt, merkle, StopRule)
├── ledger/               # Receipts storage and anchoring
├── anchor/               # Cryptographic proofs (Merkle trees)
├── detect/               # Pattern finding and anomaly detection
├── loop/                 # Self-improvement layer (META-LOOP)
├── brief/                # Evidence synthesis and decision health
├── packet/               # Claim-to-receipt mapping
├── gate/                 # Pre-execution confidence gating
├── proof.py              # Unified proof interface (BRIEF/PACKET/DETECT)
├── graph/                # Temporal knowledge graph
├── fallback/             # Web fallback for low-confidence queries
├── mcp/                  # MCP server for Claude Desktop integration
├── offline/              # Disconnected operation and local sync
├── privacy.py            # Privacy controls and redaction
├── economic.py           # SLO evaluation and payment triggers
├── spawner/              # Agent lifecycle and graduation
├── monte_carlo/          # Variance reduction via simulation
├── enterprise/           # Enterprise features (workflow, sandbox, inference, gate)
├── config/               # Feature flags and allowlists
├── constants.py          # Shared constants
├── proofpack_cli/        # CLI entry point
├── tests/                # Compliance tests
├── receipts/             # Receipt bundles
└── MANIFEST.anchor       # Deploy artifact (AnchorGlyph)
```

---

# §10 COMMIT FORMAT

```
<type>(<scope>): <description ≤50 chars>

Receipt: <receipt_type>
SLO: <threshold affected | none>
Gate: <t2h | t24h | t48h | post>
```

**Types:** `feat` | `fix` | `refactor` | `test` | `docs`

**Example:**
```
feat(provenance): add compaction with hash continuity

Receipt: compaction_receipt
SLO: none
Gate: t24h
```

---
g
# §11 VALIDATION SCRIPT

```bash
#!/bin/bash
# validate.sh - RUN BEFORE EVERY COMMIT

echo "=== CLAUDEME Compliance Check ==="

# 1. Every .py file has emit_receipt
for f in src/*.py; do
    grep -q "emit_receipt" "$f" || echo "FAIL: $f missing emit_receipt"
done

# 2. Every test has assert
for f in tests/*.py; do
    grep -q "assert" "$f" || echo "FAIL: $f missing assertions"
done

# 3. No single hash
grep -r "sha256\|md5" src/*.py | grep -v "dual_hash" && echo "FAIL: Use dual_hash"

# 4. No silent except
grep -r "except.*pass\|except:$" src/*.py && echo "FAIL: Silent exception"

# 5. No global state
grep -r "^[A-Z_]* = " src/*.py | grep -v "^#" && echo "WARN: Possible global state"

# 6. Tenant ID everywhere
grep -r "emit_receipt" src/*.py | grep -v "tenant_id" && echo "FAIL: Missing tenant_id"

echo "=== Check Complete ==="
```

---

# §12 WORKFLOW VISIBILITY

> **Purpose:** Mandate explicit workflow DAG for every receipts-native system

## Required Schema: `workflow_graph.json`

```python
# --- SCHEMA ---
{
    "nodes": [
        {"id": "str", "type": "str", "function_ref": "str"}
    ],
    "edges": [
        {"from": "str", "to": "str", "condition": "str|null"}
    ],
    "entry_node": "str",
    "exit_nodes": ["str"],
    "graph_hash": "str"  # dual-hash of entire graph structure
}
```

## workflow_receipt

```python
# --- SCHEMA ---
{
    "receipt_type": "workflow",
    "graph_hash": "str",           # dual-hash
    "planned_path": ["str"],       # array of node IDs
    "actual_path": ["str"],        # array of node IDs
    "deviations": [
        {"expected": "str", "actual": "str", "reason": "str"}
    ],
    "payload_hash": "str"          # dual-hash
}

# --- EMIT ---
def emit_workflow_receipt(
    graph_hash: str,
    planned_path: list,
    actual_path: list,
    deviations: list,
    tenant_id: str = "default"
) -> dict:
    return emit_receipt("workflow", {
        "tenant_id": tenant_id,
        "graph_hash": graph_hash,
        "planned_path": planned_path,
        "actual_path": actual_path,
        "deviations": deviations
    })

# --- TEST ---
def test_workflow_receipt_emission():
    r = emit_workflow_receipt("hash:hash", ["a", "b"], ["a", "b"], [])
    assert r["receipt_type"] == "workflow"
    assert r["deviations"] == []

# --- STOPRULE ---
def stoprule_workflow_deviation(expected: str, actual: str, reason: str):
    """HALT if actual_path deviates from planned_path without human approval."""
    emit_receipt("anomaly", {
        "metric": "workflow_deviation",
        "delta": -1,
        "classification": "violation",
        "action": "halt"
    })
    raise StopRule(f"Workflow deviation: expected {expected}, got {actual}. Reason: {reason}")
```

**Constraint:** If actual_path deviates from planned_path without human approval → HALT

---

# §13 SANDBOX REQUIREMENTS

> **Purpose:** Mandate containerized execution for all external tool calls

## Scope

Required for any function that:
- Makes HTTP/HTTPS requests
- Executes shell commands
- Reads external files
- Calls external APIs

## Sandbox Constraints

```python
SANDBOX_CONSTRAINTS = {
    "isolation": "docker_container",
    "network": "config/allowlist.json",  # domains only
    "timeout_default_s": 30,
    "timeout_max_s": 300,
    "resource_limits": {
        "memory_mb": 512,
        "cpu_cores": 1
    }
}
```

## sandbox_execution_receipt

```python
# --- SCHEMA ---
{
    "receipt_type": "sandbox_execution",
    "tool_name": "str",
    "container_id": "str",
    "input_hash": "str",          # dual-hash
    "output_hash": "str",         # dual-hash
    "exit_code": "int",
    "duration_ms": "int",
    "network_calls": [
        {"domain": "str", "allowed": "bool"}
    ],
    "payload_hash": "str"         # dual-hash
}

# --- EMIT ---
def emit_sandbox_receipt(
    tool_name: str,
    container_id: str,
    input_data: bytes,
    output_data: bytes,
    exit_code: int,
    duration_ms: int,
    network_calls: list,
    tenant_id: str = "default"
) -> dict:
    return emit_receipt("sandbox_execution", {
        "tenant_id": tenant_id,
        "tool_name": tool_name,
        "container_id": container_id,
        "input_hash": dual_hash(input_data),
        "output_hash": dual_hash(output_data),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "network_calls": network_calls
    })

# --- TEST ---
def test_sandbox_receipt_emission():
    r = emit_sandbox_receipt("test_tool", "container123", b"in", b"out", 0, 100, [])
    assert r["receipt_type"] == "sandbox_execution"
    assert r["exit_code"] == 0

# --- STOPRULE ---
def stoprule_network_violation(domain: str):
    """HALT if network call to non-allowlisted domain."""
    emit_receipt("anomaly", {
        "metric": "network_violation",
        "delta": -1,
        "classification": "violation",
        "action": "halt"
    })
    raise StopRule(f"Network violation: {domain} not in allowlist")
```

**Constraint:** If network call to non-allowlisted domain → HALT + emit violation

---

# §14 INFERENCE RECEIPTS

> **Purpose:** Mandate receipts at inference boundary for any ML model call

## inference_receipt

```python
# --- SCHEMA ---
{
    "receipt_type": "inference",
    "model_id": "str",
    "model_version": "str",
    "model_hash": "str",          # dual-hash
    "input_hash": "str",          # dual-hash
    "output_hash": "str",         # dual-hash
    "latency_ms": "int",
    "token_count": {
        "input": "int",
        "output": "int"
    },
    "quantization": "str",        # e.g., "fp16", "int8", "none"
    "payload_hash": "str"         # dual-hash
}

# --- EMIT ---
def emit_inference_receipt(
    model_id: str,
    model_version: str,
    model_hash: str,
    input_data: bytes,
    output_data: bytes,
    latency_ms: int,
    token_count: dict | None,
    quantization: str = "none",
    tenant_id: str = "default"
) -> dict:
    return emit_receipt("inference", {
        "tenant_id": tenant_id,
        "model_id": model_id,
        "model_version": model_version,
        "model_hash": model_hash,
        "input_hash": dual_hash(input_data),
        "output_hash": dual_hash(output_data),
        "latency_ms": latency_ms,
        "token_count": token_count or {"input": 0, "output": 0},
        "quantization": quantization
    })

# --- TEST ---
def test_inference_receipt_emission():
    r = emit_inference_receipt(
        "gpt-4", "0613", "hash:hash",
        b"prompt", b"response", 150,
        {"input": 10, "output": 50}, "fp16"
    )
    assert r["receipt_type"] == "inference"
    assert r["model_id"] == "gpt-4"

# --- DECORATOR ---
def receipts_inference(model_id: str, model_version: str):
    """Decorator to wrap inference functions with receipt emission."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            import time
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            emit_inference_receipt(
                model_id, model_version, "COMPUTE_AT_RUNTIME",
                str(args).encode(), str(result).encode(),
                latency_ms, None
            )
            return result
        return wrapper
    return decorator

# --- USAGE ---
# @receipts_inference(model_id="gpt-4", model_version="0613")
# def call_llm(prompt: str) -> str:
#     ...
```

**Constraint:** Every LLM/ML inference call MUST emit inference_receipt. No exceptions.

---

# CHEF'S KISS: This Document IS the Standard

```python
# This CLAUDEME file is itself compliant:
# - It has a schema (the JSON at the top)
# - It emits a receipt (when you read it, you know the version)
# - It has tests (the gate scripts)
# - It has stoprules (the anti-patterns)
# - It ships at T+48h (or gets killed)

# When you internalize this document, you become compliant.
# The receipt is the territory.
# The glyph is the state.
# The ledger is the truth.

assert understand(CLAUDEME) == True, "Re-read from §0"
```

---

**Hash of this document:** `COMPUTE_ON_SAVE`
**Version:** 3.2
**Status:** ACTIVE

*No receipt → not real. Ship at T+48h or kill.*