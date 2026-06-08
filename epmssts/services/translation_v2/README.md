# Translation Intelligence Service v2

Production-grade translation layer with context-awareness, emotion preservation, confidence scoring, intelligent retry, and drift monitoring.

## Overview

**NOT a simple wrapper** around NLLB or MarianMT. This is an enterprise-grade translation intelligence layer designed for global multi-language customer support systems.

### Key Features

✅ **Context-Aware Translation**
- NLLB-200 with beam search (beam_size=4)
- Context window support (last 1-2 sentences)
- Temperature control for quality tuning

✅ **Multi-Factor Confidence Scoring**
- Model log probability (30% weight)
- Length consistency (20% weight)
- Repetition detection (25% weight)
- Language consistency (15% weight)
- Entity preservation (10% weight)

✅ **Emotion Tone Preservation**
- Polarity matching (positive/negative/neutral) - 40%
- Intensity preservation (emotion strength) - 30%
- Markers preservation (!, ?, CAPS, emoji) - 30%

✅ **Intelligent Retry**
- Reason-specific parameter adjustment
- Max 2 retries with different strategies
- Tracks retry reasons for monitoring

✅ **Drift Monitoring**
- Confidence drift alerts (> 15% drop)
- Emotion preservation drift (> 20% drop)
- High retry rate alerts (> 20%)
- Latency spike detection (> 50% increase)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Translation Request                       │
│  (transcript, source_lang, target_lang, emotion_label, etc)  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  1. Input Validation                         │
│  - Check transcript length (max 2000 chars)                  │
│  - Validate STT confidence (min 0.4)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  2. Language Detection                       │
│  - FastText language detection                               │
│  - Code-switching detection                                  │
│  - Confidence scoring                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  3. Translation (NLLB-200)                   │
│  - Prepend context sentences                                 │
│  - Beam search (size=4, temp=1.0)                            │
│  - Log probability extraction                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              4. Confidence Scoring (5 factors)               │
│  - Model log probability                                     │
│  - Length consistency (language-pair specific)               │
│  - Repetition detection (n-gram + character)                 │
│  - Language consistency (script validation)                  │
│  - Entity preservation (proper nouns)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          5. Emotion Preservation Validation (3 factors)      │
│  - Polarity match (positive/negative/neutral)                │
│  - Intensity preservation (emotion strength)                 │
│  - Markers preserved (!, ?, CAPS)                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              6. Quality Threshold Check                      │
│  - Translation confidence >= 0.75?                           │
│  - Emotion preservation >= 0.70?                             │
│  - If NO and retries < 2 → RETRY with adjusted params       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  7. Drift Monitoring                         │
│  - Record: confidence, emotion, latency, retry               │
│  - Check for drift patterns                                  │
│  - Emit alerts if thresholds exceeded                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Translation Response                        │
│  - Translated text                                           │
│  - Language detection result                                 │
│  - 5-factor confidence metrics                               │
│  - 3-factor emotion metrics                                  │
│  - Retry info (count, reasons, adjustments)                  │
│  - Latency breakdown                                         │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### 1. POST /api/v2/translation/translate

Translate text with emotion preservation and confidence scoring.

**Request Body:**
```json
{
  "transcript": "I am very happy with this service!",
  "source_lang": "eng_Latn",  // Optional - auto-detect if not provided
  "target_lang": "spa_Latn",
  "emotion_label": "happy",
  "emotion_confidence": 0.92,
  "stt_confidence": 0.95,
  "context_window": ["Previous sentence one.", "Previous sentence two."],
  "request_id": "req_12345",
  "min_translation_confidence": 0.75,  // Optional
  "min_emotion_preservation": 0.70     // Optional
}
```

**Response:**
```json
{
  "status": "success",  // "success" | "partial" | "failed"
  "translated_text": "¡Estoy muy feliz con este servicio!",
  "language_detection": {
    "detected_language": "eng_Latn",
    "confidence": 0.98,
    "alternatives": [{"language": "eng_Latn", "confidence": 0.98}],
    "is_code_switching": false
  },
  "confidence_metrics": {
    "overall_confidence": 0.87,
    "model_log_probability": 0.85,
    "length_consistency_score": 0.90,
    "repetition_score": 1.0,
    "language_consistency_score": 0.95,
    "entity_preservation_score": 0.80
  },
  "emotion_metrics": {
    "preservation_score": 0.88,
    "polarity_match": "positive",
    "intensity_preserved": true,
    "markers_preserved": true
  },
  "model_version": "facebook/nllb-200-distilled-600M",
  "retry_info": {
    "retry_count": 0,
    "retry_reasons": [],
    "retry_adjustments": [],
    "final_attempt": true
  },
  "latency_ms": 850,
  "latency_breakdown": {
    "validation_ms": 2,
    "language_detection_ms": 50,
    "translation_and_retry_ms": 790
  },
  "request_id": "req_12345"
}
```

**Status Codes:**
- `200 OK` - Translation completed (check `status` field for quality)
- `500 Internal Server Error` - Service error

**Response Status Field:**
- `success` - Translation meets quality thresholds
- `partial` - Translation exists but below quality thresholds
- `failed` - Translation failed or very low quality

### 2. GET /api/v2/translation/health

Get service health status.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "translation_engine": true,
    "language_detector": true
  },
  "error_rate": 0.02,
  "retry_rate": 0.15,
  "average_confidence": 0.84,
  "average_emotion_preservation": 0.81,
  "uptime_seconds": 3600
}
```

### 3. GET /api/v2/translation/metrics

Get detailed metrics snapshot.

**Response:**
```json
{
  "total_requests": 1000,
  "success_count": 850,
  "partial_count": 100,
  "failed_count": 50,
  "retry_count": 150,
  "average_confidence": 0.84,
  "confidence_p50": 0.86,
  "confidence_p95": 0.92,
  "average_emotion_preservation": 0.81,
  "emotion_preservation_p50": 0.83,
  "language_distribution": {
    "eng_Latn": 500,
    "spa_Latn": 300,
    "fra_Latn": 200
  },
  "latency_p50_ms": 650,
  "latency_p95_ms": 1200,
  "latency_p99_ms": 1800,
  "retry_rate": 0.15,
  "retry_reasons_distribution": {
    "low_confidence": 80,
    "emotion_mismatch": 50,
    "repetitive_loop": 20
  },
  "active_alerts": 0
}
```

### 4. GET /api/v2/translation/drift-alerts

Get active drift alerts.

**Response:**
```json
[
  {
    "alert_type": "confidence_drift",
    "severity": "high",
    "metric_value": 0.65,
    "threshold": 0.75,
    "baseline_value": 0.87,
    "message": "Confidence drift: current=0.65, baseline=0.87, drift=25.3%",
    "timestamp": "2024-01-15T10:30:00"
  }
]
```

**Alert Types:**
- `confidence_drift` - Confidence dropped > 15% below baseline
- `emotion_preservation_drift` - Emotion preservation dropped > 20%
- `high_retry_rate` - Retry rate > 20%
- `latency_spike` - Latency > 50% above baseline

### 5. GET /api/v2/translation/model-status

Get model status.

**Response:**
```json
{
  "model_name": "facebook/nllb-200-distilled-600M",
  "device": "cuda",
  "language_detector_loaded": true,
  "translation_engine_loaded": true,
  "uptime_seconds": 3600
}
```

## Usage Examples

### Basic Translation

```python
from epmssts.services.translation_v2 import TranslationService, TranslationRequest

# Initialize service
service = TranslationService(device="cuda")

# Create request
request = TranslationRequest(
    transcript="I am very happy with this service!",
    target_lang="spa_Latn",
    emotion_label="happy",
    emotion_confidence=0.92
)

# Translate
response = await service.translate(request)

print(f"Translation: {response.translated_text}")
print(f"Confidence: {response.confidence_metrics.overall_confidence:.2f}")
print(f"Emotion preserved: {response.emotion_metrics.preservation_score:.2f}")
```

### With Context Window

```python
request = TranslationRequest(
    transcript="It's amazing!",
    target_lang="spa_Latn",
    emotion_label="happy",
    emotion_confidence=0.88,
    context_window=[
        "I just received my order.",
        "The quality is excellent."
    ]
)

response = await service.translate(request)
# Context helps: "¡Es increíble!" (referring to order quality)
```

### Monitoring Drift

```python
# Get metrics
metrics = service.get_metrics()
print(f"Average confidence: {metrics.average_confidence:.2f}")
print(f"Retry rate: {metrics.retry_rate:.1%}")

# Check drift alerts
alerts = service.get_drift_alerts()
for alert in alerts:
    print(f"Alert: {alert.alert_type} - {alert.message}")
```

## Quality Thresholds

### Default Thresholds

- **Translation Confidence**: 0.75
- **Emotion Preservation**: 0.70
- **STT Confidence**: 0.4 (minimum input quality)
- **Retry Rate Alert**: 20%
- **Confidence Drift Alert**: 15% drop

### Confidence Scoring Formula

```
Overall Confidence = 
  (0.30 × Model Log Probability) +
  (0.20 × Length Consistency) +
  (0.25 × Repetition Score) +
  (0.15 × Language Consistency) +
  (0.10 × Entity Preservation)
```

**Model Log Probability**: Normalized from [-10, 0] to [0, 1]

**Length Consistency**: Based on language-pair expected ratios
- en→es: 0.9-1.3
- en→zh: 0.5-0.9
- en→de: 0.9-1.2

**Repetition Score**: Detects n-gram loops and character repetition
- 3-gram frequency > 30% → low score
- Character repetition patterns → low score

**Language Consistency**: Script validation
- Spanish → Latin script
- Chinese → Han script
- Hindi → Devanagari script

**Entity Preservation**: Proper noun retention
- Extracts capitalized words from source
- Checks presence in translation

### Emotion Preservation Formula

```
Preservation Score = 
  (0.40 × Polarity Match) +
  (0.30 × Intensity Preserved) +
  (0.30 × Markers Preserved)
```

**Polarity Match**: positive/negative/neutral classification
- Keyword-based emotion detection
- Adjusted by original emotion confidence

**Intensity Preserved**: Emotion strength comparison
- Keyword count ratio
- Exclamation mark preservation

**Markers Preserved**: Signal retention
- Exclamation marks (!)
- Question marks (?)
- Capitalization patterns
- Emoji preservation

## Retry Logic

### Retry Triggers

1. **Empty Output**: Translation returned empty string
2. **Low Confidence**: Overall confidence < 0.6
3. **Emotion Mismatch**: Preservation score < 0.6
4. **Repetitive Loop**: Detected n-gram repetition
5. **Length Mismatch**: Translation too short/long vs expected

### Retry Strategies

**First Retry** (if low confidence or repetition):
- Increase beam size: 4 → 6
- Adjust temperature: 1.0 → 1.2

**Second Retry** (if first fails):
- Reduce beam size: 6 → 3
- Lower temperature: 1.2 → 0.8

**Reason-Specific Adjustments**:
- Repetition detected → Lower temperature (0.8)
- Low confidence → Higher beams (6)
- Empty output → Reset to defaults + increase max_length

**Max Retries**: 2 (configurable)

## Supported Languages

NLLB-200 supports 200 languages. Common language codes:

| Language | Code |
|----------|------|
| English | `eng_Latn` |
| Spanish | `spa_Latn` |
| French | `fra_Latn` |
| German | `deu_Latn` |
| Chinese (Simplified) | `zho_Hans` |
| Hindi | `hin_Deva` |
| Telugu | `tel_Telu` |
| Arabic | `arb_Arab` |
| Russian | `rus_Cyrl` |
| Japanese | `jpn_Jpan` |

[Full list](https://github.com/facebookresearch/flores/blob/main/flores200/README.md#languages-in-flores-200)

## Performance

### Latency Targets

- **Short text** (< 50 chars): p95 < 1s
- **Moderate text** (50-200 chars): p95 < 2s
- **Long text** (200-500 chars): p95 < 3s

### Throughput

- **GPU (NVIDIA T4)**: ~30 requests/sec
- **GPU (NVIDIA A100)**: ~100 requests/sec
- **CPU (8 cores)**: ~5 requests/sec

### Model Size

- **NLLB-200-distilled-600M**: ~600MB
- **FastText language detection**: ~126MB

## Deployment

### Requirements

```txt
transformers>=4.35.0
torch>=2.0.0
fasttext>=0.9.2
langdetect>=1.0.9
pydantic>=2.0.0
numpy>=1.24.0
fastapi>=0.104.0
```

### GPU Setup

```bash
# Install CUDA dependencies
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Verify GPU availability
python -c "import torch; print(torch.cuda.is_available())"
```

### Model Caching

Models are downloaded on first use. To pre-download:

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Download NLLB-200
model_name = "facebook/nllb-200-distilled-600M"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
```

### FastAPI Integration

```python
# In main.py
from fastapi import FastAPI
from epmssts.services.translation_v2.routes import router, initialize_translation_service

app = FastAPI()

# Initialize translation service on startup
@app.on_event("startup")
async def startup_event():
    initialize_translation_service(
        model_name="facebook/nllb-200-distilled-600M",
        device="cuda",
        fasttext_model_path=None  # Auto-download
    )

# Include translation routes
app.include_router(router)
```

### Docker Deployment

```dockerfile
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y python3.10 python3-pip

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy service
COPY epmssts/ /app/epmssts/

# Expose port
EXPOSE 8000

# Start service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Model configuration
TRANSLATION_MODEL_NAME=facebook/nllb-200-distilled-600M
TRANSLATION_DEVICE=cuda

# Quality thresholds
MIN_TRANSLATION_CONFIDENCE=0.75
MIN_EMOTION_PRESERVATION=0.70
MIN_STT_CONFIDENCE=0.4

# Drift monitoring
ENABLE_DRIFT_MONITORING=true
CONFIDENCE_DRIFT_THRESHOLD=0.15
EMOTION_DRIFT_THRESHOLD=0.20
HIGH_RETRY_RATE_THRESHOLD=0.20
```

## Monitoring

### Key Metrics

**Translation Quality**:
- `translation_confidence_avg` - Average confidence score
- `translation_confidence_p95` - 95th percentile confidence
- `emotion_preservation_avg` - Average emotion preservation
- `emotion_preservation_p50` - Median emotion preservation

**Performance**:
- `translation_latency_p50_ms` - Median latency
- `translation_latency_p95_ms` - 95th percentile latency
- `translation_latency_p99_ms` - 99th percentile latency

**Reliability**:
- `translation_success_rate` - % of successful translations
- `translation_partial_rate` - % of partial translations
- `translation_error_rate` - % of failed translations
- `translation_retry_rate` - % requiring retry

**Drift Alerts**:
- `translation_confidence_drift_alert` - Confidence degradation
- `translation_emotion_drift_alert` - Emotion preservation degradation
- `translation_high_retry_rate_alert` - Retry rate spike
- `translation_latency_spike_alert` - Latency increase

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request counters
translation_requests_total = Counter(
    'translation_requests_total',
    'Total translation requests',
    ['status']  # success, partial, failed
)

# Confidence metrics
translation_confidence = Histogram(
    'translation_confidence',
    'Translation confidence scores',
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Latency metrics
translation_latency = Histogram(
    'translation_latency_seconds',
    'Translation latency',
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0]
)

# Retry metrics
translation_retries = Counter(
    'translation_retries_total',
    'Total translation retries',
    ['reason']
)
```

## Error Codes

| Code | Exception | Description |
|------|-----------|-------------|
| ERR_TRANS_001 | TranslationModelLoadError | Failed to load translation model |
| ERR_TRANS_002 | LanguageDetectionModelLoadError | Failed to load language detection model |
| ERR_TRANS_003 | TranslationInferenceError | Translation inference failed |
| ERR_TRANS_011 | EmptyTranscriptError | Input transcript is empty |
| ERR_TRANS_012 | TranscriptTooLongError | Transcript exceeds max length |
| ERR_TRANS_013 | STTConfidenceTooLowError | STT confidence below threshold |
| ERR_TRANS_014 | UnsupportedLanguageError | Language not supported |
| ERR_TRANS_021 | LanguageDetectionError | Language detection failed |
| ERR_TRANS_022 | LanguageConfidenceTooLowError | Language detection confidence low |
| ERR_TRANS_023 | CodeSwitchingDetectedError | Code-switching detected in transcript |
| ERR_TRANS_031 | EmptyTranslationError | Translation output is empty |
| ERR_TRANS_032 | TranslationConfidenceTooLowError | Translation confidence below threshold |
| ERR_TRANS_033 | RepetitiveLoopDetectedError | Repetitive n-gram loop detected |
| ERR_TRANS_034 | EmotionPreservationError | Failed to preserve emotion tone |
| ERR_TRANS_035 | TranslationTimeoutError | Translation exceeded timeout |
| ERR_TRANS_046 | MaxRetriesExceededError | Exceeded maximum retry attempts |
| ERR_TRANS_047 | FallbackModelUnavailableError | Fallback model not available |
| ERR_TRANS_056 | ConfidenceDriftError | Confidence drift detected |
| ERR_TRANS_057 | EmotionPreservationDriftError | Emotion preservation drift detected |
| ERR_TRANS_058 | HighRetryRateAlertError | Retry rate exceeds threshold |

## Testing

Tests will be added in `tests/` directory covering:

- ✅ Language detection accuracy
- ✅ Translation quality (BLEU, COMET)
- ✅ Confidence scoring calibration
- ✅ Emotion preservation validation
- ✅ Retry logic correctness
- ✅ Drift monitoring accuracy
- ✅ Integration tests
- ✅ Performance benchmarks

Target coverage: **> 85%**

## License

MIT License - See LICENSE file

## Support

For issues, questions, or contributions, please contact the EPMSSTS development team.
