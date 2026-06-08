# Emotion-Aware Text-to-Speech Service v2

Production-grade neural speech synthesis with emotion preservation, prosody control, waveform validation, and intelligent fallback chains.

## Overview

**NOT a basic TTS wrapper.** This is an enterprise-grade Text-to-Speech microservice designed for global AI-powered customer support systems.

### Key Features

✅ **Neural TTS Synthesis**
- Coqui XTTS v2 (multilingual, 16 languages)
- GPU accelerated (FP16 support)
- High-quality speech output

✅ **Emotion-Aware Prosody Control**
- Maps emotions → prosody parameters (rate, pitch, energy, variance)
- 8 emotions supported (happy, sad, angry, neutral, excited, fear, surprise, disgust)
- Calibrated ranges (preserve intelligibility)
- Confidence-weighted intensity

✅ **Waveform Quality Validation**
- Duration checks (> 0.1s)
- Silence detection (RMS > threshold)
- Clipping detection (peak < 0.99)
- Pure tone detection (spectral flatness)
- File size validation (> 5KB)

✅ **Intelligent Fallback Chain**
- Primary: Coqui XTTS v2
- Retry with adjusted prosody
- Secondary: gTTS (Google TTS)
- System TTS: pyttsx3
- Never returns silent audio

✅ **Observable & Scalable**
- Latency tracking (p50, p95, p99)
- Emotion distribution metrics
- Fallback usage monitoring
- GPU memory tracking
- Prometheus compatible

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         TTS Request                               │
│  (translated_text, target_language, emotion_label, confidence)    │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    1. Input Validation                            │
│  - Check text not empty                                           │
│  - Check length < 5000 chars                                      │
│  - Check translation_confidence >= 0.5                            │
│  - Check language supported                                       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                 2. Prosody Mapping (Emotion → Params)             │
│  Happy    → +8% rate, +1.5 pitch, +15% energy, +20% variance     │
│  Sad      → -10% rate, -1.5 pitch, -15% energy, -20% variance    │
│  Angry    → +12% rate, +0.5 pitch, +35% energy, +25% variance    │
│  Neutral  → 0% changes (baseline)                                 │
│  Excited  → +15% rate, +2.0 pitch, +25% energy, +30% variance    │
│                                                                    │
│  Intensity scaled by emotion_confidence                           │
│  All parameters bounded (prevent distortion)                      │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                 3. Neural TTS Synthesis (XTTS v2)                 │
│  - Load text → tokenize                                           │
│  - Apply prosody (rate, pitch, energy)                            │
│  - Generate mel-spectrogram                                       │
│  - Vocoder → waveform                                             │
│  - Post-process: time stretch, pitch shift (pyrubberband)         │
│  - GPU accelerated, FP16 inference                                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                4. Waveform Quality Validation                     │
│  ✓ Duration > 0.1s                                                │
│  ✓ RMS amplitude > 0.01 (not silent)                              │
│  ✓ Peak amplitude < 0.99 (not clipped)                            │
│  ✓ Spectral flatness 0.05-0.6 (not pure tone/noise)              │
│  ✓ File size > 5KB                                                │
│                                                                    │
│  If validation FAILS → Trigger fallback                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
                      [Validation OK?]
                       /            \
                    YES              NO
                     │                │
                     │                ▼
                     │    ┌────────────────────────────┐
                     │    │  5. Fallback Chain          │
                     │    │  a) Retry primary (reduced  │
                     │    │     prosody intensity)      │
                     │    │  b) Secondary: gTTS         │
                     │    │  c) System TTS: pyttsx3     │
                     │    │  d) Structured failure      │
                     │    └──────────┬─────────────────┘
                     │               │
                     │               ▼
                     │        [Fallback OK?]
                     │          /        \
                     │        YES        NO
                     │         │          │
                     ▼         ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    6. Save Audio File                             │
│  Format: WAV, 16kHz, Mono, PCM 16-bit                             │
│  Path: ./tts_outputs/tts_{request_id}.wav                         │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       TTS Response                                │
│  - status: success/partial/failed                                 │
│  - audio_path: ./tts_outputs/tts_{request_id}.wav                │
│  - prosody_profile: {rate, pitch, energy, variance}               │
│  - waveform_quality: {duration, rms, peak, flatness, is_valid}   │
│  - fallback_info: {fallback_used, engine_used, retry_count}      │
│  - latency_ms: 850                                                │
│  - latency_breakdown: {validation, prosody, synthesis, save}      │
└──────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### 1. POST /api/v2/tts/synthesize

Synthesize speech from text with emotion preservation.

**Request Body:**
```json
{
  "translated_text": "I am very excited about this product!",
  "target_language": "en",
  "emotion_label": "excited",
  "emotion_confidence": 0.89,
  "translation_confidence": 0.92,
  "request_id": "req_12345",
  "speaker_id": null,
  "prosody_intensity": 1.0,
  "min_translation_confidence": 0.5
}
```

**Response:**
```json
{
  "status": "success",
  "audio_path": "./tts_outputs/tts_req_12345.wav",
  "audio_base64": null,
  "prosody_profile": {
    "rate_multiplier": 1.15,
    "pitch_shift": 2.0,
    "energy_scale": 1.25,
    "pitch_variance": 1.3,
    "emotion_intensity": 0.89
  },
  "waveform_quality": {
    "duration_seconds": 2.5,
    "file_size_kb": 80.0,
    "rms_amplitude": 0.15,
    "peak_amplitude": 0.85,
    "is_clipping": false,
    "spectral_flatness": 0.25,
    "is_valid": true,
    "validation_errors": []
  },
  "fallback_info": {
    "fallback_used": false,
    "primary_engine_error": null,
    "engine_used": "primary_xtts_v2",
    "retry_count": 0
  },
  "latency_ms": 1250,
  "latency_breakdown": {
    "validation_ms": 5,
    "prosody_mapping_ms": 2,
    "synthesis_ms": 1200,
    "waveform_validation_ms": 10,
    "save_audio_ms": 33
  },
  "model_version": "tts_models/multilingual/multi-dataset/xtts_v2",
  "request_id": "req_12345",
  "error_message": null
}
```

**Status Codes:**
- `200 OK` - Synthesis completed (check `status` field)
- `500 Internal Server Error` - Service error

**Response Status Field:**
- `success` - Synthesis succeeded with primary engine
- `partial` - Synthesis succeeded but used fallback
- `failed` - All synthesis attempts failed

### 2. GET /api/v2/tts/audio/{request_id}

Download generated audio file.

**Response:**
- WAV file (16kHz, mono, PCM 16-bit)

### 3. GET /api/v2/tts/health

Get service health status.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "primary_tts": true
  },
  "gpu_available": true,
  "gpu_memory_used_mb": 1250.5,
  "error_rate": 0.02,
  "fallback_rate": 0.08,
  "average_latency_ms": 1180,
  "uptime_seconds": 7200
}
```

### 4. GET /api/v2/tts/metrics

Get detailed metrics snapshot.

**Response:**
```json
{
  "total_requests": 5000,
  "success_count": 4600,
  "partial_count": 350,
  "failed_count": 50,
  "fallback_count": 400,
  "average_latency_ms": 1180,
  "latency_p50_ms": 950,
  "latency_p95_ms": 2100,
  "latency_p99_ms": 3200,
  "emotion_distribution": {
    "happy": 1500,
    "sad": 800,
    "angry": 600,
    "neutral": 1800,
    "excited": 300
  },
  "language_distribution": {
    "en": 3000,
    "es": 1200,
    "fr": 800
  },
  "error_distribution": {
    "ERR_TTS_036": 30,
    "ERR_TTS_038": 20
  },
  "average_audio_duration_seconds": 2.5,
  "average_audio_size_kb": 80,
  "waveform_validation_failures": 45
}
```

### 5. GET /api/v2/tts/model-info

Get model information.

**Response:**
```json
{
  "model": {
    "model_name": "tts_models/multilingual/multi-dataset/xtts_v2",
    "device": "cuda",
    "fp16_enabled": true,
    "sample_rate": 16000,
    "model_loaded": true,
    "supported_languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "ko", "hi"],
    "gpu_available": true,
    "gpu_memory_allocated_mb": 1250.5
  },
  "prosody": {
    "total_emotions": 8,
    "supported_emotions": ["happy", "sad", "angry", "neutral", "excited", "fear", "surprise", "disgust"],
    "rate_range": [0.7, 1.3],
    "pitch_range": [-3.0, 3.5],
    "energy_range": [0.7, 1.5],
    "variance_range": [0.7, 1.4]
  },
  "validation": {
    "min_duration_seconds": 0.1,
    "min_rms_amplitude": 0.01,
    "max_peak_amplitude": 0.99
  },
  "fallback": {
    "total_attempts": 5000,
    "primary_success_count": 4600,
    "retry_success_count": 300,
    "secondary_success_count": 50,
    "system_tts_success_count": 0,
    "fallback_rate": 0.08,
    "primary_success_rate": 0.92
  }
}
```

### 6. GET /api/v2/tts/supported-emotions

Get list of supported emotions.

**Response:**
```json
{
  "emotions": [
    {"label": "happy", "description": "Upbeat, energetic, positive tone"},
    {"label": "sad", "description": "Subdued, melancholic, lower energy"},
    {"label": "angry", "description": "Intense, forceful, emphatic"},
    {"label": "neutral", "description": "Natural, balanced, conversational"},
    {"label": "excited", "description": "Enthusiastic, animated, high energy"},
    {"label": "fear", "description": "Anxious, tense, uncertain"},
    {"label": "surprise", "description": "Unexpected, sudden, exclamatory"},
    {"label": "disgust", "description": "Aversive, repelled, negative"}
  ]
}
```

### 7. GET /api/v2/tts/supported-languages

Get list of supported languages.

**Response:**
```json
{
  "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "ko", "hi"],
  "total": 16
}
```

## Prosody Mapping

### Emotion → Prosody Parameters

| Emotion | Rate | Pitch Shift | Energy | Variance | Description |
|---------|------|-------------|--------|----------|-------------|
| **Happy** | +8% | +1.5 semitones | +15% | +20% | Upbeat, positive |
| **Sad** | -10% | -1.5 semitones | -15% | -20% | Subdued, melancholic |
| **Angry** | +12% | +0.5 semitones | +35% | +25% | Intense, forceful |
| **Neutral** | 0% | 0 semitones | 0% | 0% | Balanced, natural |
| **Excited** | +15% | +2.0 semitones | +25% | +30% | Enthusiastic, animated |
| **Fear** | +10% | +1.0 semitones | -5% | +15% | Anxious, tense |
| **Surprise** | +5% | +2.5 semitones | +15% | +25% | Exclamatory, sudden |
| **Disgust** | -5% | -0.5 semitones | -10% | -10% | Aversive, negative |

### Intensity Scaling

Prosody intensity is scaled by `emotion_confidence`:

```
effective_intensity = prosody_intensity × emotion_confidence
```

- `emotion_confidence = 1.0` → Full prosody effect
- `emotion_confidence = 0.5` → 50% prosody effect (closer to neutral)
- `emotion_confidence = 0.2` → 20% prosody effect (mostly neutral)

This prevents over-exaggeration when emotion prediction is uncertain.

### Parameter Boundaries

All prosody parameters are clamped to safe ranges:

- **Rate**: [0.7, 1.3] (±30%)
- **Pitch**: [-3.0, +3.5] semitones
- **Energy**: [0.7, 1.5] (±50%)
- **Variance**: [0.7, 1.4] (±40%)

Prevents distortion and maintains intelligibility.

## Waveform Validation

### Validation Checks

1. **Duration Check**
   - Threshold: > 0.1 seconds
   - Catches: Empty output, truncation

2. **RMS Amplitude Check (Silence Detection)**
   - Threshold: > 0.01
   - Catches: Silent audio, very quiet output

3. **Peak Amplitude Check (Clipping Detection)**
   - Threshold: < 0.99
   - Catches: Audio clipping, distortion

4. **Spectral Flatness Check (Pure Tone Detection)**
   - Range: 0.05 - 0.6
   - Catches: Pure tones (< 0.05), noise (> 0.6)
   - Normal speech: 0.1 - 0.4

5. **File Size Check**
   - Threshold: > 5KB
   - Catches: Corrupted files, empty writes

### Validation Response

If validation **fails**, waveform_quality contains:
```json
{
  "is_valid": false,
  "validation_errors": [
    "Duration 0.05s < 0.1s",
    "RMS 0.005 < 0.01 (likely silent)"
  ]
}
```

Triggers fallback chain automatically.

## Fallback Chain

### Strategy

```
Primary Engine (XTTS v2)
    ↓ [Validation fails]
Retry (Reduced prosody intensity)
    ↓ [Still fails]
Secondary Engine (gTTS)
    ↓ [Still fails]
System TTS (pyttsx3)
    ↓ [Still fails]
Structured Failure (Never empty)
```

### Fallback Triggers

1. **Waveform validation failure**
   - Silent audio (RMS < threshold)
   - Too short (duration < 0.1s)
   - Clipped (peak > 0.99)
   - Pure tone (flatness < 0.05)

2. **Synthesis errors**
   - GPU OOM
   - Timeout (> 10s)
   - Model inference error
   - Empty output

### Retry Strategy

On first retry:
- **Reduce prosody intensity** → 50%
- Move emotion parameters closer to neutral
- Prevents synthesis issues from extreme prosody

### Engine Characteristics

| Engine | Quality | Speed | Prosody | Fallback Level |
|--------|---------|-------|---------|----------------|
| **XTTS v2** | ⭐⭐⭐⭐⭐ | Medium | ✅ Full | Primary |
| **XTTS v2 Retry** | ⭐⭐⭐⭐⭐ | Medium | ✅ Reduced | Level 1 |
| **gTTS** | ⭐⭐⭐ | Fast | ❌ None | Level 2 |
| **pyttsx3** | ⭐⭐ | Very Fast | ❌ None | Level 3 |

## Latency SLA

### Performance Targets

| Text Length | p95 Latency |
|-------------|-------------|
| Short (< 50 chars) | < 1.5s |
| Moderate (50-200 chars) | < 3s |
| Long (200-500 chars) | < 5s |

### Latency Breakdown

Typical latency distribution:
- Validation: 5ms (0.4%)
- Prosody mapping: 2ms (0.2%)
- Synthesis: 1200ms (96%)
- Waveform validation: 10ms (0.8%)
- Audio save: 33ms (2.6%)

**Total: ~1250ms** for moderate text

### Optimization Strategies

1. **GPU Acceleration**
   - 5-10x faster than CPU
   - Use NVIDIA GPU (T4, V100, A100)

2. **FP16 Inference**
   - 2x faster inference
   - 50% less GPU memory
   - Minimal quality loss

3. **Model Caching**
   - Load model once at startup
   - Keep in GPU memory
   - Avoid per-request loading

4. **Batch Synthesis**
   - Process multiple requests in batch
   - Improves GPU utilization

## Deployment

### Requirements

```txt
# Core TTS
TTS>=0.20.0  # Coqui TTS
torch>=2.0.0
torchaudio>=2.0.0

# Audio processing
soundfile>=0.12.0
librosa>=0.10.0
pyrubberband>=0.3.0

# Fallback engines
gtts>=2.4.0
pyttsx3>=2.90

# API
fastapi>=0.104.0
pydantic>=2.0.0
numpy>=1.24.0
```

### GPU Setup

```bash
# Install CUDA dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify GPU
python -c "import torch; print(torch.cuda.is_available())"
```

### Model Caching

Models are downloaded on first use. To pre-download:

```python
from TTS.api import TTS

# Download XTTS v2
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
```

Model cache location: `~/.local/share/tts/`

### FastAPI Integration

```python
# In main.py
from fastapi import FastAPI
from epmssts.services.tts_v2.routes import router, initialize_tts_service

app = FastAPI()

# Initialize TTS service on startup
@app.on_event("startup")
async def startup_event():
    initialize_tts_service(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2",
        device="cuda",
        enable_fp16=True,
        output_dir="./tts_outputs"
    )

# Include TTS routes
app.include_router(router)
```

### Docker Deployment

```dockerfile
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y python3.10 python3-pip ffmpeg

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy service
COPY epmssts/ /app/epmssts/

# Create output directory
RUN mkdir -p /app/tts_outputs

# Expose port
EXPOSE 8000

# Run service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Model configuration
TTS_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
TTS_DEVICE=cuda
TTS_ENABLE_FP16=true
TTS_OUTPUT_DIR=./tts_outputs

# Quality thresholds
TTS_MAX_TEXT_LENGTH=5000
TTS_MIN_TRANSLATION_CONFIDENCE=0.5
TTS_MIN_RMS_AMPLITUDE=0.01

# Fallback configuration
TTS_ENABLE_RETRY=true
TTS_ENABLE_SECONDARY=true
TTS_ENABLE_SYSTEM_TTS=true
```

## Monitoring

### Key Metrics

**Synthesis Quality**:
- `tts_success_rate` - % successful syntheses
- `tts_fallback_rate` - % using fallback
- `tts_waveform_validation_failures` - Invalid audio count

**Performance**:
- `tts_latency_p50_ms` - Median latency
- `tts_latency_p95_ms` - 95th percentile latency
- `tts_latency_p99_ms` - 99th percentile latency

**Errors**:
- `tts_error_rate` - % failed syntheses
- `tts_error_distribution` - Error types breakdown

**Resource Usage**:
- `tts_gpu_memory_used_mb` - GPU memory usage
- `tts_gpu_utilization` - GPU utilization %

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request counters
tts_requests_total = Counter(
    'tts_requests_total',
    'Total TTS requests',
    ['status']  # success, partial, failed
)

# Latency histogram
tts_latency_seconds = Histogram(
    'tts_latency_seconds',
    'TTS synthesis latency',
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
)

# Fallback usage
tts_fallback_used = Counter(
    'tts_fallback_used_total',
    'Fallback engine usage',
    ['engine']  # retry, gtts, pyttsx3
)
```

## Testing

Tests in `tests/` directory covering:

- ✅ Prosody mapping correctness
- ✅ Synthesis quality (happy, sad, angry speech)
- ✅ Waveform validation accuracy
- ✅ Fallback chain behavior
- ✅ Latency benchmarks
- ✅ Edge cases (empty text, very long text)
- ✅ Integration tests

Target coverage: **> 85%**

## Error Codes

| Code | Exception | Description |
|------|-----------|-------------|
| ERR_TTS_001 | TTSModelLoadError | Model failed to load |
| ERR_TTS_011 | EmptyInputTextError | Input text is empty |
| ERR_TTS_012 | TextTooLongError | Text exceeds max length |
| ERR_TTS_013 | TranslationConfidenceTooLowError | Translation quality insufficient |
| ERR_TTS_014 | UnsupportedLanguageError | Language not supported |
| ERR_TTS_021 | SynthesisInferenceError | Synthesis failed |
| ERR_TTS_022 | SynthesisTimeoutError | Synthesis timeout (> 10s) |
| ERR_TTS_023 | GPUOOMError | GPU out of memory |
| ERR_TTS_036 | AudioDurationTooShortError | Audio < 0.1s |
| ERR_TTS_037 | AudioFileSizeTooSmallError | File < 5KB |
| ERR_TTS_038 | SilentAudioDetectedError | RMS < threshold |
| ERR_TTS_039 | AudioClippingDetectedError | Peak > 0.99 |
| ERR_TTS_040 | PureToneDetectedError | Not speech (pure tone) |
| ERR_TTS_048 | FallbackChainExhaustedError | All fallbacks failed |

## License

MIT License - See LICENSE file

## Support

For issues, questions, or contributions, contact the EPMSSTS development team.
