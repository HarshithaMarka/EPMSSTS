# EPMSSTS Performance Configuration Guide

Quick reference for configuring and optimizing EPMSSTS performance.

---

## Model Selection

### STT (Speech-to-Text)

**Default Behavior:**
- **CPU:** Automatically uses `base` model (fast, good accuracy)
- **GPU:** Uses `large-v3` model (slower, best accuracy)

**Override Options:**

```bash
# Force large-v3 model (higher accuracy, much slower on CPU)
export EPMSSTS_STT_FORCE_LARGE=1

# Default behavior (auto-select based on device)
export EPMSSTS_STT_FORCE_LARGE=0
```

**Model Comparison:**

| Model | Size | CPU Latency | GPU Latency | WER | Use Case |
|-------|------|-------------|-------------|-----|----------|
| base | 142MB | ~1.0s | ~0.2s | 15-20% | **Default** - Fast, good enough |
| large-v3 | 2.87GB | ~26s | ~1-2s | 10% | High accuracy required |

**Recommendation:**
- Development/Testing: `base` model
- Production (CPU): `base` model
- Production (GPU): Can use `large-v3` if accuracy critical

---

## Performance Tuning

### Current Performance (CPU)

```
Audio Duration: 2s
Total Latency: 2.4s
Breakdown:
  - STT: 1.0s
  - Emotion: 0.8s
  - Translation: 0.9s
  - TTS: 0.005s
```

### With GPU (Projected)

```
Audio Duration: 2s
Total Latency: 0.5-0.7s (3-5x faster)
Breakdown:
  - STT: 0.2-0.3s
  - Emotion: 0.1-0.15s
  - Translation: 0.15-0.2s
  - TTS: 0.005s
```

---

## Concurrency Settings

### Current Configuration

```python
# epmssts/api/main.py
PIPELINE_MAX_CONCURRENCY = 1  # Serialize requests
PIPELINE_QUEUE_TIMEOUT = 2.5  # seconds
PIPELINE_TIMEOUT = 120  # seconds
```

### Recommended Settings by Load

**Low Load (1-3 users):**
```bash
EPMSSTS_PIPELINE_MAX_CONCURRENCY=1
EPMSSTS_PIPELINE_QUEUE_TIMEOUT=2.5
EPMSSTS_PIPELINE_TIMEOUT=120
```

**Medium Load (3-10 users) - Requires GPU:**
```bash
EPMSSTS_PIPELINE_MAX_CONCURRENCY=3
EPMSSTS_PIPELINE_QUEUE_TIMEOUT=5.0
EPMSSTS_PIPELINE_TIMEOUT=60
```

**High Load (10+ users) - Requires GPU + Horizontal Scaling:**
```bash
EPMSSTS_PIPELINE_MAX_CONCURRENCY=5
EPMSSTS_PIPELINE_QUEUE_TIMEOUT=10.0
EPMSSTS_PIPELINE_TIMEOUT=60
# + Load balancer + Multiple instances
```

---

## Memory Optimization

### Current Usage

```
Per Request: ~377 MB (peak)
Base Memory: ~1.3 GB (models loaded)
Total: ~1.7 GB peak per process
```

### Recommendations

**Minimum RAM:**
- Development: 4 GB
- Production (single instance): 8 GB
- Production (multiple instances): 8 GB + (2 GB × num_instances)

**GPU VRAM (if using GPU):**
- base model: 2-3 GB
- large-v3 model: 6-8 GB

---

## Device Configuration

### Auto-Detection (Default)

```python
# Automatically detects GPU, falls back to CPU
device = "cuda" if torch.cuda.is_available() else "cpu"
```

### Manual Override

```bash
# Force CPU
export EPMSSTS_DEVICE=cpu

# Force GPU
export EPMSSTS_DEVICE=cuda
```

---

## Quick Start Commands

### Development (Fast)

```bash
# Use base model, CPU
export EPMSSTS_STT_FORCE_LARGE=0
export EPMSSTS_TTS_ENGINE=fallback
uvicorn epmssts.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production (Balanced)

```bash
# Auto-detect device, optimize for production
export EPMSSTS_STT_FORCE_LARGE=0
export EPMSSTS_DEVICE=auto
uvicorn epmssts.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Production (High Accuracy)

```bash
# Use large-v3 model (requires GPU for reasonable speed)
export EPMSSTS_STT_FORCE_LARGE=1
export EPMSSTS_DEVICE=cuda
uvicorn epmssts.api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## Benchmarking

### Run Performance Benchmark

```bash
python performance_benchmark.py
```

### Run Verification Tests

```bash
# Quick verification
python verify_pipeline_simple.py

# Comprehensive verification
python comprehensive_pipeline_verification.py
```

### Check Current Performance

```bash
curl http://localhost:8000/metrics/performance
```

---

## Troubleshooting

### Issue: STT Too Slow (>10s)

**Solution:**
1. Check if using large-v3 on CPU: `echo $EPMSSTS_STT_FORCE_LARGE`
2. If 1, set to 0: `export EPMSSTS_STT_FORCE_LARGE=0`
3. Restart service

### Issue: Empty Transcripts

**Possible Causes:**
1. Audio is actually silent (VAD filtering)
2. Audio quality too low for base model

**Solution:**
```bash
# Try large-v3 model (better with poor audio)
export EPMSSTS_STT_FORCE_LARGE=1
```

### Issue: High Memory Usage

**Solution:**
1. Reduce `EPMSSTS_PIPELINE_MAX_CONCURRENCY` to 1
2. Limit worker processes
3. Enable swap if needed

### Issue: 429 Too Many Requests

**Solution:**
```bash
# Increase queue timeout
export EPMSSTS_PIPELINE_QUEUE_TIMEOUT=10.0

# Or increase concurrency (if GPU available)
export EPMSSTS_PIPELINE_MAX_CONCURRENCY=3
```

---

## Performance Monitoring

### Key Metrics to Monitor

1. **Latency per stage** (from `/metrics` endpoint)
2. **Queue wait time** (429 error rate)
3. **Memory usage** (RSS, peak)
4. **CPU/GPU utilization**
5. **Request throughput** (requests/second)

### Alerts to Configure

```
Latency > 5s: Warning
Latency > 10s: Critical
Memory > 90%: Warning
429 Errors > 10%: Warning
Model load failures: Critical
```

---

## Optimization Checklist

**Before Production:**

- [ ] GPU available? (recommended for >10 users)
- [ ] Set `EPMSSTS_STT_FORCE_LARGE` appropriately
- [ ] Configure concurrency limits
- [ ] Setup monitoring (Prometheus/Grafana)
- [ ] Run load tests
- [ ] Configure alerts
- [ ] Setup auto-scaling (if cloud)
- [ ] Document configuration decisions

**For Best Performance:**

- [ ] Use GPU if available
- [ ] Use base model unless accuracy critical
- [ ] Set `beam_size=1` (already default)
- [ ] Enable VAD filtering (already default)
- [ ] Use int8 quantization on CPU (already default)
- [ ] Implement request queueing
- [ ] Cache common translations (optional)

---

## Environment Variables Reference

```bash
# STT Configuration
EPMSSTS_STT_FORCE_LARGE=0|1  # 0=auto, 1=force large-v3

# Device Selection
EPMSSTS_DEVICE=auto|cpu|cuda  # auto=default

# TTS Engine
EPMSSTS_TTS_ENGINE=auto|coqui|pyttsx3|fallback

# Concurrency
EPMSSTS_PIPELINE_MAX_CONCURRENCY=1
EPMSSTS_PIPELINE_QUEUE_TIMEOUT=2.5
EPMSSTS_PIPELINE_TIMEOUT=120

# Timeouts (seconds)
EPMSSTS_TIMEOUT_STT=60
EPMSSTS_TIMEOUT_EMOTION=10
EPMSSTS_TIMEOUT_TRANSLATION=30
EPMSSTS_TIMEOUT_TTS=10
```

---

## Support

For performance issues or questions:
1. Check logs: `epmssts.log`
2. Run benchmark: `python performance_benchmark.py`
3. Review reports in `outputs/`
4. Refer to [PERFORMANCE_OPTIMIZATION_REPORT.md](PERFORMANCE_OPTIMIZATION_REPORT.md)

**Current Status:** ✅ Optimized to 2.4s (92% improvement from baseline)
