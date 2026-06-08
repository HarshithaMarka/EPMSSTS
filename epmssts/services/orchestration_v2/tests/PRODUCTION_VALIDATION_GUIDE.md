# EPMSSTS Production Hardening & Reliability Validation Phase

## Overview

The Production Hardening & Reliability Validation Phase is a comprehensive, **automated 8-phase systematic validation** that ensures EPMSSTS is production-ready before deployment.

This is **not** feature expansion. This is structured **system validation under realistic load and fault conditions**.

---

## Validation Phases

### Phase 1: SLA & Latency Validation
**Objective:** Validate SLA enforcement and measure latency characteristics across load profiles.

**Scenarios:**
- 10 concurrent requests
- 50 concurrent requests  
- STT slowdown (300ms injected)
- TTS slowdown (400ms injected)

**Measures:**
- Latency percentiles (p50, p95, p99)
- Per-stage latency breakdown
- SLA breach rate (%)
- Degraded response rate (%)
- Retry frequency

**Pass Criteria:**
- p99 latency ≤ 5000ms
- Degradation rate ≤ 10%
- SLA breach rate ≤ 5%

---

### Phase 2: Failure Isolation Testing
**Objective:** Verify circuit breaker activation and failure containment.

**Scenarios Simulated:**
- STT crash
- Emotion model failure
- Translation timeout  
- TTS synthesis failure
- Redis outage
- GPU unavailability

**Validates:**
- Circuit breaker activates correctly
- Fallback chain executes (no cascade)
- API remains responsive
- Proper degraded status returned
- No sensitive error leakage

**Pass Criteria:**
- Zero cascade failures across 6 scenarios
- All APIs respond within 1s timeout
- All return proper status (success/degraded/failed)

---

### Phase 3: Confidence Propagation Audit
**Objective:** Validate confidence aggregation formula and uncertainty flag logic.

**Test Scenarios:**
1. **Normal Confidence:** All stages 0.85+ → system_confidence high, no uncertainty
2. **Low STT Confidence:** stt=0.45 → system_confidence reduced, uncertainty=TRUE
3. **High Emotion Entropy:** emotion_entropy=0.8 → prosody reduced, uncertainty=TRUE
4. **Weakest Link Test:** translation=0.5 → system_confidence=0.69, reflects weakness

**Validates:**
- Confidence formula: 0.35×stt + 0.15×emotion + 0.30×translation + 0.20×tts
- Uncertainty threshold: system_confidence < 0.55 → flag=TRUE
- Weakest stage correctly identified
- Entropy properly reduces prosody strength

**Pass Criteria:**
- All confidence calculations match expected values ±0.02
- Uncertainty flag set appropriately
- Weakest stage always identified correctly

---

### Phase 4: Observability & Metrics Audit
**Objective:** Verify metrics collection, drift detection, and alert conditions.

**Validates:**
- Prometheus metrics exported correctly
- Stage latency histogram tracks all stages
- Drift detection counters increment
- Emotion distribution monitored
- SLA breach counter accurate
- Neutral emotion drift detection working

**Drift Detection:**
- Target: <20% neutral emotion responses
- Alert trigger: >20% neutral indicates potential model degradation

**Pass Criteria:**
- All metrics present and accurate
- Drift detector activates when neutral >20%
- No missing or stale metrics

---

### Phase 5: Concurrency & Memory Test
**Objective:** Validate concurrent request handling and resource limits.

**Load Test:**
- 100 parallel async requests
- GPU memory tracking
- Deadlock detection
- Semaphore control validation

**Measures:**
- Success rate (target: ≥95%)
- Memory increase (limit: <500MB)
- GPU memory usage (limit: <4000MB)
- No blocking or deadlocks

**Pass Criteria:**
- 95+ requests succeed from 100 concurrent
- Memory increase <500MB
- GPU memory <4000MB
- Zero deadlocks detected

---

### Phase 6: Security Validation
**Objective:** Verify security guards and rejection logic.

**Security Tests:**
1. **Invalid JWT** → 401 Unauthorized (if enabled)
2. **Missing JWT** → Allowed (if optional)
3. **Oversized Payload (>12MB)** → 413 Payload Too Large
4. **Rate Limit Burst** → 429 Too Many Requests
5. **Malformed Audio** → 400 Bad Request
6. **SQL/JSON Injection in Transcript** → Sanitized, no leakage

**Pass Criteria:**
- All malicious requests rejected appropriately
- No server crashes
- No sensitive info leaked in error responses
- Security headers present

---

### Phase 7: Redis Fallback Test
**Objective:** Validate graceful degradation when Redis unavailable.

**Sequence:**
1. Verify normal Redis operation and trace storage
2. Simulate Redis outage → activate local fallback
3. Store 10 traces in fallback (memory)
4. Retrieve traces successfully from fallback
5. Re-enable Redis
6. Synchronize all traces back to Redis

**Pass Criteria:**
- Zero data loss during outage
- Traces accessible from fallback
- Sync completes without errors
- No API downtime

---

### Phase 8: Production Readiness Score
**Objective:** Compute final production readiness score and deployment recommendation.

**Scoring Breakdown (100 total):**
- **SLA Compliance** (20 pts): p99 latency, breach rate
- **Failure Isolation** (20 pts): No cascades, proper fallbacks
- **Confidence Calibration** (15 pts): Formula accuracy, entropy handling
- **Drift Resilience** (15 pts): Drift detection accuracy, alert activation
- **Concurrency Stability** (15 pts): High load handling, no deadlocks
- **Security Hardening** (15 pts): All guards active, no exploits

**Deployment Recommendations:**
- **≥90:** ✅ **Staged Rollout** - Ready for production (10% → 50% → 100%)
- **70-89:** ⚠️ **Pilot Only** - Deploy to limited environment, address medium issues
- **<70:** ❌ **Not Ready** - Critical issues must be resolved before any deployment

---

## Running the Validation Suite

### Option 1: Quick Start (All-in-One)
```bash
# Run complete validation suite
python -m pytest epmssts/services/orchestration_v2/tests/master_orchestration.py -v -s

# Or directly:
python epmssts/services/orchestration_v2/tests/master_orchestration.py
```

### Option 2: Individual Phases
```bash
# Run only systematic 8-phase validation
python epmssts/services/orchestration_v2/tests/production_harness.py

# Run only live endpoint testing (requires running server)
python epmssts/services/orchestration_v2/tests/live_endpoint_harness.py

# Run master orchestration
python epmssts/services/orchestration_v2/tests/master_orchestration.py
```

### Option 3: From Terminal

```powershell
# Activate virtual environment
& .\venv_py310\Scripts\Activate.ps1

# Start FastAPI server (if testing live endpoints)
uvicorn epmssts.api.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal:
python epmssts/services/orchestration_v2/tests/master_orchestration.py
```

---

## Output Files

All validation reports are saved to `./validation_reports/`:

### Systematic Validation
- **`production_audit_[timestamp].json`** - Complete 8-phase audit with all metrics
  - Phase results (status, duration, findings)
  - Key metrics per phase
  - Critical/medium/low issues per phase
  - Score breakdown

### Live Endpoint Testing
- Generated within master orchestration report

### Master Orchestration
- **`master_audit_report_[timestamp].json`** - Aggregated results from both validation types
- **`executive_summary_[timestamp].txt`** - Human-readable summary with deployment decision

---

## Report Structure

### Executive Summary (Text)
Shows:
- Production readiness score (0-100)
- Deployment recommendation
- All critical/medium issues
- Next steps and actions

Example:
```
EXECUTIVE SUMMARY

Production Readiness Score: 92/100
Deployment Recommendation: STAGED_ROLLOUT

Phases Completed:
  └─ Phase 1: SLA & Latency Validation          [PASS]
  └─ Phase 2: Failure Isolation Testing         [PASS]
  └─ Phase 3: Confidence Propagation Audit      [WARN]
  └─ Phase 4: Observability & Metrics Audit     [PASS]
  └─ Phase 5: Concurrency & Memory Test         [PASS]
  └─ Phase 6: Security Validation               [PASS]
  └─ Phase 7: Redis Fallback Test               [PASS]
  └─ Phase 8: Production Readiness Score        [PASS]

Critical Issues: 0
Medium Issues: 1
  ⚠ Emotion confidence occasionally below threshold
```

### Detailed JSON Report
Complete metrics for each phase:
```json
{
  "phase_number": 1,
  "phase_name": "SLA & Latency Validation",
  "status": "PASS",
  "duration_seconds": 15.3,
  "findings": [
    "10 concurrent: p50=145.2ms, p95=385.1ms, p99=412.5ms",
    "50 concurrent: p50=150.3ms, p95=420.2ms, p99=510.3ms"
  ],
  "key_metrics": {
    "concurrent_10": {...},
    "concurrent_50": {...},
    "sla_breach_rate": 2.1,
    "degraded_rate": 3.5,
    "success_rate": 96.4
  }
}
```

---

## Interpreting Results

### Phase Statuses
- **PASS**: All criteria met, no issues
- **WARN**: Criteria mostly met, some medium issues found
- **FAIL**: Critical issues found, phase did not pass

### Score Interpretation
| Score | Status | Action |
|-------|--------|--------|
| 90-100 | 🟢 Ready | Proceed with staged rollout |
| 70-89 | 🟡 Caution | Address medium issues, pilot first |
| <70 | 🔴 Blocked | Fix critical issues, retry validation |

### Common Issues

**Issue:** p99 latency > 5000ms
- **Cause:** Slow downstream service or resource contention
- **Action:** Check STT/TTS service latency, scale horizontally

**Issue:** SLA breach rate > 5%
- **Cause:** Timeouts or service degradation
- **Action:** Review timeout configuration per stage

**Issue:** High degradation rate
- **Cause:** Cascading failures or confidence drops
- **Action:** Verify circuit breaker states, check model accuracy

**Issue:** Memory increase > 500MB under 100 concurrent requests
- **Cause:** Memory leak or inefficient caching
- **Action:** Profile heap, check for dangling references

**Issue:** Drift detection triggered (>20% neutral)
- **Cause:** Emotion model degradation or data shift
- **Action:** Retrain emotion model, investigate new data distribution

---

## Best Practices for Production Use

### Pre-Deployment
1. Run complete validation suite in staging environment
2. Review all critical/medium issues
3. Ensure score ≥90 for staged rollout
4. Get approval from architecture team

### Staged Rollout Strategy
```
Stage 1 (10% traffic):      24-48 hours monitoring
  ↓ (if stable)
Stage 2 (50% traffic):      12-24 hours monitoring  
  ↓ (if stable)
Stage 3 (100% traffic):     Gradual shift
```

### Monitoring During Rollout
- Watch SLA breach rate <5%
- Monitor degradation rate <10%
- Track drift detection triggers
- Alert on circuit breaker activations
- Monitor memory and GPU usage

### Incident Response
If issues detected:
1. Immediately drop traffic back to 10%
2. Investigate issue root cause
3. Fix and re-validate Phase that failed
4. Resume rollout only after score ≥90

---

## Architecture Notes

### Async Execution
- Load testing uses `asyncio` for true parallelism
- No artificial delays inserted
- Real latency measurements from request start to response

### Fallback Validation
- Redis outage test uses local in-memory store
- Validates graceful degradation
- Ensures zero data loss during transitions

### Security Testing
- Tests actual form of security guards
- Verifies rejection codes
- Checks for information leakage in errors

### Confidence Propagation
- Uses real aggregation formula from orchestrator
- Validates uncertainty flag logic
- Tests entropy impact on prosody

---

## Integration with CI/CD

### Add to Pipeline
```yaml
production_validation:
  stage: validate
  script:
    - python epmssts/services/orchestration_v2/tests/master_orchestration.py
  artifacts:
    paths:
      - validation_reports/
    reports:
      json: validation_reports/master_audit_report_*.json
  only:
    - main
  when: manual
```

### Automated Checks
```yaml
# Fail if score < 85
if (json report) production_readiness_score < 85:
  exit 1
```

---

## Troubleshooting

### Tests Won't Run
```bash
# Ensure pytest is installed
pip install pytest pytest-asyncio

# Ensure dependencies installed
pip install -r requirements.txt

# Check Python version (3.10+)
python --version
```

### Live Endpoint Tests Fail
```bash
# Ensure server is running
uvicorn epmssts.api.main:app --reload

# Check server logs for errors
# Verify orchestration_v2 initialized in main.py
```

### Memory Issues
```bash
# Run smaller load test
# Modify phase 5 to use 50 concurrent instead of 100

# Check available system memory
psutil.virtual_memory()
```

### Redis Connection Issues
```bash
# Ensure Redis server running (or verify fallback works)
redis-cli ping

# Check Redis connection in state_store.py logs
```

---

## Performance Baseline

### Expected Latencies (Single Request)
- p50: 120-150ms
- p95: 300-400ms  
- p99: 400-500ms

### Expected Resource Usage
- Memory (idle): ~200MB
- Memory increase (100 concurrent): <500MB
- GPU memory: 2000-3000MB
- CPU (per replica): 30-50%

### Expected Quality Metrics
- Success rate: >95%
- SLA breach rate: <5%
- Degradation rate: <10%
- System confidence: >0.75

---

## Next Steps After Validation

If Validation Passes (≥90 score):
1. ✅ Proceed to staged rollout
2. ✅ Deploy to 10% of traffic
3. ✅ Monitor for 24-48 hours
4. ✅ Gradually increase traffic
5. ✅ Fine-tune based on real metrics

If Validation Requires Improvement (70-89 score):
1. ⚠️ Address medium issues
2. ⚠️ Re-run Phase validation
3. ⚠️ Deploy to pilot environment first
4. ⚠️ Extended monitoring (72+ hours)

If Validation Fails (<70 score):
1. ❌ DO NOT DEPLOY
2. ❌ Fix critical issues
3. ❌ Re-run complete validation
4. ❌ Escalate to engineering

---

## Support & Questions

For questions about validation results:
1. Check executive summary for recommendations
2. Review individual phase findings in JSON report
3. Cross-reference issues with failure mode table
4. Escalate critical issues to engineering team

---

**Last Updated:** March 2, 2026
**EPMSSTS Version:** Production Hardening Phase
**Validation Framework:** 8-Phase Systematic + Live Endpoint Testing
