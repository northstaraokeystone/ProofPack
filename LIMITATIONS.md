# ProofPack Known Limitations

**Last Updated:** 2025-01-01
**Version:** v3.3
**Status:** Research-Grade Proof-of-Concept

This document honestly describes ProofPack's current limitations. Enterprise hardening planned for Q2 2025 post-seed funding.

---

## Production Blockers (CRITICAL)

These gaps prevent enterprise deployment:

### L1: No Automated CI/CD (CRITICAL)
**Gap:** No GitHub Actions, no automated testing on PR
**Impact:** Manual verification required before merge
**Workaround:** Run `pytest tests/` locally before merge
**Fix ETA:** Q1 2025 (2-week effort post-seed)

### L2: Test Coverage (MEDIUM - Improved)
**Gap:** Compliance tests cover principles; unit test coverage improving
**Impact:** Cannot verify all behavior changes don't break functionality
**Workaround:** Manual testing + compliance suite + Monte Carlo scenarios
**Progress:** Added Monte Carlo scenarios for WORKFLOW, SANDBOX, INFERENCE, PLAN_APPROVAL
**Fix ETA:** Q2 2025 (target 80%+ coverage)

### L3: No Monitoring/Observability (HIGH)
**Gap:** No Prometheus metrics, no Datadog integration, no alerting
**Impact:** Cannot detect production issues proactively
**Workaround:** Manual log inspection, receipt stream analysis
**Fix ETA:** Q2 2025

### L4: No Deployment Automation (MEDIUM)
**Gap:** No Docker, no Kubernetes manifests, no config management
**Impact:** Manual deployment prone to errors
**Workaround:** Deployment runbook (manual steps)
**Fix ETA:** Q1 2025

---

## Security Gaps (HIGH)

**No formal security audit completed.**

Known areas needing review:
- No penetration testing
- No dependency vulnerability scanning (Dependabot not configured)
- No secrets management (environment variables used directly)
- No rate limiting on API endpoints
- No authentication/authorization framework

**Workaround:** Internal use only, no public-facing API
**Fix ETA:** Q2 2025 (requires security audit)

---

## Architecture Gaps (MEDIUM)

### Parent Hash Chaining
**Gap:** Infrastructure exists but not all receipts chain parent_hash field
**Impact:** Full lineage tracing requires code updates
**Location:** `proofpack/ledger/query.py:trace_lineage()`
**Workaround:** Merkle roots provide batch verification
**Fix ETA:** Q1 2025

### Gate Shell Scripts
**Gap:** Timeline gates (gate_t2h.sh, gate_t24h.sh, gate_t48h.sh) not as standalone scripts
**Impact:** Gate enforcement is in Python, not easily scriptable
**Location:** `gate/` module
**Workaround:** Python gate module + Plan Proposal module provides equivalent functionality
**Fix ETA:** Q1 2025

### Entropy-StopRule Integration
**Gap:** Entropy violations tracked but may not trigger StopRule directly
**Impact:** Thermodynamic governance not fully enforced
**Location:** `proofpack/loop/entropy.py`
**Workaround:** entropy_conservation() returns validity; calling code must check
**Fix ETA:** Q1 2025

---

## Enterprise Integration (NEW - Implemented)

The following enterprise features have been added in v3.3:

### Workflow Visibility (CLAUDEME §12) [IMPLEMENTED]
- 7-node DAG execution graph with deviation detection
- HALT on unauthorized deviations
- Location: `proofpack/src/workflow/`, `proofpack/workflow_graph.json`

### Sandbox Execution (CLAUDEME §13) [IMPLEMENTED]
- Docker-isolated tool execution
- Network allowlist for government APIs
- Location: `proofpack/src/sandbox/`, `proofpack/config/allowlist.json`

### Inference Tracking (CLAUDEME §14) [IMPLEMENTED]
- Model version hashing and tampering detection
- Inference receipt emission
- Location: `proofpack/src/inference/`

### Plan Proposal (HITL) [IMPLEMENTED]
- Human-in-the-loop approval workflow
- Risk levels: CRITICAL, HIGH, MEDIUM, LOW
- Location: `proofpack/src/gate/plan_proposal.py`

### META-LOOP Integration [IMPLEMENTED]
- PLAN_PROPOSAL phase added between GATE and ACTUATE
- Location: `proofpack/loop/cycle.py`

---

## Scalability Limitations (MEDIUM)

**Not tested beyond:**
- 10,000 receipts per run
- Single-machine deployment
- 1GB receipt ledgers

**Known bottlenecks:**
- Receipt parsing (Python JSONL, not streaming)
- Merkle computation (O(n log n) in-memory)
- No horizontal scaling support

**Workaround:** Sufficient for proof-of-concept validation
**Fix ETA:** Q3 2025 (if needed based on pilot requirements)

---

## Documentation Gaps (LOW)

**Missing:**
- API documentation (no OpenAPI/Swagger)
- Architecture decision records (ADRs)
- Performance benchmarks documentation
- Troubleshooting guide
- Deployment guide

**Workaround:** Code comments + README
**Fix ETA:** Ongoing

---

## What These Limitations Mean

**For Researchers:** ProofPack validates receipts-native thesis. Limitations are acceptable at research stage.

**For Investors:** Gaps are standard for seed-stage category creators. Enterprise hardening post-funding.

**For Enterprise Buyers:** Not ready for production deployment. Pilot-ready with support.

**For Contributors:** High-impact areas to contribute (see ROADMAP.md).

---

## Transparency Commitment

This document updated with each release. All gaps public.

**No surprises. No hidden issues. No fake perfection.**

If you find a limitation not listed here, please open an issue.

---

## See Also

- [ROADMAP.md](ROADMAP.md) - Path to fixing these limitations
- [COMPLIANCE_REPORT.md](compliance/COMPLIANCE_REPORT.md) - What does work
- [CLAIMS_VERIFICATION.md](docs/CLAIMS_VERIFICATION.md) - Verify current capabilities
