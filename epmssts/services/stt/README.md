# Speech-to-Text (STT) Service

Production-grade Whisper-based speech transcription microservice.

## Features

- **Whisper Integration**: Uses `faster-whisper` for efficient speech-to-text
- **GPU/CPU Support**: Automatic device selection with intelligent fallback
- **Confidence Scoring**: Multi-factor confidence assessment (5 independent factors)
- **Concurrency Control**: Semaphore-based queue management to prevent GPU OOM
- **Quality Thresholds**: Rejects unreliable transcriptions based on:
  - Confidence score cutoff
  - No-speech probability threshold
  - Hallucination detection
- **Observability**: Structured JSON logging, metrics tracking, health checks
- **Error Handling**: 14 distinct error codes for precise failure diagnosis
- **Async Ready**: Full `asyncio` support for concurrent requests

## Architecture

### Core Components

1. **DeviceManager** (`device_manager.py`)
   - GPU detection and initialization
   - CPU fallback logic
   - Memory management
   - Health monitoring

2. **ModelManager** (`model_manager.py`)
   - Whisper model loading and caching
   - Quantization selection (float16 on GPU, int8 on CPU)
   - Model warmup
   - Lifecycle management

3. **TranscriptionConfidenceScorer** (`confidence_scorer.py`)
   - Multi-factor confidence assessment (5 factors)
   - Hallucination detection
   - Repetition analysis
   - Segment consistency checking

4. **SpeechToTextService** (`stt_service.py`)
   - Main orchestration service
   - Async inference pipeline
   - Concurrency control
   - Metrics collection

### Data Flow

```
SttRequest (audio_data in base64)
    ↓
SpeechToTextService.transcribe()
    ├─ Audio preprocessing (decode, resample, normalize)
    ├─ Acquire inference slot (semaphore)
    ├─ Run inference (ModelManager + DeviceManager)
    ├─ Score confidence (ConfidenceScorer)
    ├─ Validation checks
    └─ SttResponse (with transcript, confidence, metrics)
```

## Configuration

### Model Sizes

- `tiny` - 39M parameters (fastest, lowest quality)
- `base` - 74M parameters
- `small` - 244M parameters
- `medium` - 769M parameters (recommended with GPU)
- `large` - 1.5B parameters (requires GPU)
- `large-v3` - 1.5B parameters with improved accuracy

### Device Selection

```python
service = SpeechToTextService(
    model_size="medium",          # Language model size
    device_prefer_gpu=True,       # Try GPU first
    max_concurrent_inferences=4,  # Concurrency limit
    queue_timeout_seconds=30.0,   # Queue wait timeout
    inference_timeout_seconds=60.0,  # Inference timeout
)
```

### Quality Thresholds (in SttRequest)

```python
request = SttRequest(
    audio_data=base64_encoded_audio,
    confidence_threshold=0.5,    # Min confidence score [0-1]
    no_speech_threshold=0.3,     # Max no-speech prob [0-1]
)
```

## API Endpoints

### POST /stt/transcribe
Transcribe audio.

**Request:**
```json
{
  "audio_data": "base64_encoded_audio",
  "format": "wav",
  "language": "en",
  "confidence_threshold": 0.5,
  "no_speech_threshold": 0.3
}
```

**Success Response (200):**
```json
{
  "success": true,
  "transcript": "Hello world",
  "confidence": 0.92,
  "language": "en",
  "processing_time_ms": 245.5,
  "device_used": "gpu",
  "audio_duration_seconds": 2.5,
  "segments": [...]
}
```

**Error Response (400):**
```json
{
  "success": false,
  "error_code": "ERR_STT_020",
  "error_message": "No speech detected",
  "user_friendly_message": "No speech detected. Check audio input."
}
```

## Error Codes

| Code | Reason | Recovery |
|------|--------|----------|
| ERR_STT_001 | Model load failed | Restart service |
| ERR_STT_010 | Inference timeout | Retry with shorter audio |
| ERR_STT_020 | No speech detected | Check audio quality |
| ERR_STT_021 | Audio too short | Provide ≥ 0.5s audio |
| ERR_STT_022 | Audio too long | Max 10 minutes |
| ERR_STT_025 | Hallucination detected | Unreliable transcript |
| ERR_STT_031 | Queue full | Retry shortly |

See `exceptions.py` for complete error code reference.

## Usage Example

### Python

```python
import asyncio
from epmssts.services.stt import SpeechToTextService, SttRequest
import base64

async def transcribe_audio(audio_file_path):
    # Initialize service
    service = SpeechToTextService(model_size="medium")
    await service.initialize()
    
    # Prepare audio
    with open(audio_file_path, 'rb') as f:
        audio_bytes = f.read()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    
    # Create request
    request = SttRequest(
        audio_data=audio_b64,
        format="wav",
        language="en",
        confidence_threshold=0.5,
    )
    
    # Transcribe
    response = await service.transcribe(request)
    
    if response.success:
        print(f"Transcript: {response.transcript}")
        print(f"Confidence: {response.confidence:.2f}")
        print(f"Device: {response.device_used}")
    else:
        print(f"Error: {response.user_friendly_message}")

# Run
asyncio.run(transcribe_audio("audio.wav"))
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| P95 Latency (5s audio) | < 2.5s | GPU with float16 |
| P95 Latency (15s audio) | < 5.0s | GPU with float16 |
| Throughput | 100k req/day | 1 GPU, 4 concurrent |
| GPU Memory | < 4GB | Medium model recommended |
| CPU Memory | < 2GB | With int8 quantization |

## Monitoring

### Health Check
```python
health = service.get_health_status()
# {
#   "status": "healthy|degraded|unhealthy",
#   "model_loaded": True,
#   "error_rate": 0.01,
#   ...
# }
```

### Metrics
```python
metrics = service.get_metrics()
# {
#   "total_requests": 1000,
#   "success_rate": 0.98,
#   "average_latency_ms": 245,
#   "language_distribution": {"en": 850, "es": 150},
#   "gpu_used_percentage": 95,
#   ...
# }
```

## Deployment

### Requirements
- Python 3.10+
- PyTorch (CPU or CUDA 11.8+)
- faster-whisper
- soundfile, librosa, numpy, scipy

### Installation
```bash
pip install -r requirements.txt
```

### Running Service
```python
# In your FastAPI app
from epmssts.services.stt import SpeechToTextService

stt_service = SpeechToTextService(model_size="medium")

@app.on_event("startup")
async def startup():
    await stt_service.initialize()

@app.post("/stt/transcribe")
async def transcribe(request: SttRequest):
    return await stt_service.transcribe(request)
```

## Testing

Run all STT tests:
```bash
pytest epmssts/services/stt/tests/ -v
```

Test coverage:
```bash
pytest epmssts/services/stt/tests/ --cov=epmssts.services.stt --cov-report=html
```

## Known Limitations

1. Models require ~2-4GB VRAM (medium) or ~8GB (large)
2. Inference is CPU-bound even on GPU (Whisper limitation)
3. Language detection works for ~99 languages
4. Maximum audio duration: 10 minutes (model limitation)
5. Minimum reliable audio: 0.5 seconds

## Future Enhancements

- [ ] Streaming transcription support
- [ ] Vocabulary constraints
- [ ] Language-specific models
- [ ] Diarization (speaker separation)
- [ ] Keyword spotting
- [ ] Custom acoustic models

## References

- [Faster Whisper](https://github.com/guillaumekln/faster-whisper)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [EPMSSTS Documentation](../../../docs/)
