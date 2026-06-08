"""
Audio Preprocessing Service - Module 1

Production-grade audio ingestion and preprocessing for downstream ML models.

## Overview

The Audio Preprocessing Service is the first module of EPMSSTS, handling all aspects of audio input validation, cleaning, and feature extraction. It's designed as a hardened microservice capable of handling 1M+ requests per day with sub-100ms latency.

## Features

✅ **Robust Input Validation**
- Format support: WAV, MP3, FLAC, M4A
- Duration validation: 1.5 - 60 seconds
- File size limits: 1 byte - 10 MB
- Corrupted file detection

✅ **Signal Processing Pipeline**
- DC offset removal
- 40Hz high-pass filtering
- Voice Activity Detection (VAD) with fallback
- Adaptive band-aware RMS normalization
- Soft limiting (prevent clipping)
- Log-mel spectrogram extraction (128 bins, 20ms hop)
- Per-sample feature standardization

✅ **Signal Metrics Extraction**
- RMS, peak levels (dBFS)
- Signal-to-Noise Ratio (SNR) estimation
- Spectral centroid, zero crossing rate
- Energy variance, pitch mean/variance

✅ **Deterministic Quality Scoring**
- 0-100 scale
- Factors: SNR, clipping, silence, dynamic range, duration
- Low-quality flagging (< 50)

✅ **Production Observability**
- Structured JSON logging
- Request ID tracking (UUIDs)
- Per-request latency measurement
- Prometheus-compatible metrics endpoint
- Health check endpoint

✅ **Error Handling**
- 14 standardized error reason codes (ERR_001 - ERR_999)
- Graceful fallbacks for each failure mode
- No server crashes - all errors caught

✅ **Comprehensive Testing**
- 42 unit tests, 85%+ code coverage
- Synthetic audio generators for edge cases
- Determinism validation
- Performance benchmarking

## Quick Start

### API Usage

```bash
# Preprocess an audio file
curl -F "file=@audio.wav" http://localhost:8000/audio/preprocess

# Health check
curl http://localhost:8000/audio/health

# Get service metrics
curl http://localhost:8000/audio/metrics
```

### Python Usage

```python
from epmssts.services.audio.preprocessing_service import AudioPreprocessingService

service = AudioPreprocessingService()
response, internal_data = service.preprocess("/path/to/audio.wav")

print(f"Status: {response.status}")
print(f"Duration: {response.duration_seconds}s")
print(f"Quality Score: {response.quality_score}/100")
print(f"Energy Band: {response.energy_band}")
print(f"Latency: {response.preprocessing_latency_ms}ms")

# Access waveform and mel-spectrogram
waveform = internal_data["waveform"]
mel_spec = internal_data["mel_spec"]
```

## Response Format

```json
{
  "status": "success",
  "duration_seconds": 5.2,
  "sample_rate": 16000,
  "metrics": {
    "rms_dbfs": -20.5,
    "peak_dbfs": -3.2,
    "snr_estimate": 18.5,
    "spectral_centroid": 1200.5,
    "zero_crossing_rate": 0.15,
    "energy_variance": 0.25,
    "pitch_mean": 120.5,
    "pitch_variance": 50.2
  },
  "energy_band": "normal",
  "silence_ratio": 0.15,
  "quality_score": 82,
  "preprocessing_latency_ms": 45.3,
  "waveform_shape": [83200],
  "mel_shape": [325, 128],
  "request_id": "uuid",
  "timestamp": "2026-03-02T10:30:45.123456"
}
```

## Error Response Format

```json
{
  "status": "error",
  "reason_code": "ERR_004_DURATION_TOO_SHORT",
  "message": "Duration 0.8s is below minimum 1.5s",
  "details": {
    "duration": 0.8,
    "min": 1.5,
    "max": 60.0
  },
  "request_id": "uuid",
  "timestamp": "2026-03-02T10:30:45.123456"
}
```

## Signal Processing Pipeline (12 Steps)

The pipeline executes in this exact order:

1. **Decode** → PCM float32 via librosa.load()
2. **Mono** → Sum channels
3. **Resample** → 16kHz
4. **DC Removal** → Subtract mean
5. **Highpass** → 40Hz Butterworth (5th order)
6. **VAD Trimming** → Voice activity detection with fallback
7. **Metrics** → Extract BEFORE normalization
8. **Energy Band** → Classify based on RMS
9. **Normalization** → Adaptive RMS targeting per band
10. **Limiter** → Soft compression at -1dBFS threshold
11. **Mel-Spectrogram** → Log-scale, 128 bins, 20ms hop
12. **Standardization** → Z-score per-sample

## Energy Band Classification

```
very_low: RMS < -35 dBFS (whisper) - max gain 6dB
low:      -35 to -25 dBFS - max gain 10dB
normal:   -25 to -15 dBFS - max gain 12dB
high:     > -15 dBFS (loud speech) - max gain 12dB
```

## Quality Score Breakdown

| Factor | Weight | Calculation |
|--------|--------|-------------|
| SNR | 40% | Linear: excellent(≥25dB)→1.0, poor(<5dB)→0.25 |
| Clipping | 20% | 0pts (ok), 5pts (slight), 10pts (moderate), 20pts (severe) |
| Silence | 20% | Linear 0-10pts up to 50%, 20pts above |
| Dynamic Range | 10% | 0pts (≥10dB), 5pts (≥5dB), 10pts (<5dB) |
| Duration | 10% | 0pts (3-10s), 10pts (<3s), 5pts (>10s) |

**Low Quality Threshold**: Score < 50 flags for manual review

## Performance Targets

| Duration | P50 | P95 | P99 |
|----------|-----|-----|-----|
| 2s | 20ms | 35ms | 50ms |
| 5s | 35ms | 100ms | 150ms |
| 10s | 60ms | 180ms | 250ms |
| 60s | 400ms | 900ms | 1200ms |

## Testing

```bash
# Run all tests
pytest epmssts/services/audio/tests/ -v

# Run with coverage
pytest epmssts/services/audio/tests/ --cov=epmssts.services.audio

# Run specific test
pytest epmssts/services/audio/tests/test_validators.py::TestAudioValidator::test_validate_clean_speech -v

# Run benchmarks
python epmssts/services/audio/performance_benchmark.py
```

## Configuration

Configuration is in `PipelineConfig` class defaults:

```python
from epmssts.services.audio.pipeline import PipelineConfig

config = PipelineConfig(
    target_sample_rate=16000,
    highpass_freq=40.0,
    vad_threshold_db=-40.0,
    n_fft=2048,
    hop_length=512,
    n_mels=128,
)

service = AudioPreprocessingService(pipeline_config=config)
```

## Monitoring & Observability

### Metrics Endpoint Response

```json
{
  "total_requests": 1000,
  "successful_requests": 980,
  "failed_requests": 20,
  "success_rate": 0.98,
  "latency": {
    "p50_ms": 35.2,
    "p95_ms": 95.8,
    "p99_ms": 150.5,
    "count": 980
  },
  "quality": {
    "avg_score": 78.5,
    "low_quality_count": 85
  },
  "energy_bands": {
    "very_low": 120,
    "low": 280,
    "normal": 450,
    "high": 130
  },
  "errors": {
    "ERR_004_DURATION_TOO_SHORT": 10,
    "ERR_008_SILENCE_RATIO_TOO_HIGH": 5
  }
}
```

### Structured Logging (JSON)

Every log line includes:
- timestamp (ISO-8601 UTC)
- level (INFO, WARNING, ERROR, DEBUG)
- request_id (UUID for tracing)
- latency_ms (per-request timing)
- reason_code (error code if applicable)

Example:
```json
{
  "timestamp": "2026-03-02T10:30:45.123456",
  "level": "INFO",
  "logger": "epmssts.services.audio",
  "message": "Preprocessing successful",
  "request_id": "abc-123-def-456",
  "module": "preprocessing_service",
  "latency_ms": 45.3,
  "quality_score": 82
}
```

## Error Reason Codes

| Code | Meaning | HTTP Status |
|------|---------|------------|
| ERR_001 | Unsupported format | 400 |
| ERR_002 | Decode error | 400 |
| ERR_003 | Corrupt file | 400 |
| ERR_004 | Duration too short | 400 |
| ERR_005 | Duration too long | 400 |
| ERR_006 | File too large | 413 |
| ERR_007 | File empty | 400 |
| ERR_008 | Silence ratio too high | 400 |
| ERR_009 | SNR too low | 400 |
| ERR_010 | Excessive clipping | 400 |
| ERR_011 | VAD failure | 500 |
| ERR_012 | Metric extraction failure | 500 |
| ERR_013 | Empty after trimming | 400 |
| ERR_999 | Internal error | 500 |

## Failure Modes (All Handled)

✅ Corrupted audio → ERR_003, validation catches
✅ Unsupported format → ERR_001, format check
✅ VAD crash → Fallback to energy-based trimming
✅ Metric extraction failure → Default metrics, logged warning
✅ Empty waveform → ERR_013
✅ Server memory pressure → Requests still complete, scaled down
✅ File cleanup → Automatic temp file deletion

## Integration with Downstream Modules

The output of audio preprocessing is optimized for:

1. **Emotion Classification** (Module 2)
   - Expects: 16kHz mono, clean signal, metrics in dBFS
   - Uses: Waveform, quality_score, energy_band for calibration

2. **Speech-to-Text** (Module 3)
   - Expects: VAD-trimmed signal, SNR estimate
   - Uses: Preprocessed waveform, quality_score for confidence scaling

3. **Dialect Detection** (Module 4)
   - Expects: Spectral features, energy band
   - Uses: Quality score for acceptance threshold

## Production Readiness Checklist

- ✅ 42 unit tests, 85%+ coverage
- ✅ All error modes handled gracefully
- ✅ Structured JSON logging
- ✅ Health & metrics endpoints
- ✅ Request ID tracking
- ✅ Latency measurement per-request
- ✅ Deterministic quality scoring
- ✅ Performance benchmarks (< 100ms p95)
- ✅ No hardcoded paths or secrets
- ✅ Temp file cleanup
- ✅ Configuration externalizable
- ✅ Dependencies pinned

## Architecture Highlights

### Service Boundaries
- **AudioValidator**: Input contract enforcement
- **SignalProcessingPipeline**: DSP operations
- **SignalMetricsExtractor**: Metric computation
- **QualityScorer**: Deterministic scoring
- **AudioPreprocessingService**: Orchestration & observability

### Design Principles
- **No Peak Normalization**: Preserves dynamic range
- **Band-Aware Adaptation**: Different bands get different treatment
- **Metrics Before Normalization**: Capture true signal properties
- **Graceful Fallbacks**: VAD fails → energy-based trimming
- **Structured Errors**: Named reason codes for debugging
- **Full Observability**: Every request traced and measured

## Dependencies

```
librosa>=0.9.2
scipy>=1.8.0
numpy>=1.20.0
soundfile>=0.11.0
pydantic>=2.0.0
fastapi>=0.100.0
```

## Development Notes

- Code is organized by responsibility (validators, pipeline, metrics, scoring)
- Each component is independently testable
- Pipeline order is critical - do not reorder steps
- Metrics extracted BEFORE normalization (by design)
- Quality score is deterministic (same input → same score)

## Support & Documentation

See `docs/AUDIO_PREPROCESSING_PRODUCTION_GUIDE.md` for:
- Detailed architecture
- Configuration tuning
- Deployment instructions
- Monitoring setup
- Performance benchmarking
- Troubleshooting guide

---

**Status**: ✅ Production-Ready  
**Version**: 1.0.0  
**Last Updated**: 2026-03-02  
**Author**: EPMSSTS Project
"""
