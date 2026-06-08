# TTS Service v2 - Integration Guide

Step-by-step guide to integrate the Emotion-Aware TTS service into the EPMSSTS backend.

## Integration Steps

### 1. Install Dependencies

Add to `requirements.txt`:

```txt
# TTS Service v2 dependencies
TTS>=0.20.0  # Coqui TTS
torch>=2.0.0
torchaudio>=2.0.0
soundfile>=0.12.0
librosa>=0.10.0
pyrubberband>=0.3.0
gtts>=2.4.0
pyttsx3>=2.90
```

Install:

```bash
# Install with GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install TTS dependencies
pip install TTS soundfile librosa pyrubberband gtts pyttsx3
```

### 2. Update Main FastAPI Application

Edit your main application file (e.g., `main.py`):

```python
from fastapi import FastAPI
from epmssts.services.tts_v2.routes import router as tts_router, initialize_tts_service

app = FastAPI(title="EPMSSTS API")

# Startup event: Initialize TTS service
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    
    # Initialize TTS Service v2
    initialize_tts_service(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2",
        device="cuda",  # Use "cpu" if no GPU
        enable_fp16=True,
        output_dir="./tts_outputs"
    )
    
    print("✅ TTS Service v2 initialized")

# Include TTS routes
app.include_router(tts_router)
```

### 3. Connect to Full EPMSSTS Pipeline

Integrate TTS after Translation service:

```python
# Example full pipeline endpoint
@app.post("/api/process-audio-full")
async def process_audio_full_pipeline(
    audio: UploadFile,
    target_language: str
):
    """
    Complete EPMSSTS pipeline:
    Audio → STT → Emotion → Translation → TTS
    """
    
    # Step 1: Audio Preprocessing
    processed_audio = await audio_preprocessing_service.process(audio)
    
    # Step 2: STT (Speech-to-Text)
    stt_result = await stt_service.transcribe(processed_audio)
    transcript = stt_result["transcript"]
    stt_confidence = stt_result["confidence"]
    
    # Step 3: Emotion Recognition
    emotion_result = await emotion_service.predict(processed_audio, transcript)
    emotion_label = emotion_result["emotion"]
    emotion_confidence = emotion_result["confidence"]
    
    # Step 4: Translation
    translation_request = TranslationRequest(
        transcript=transcript,
        target_lang=target_language,
        emotion_label=emotion_label,
        emotion_confidence=emotion_confidence,
        stt_confidence=stt_confidence
    )
    
    translation_result = await translation_service.translate(translation_request)
    translated_text = translation_result.translated_text
    translation_confidence = translation_result.confidence_metrics.overall_confidence
    
    # Step 5: TTS (NEW)
    from epmssts.services.tts_v2 import TTSRequest
    
    tts_request = TTSRequest(
        translated_text=translated_text,
        target_language=target_language,
        emotion_label=emotion_label,
        emotion_confidence=emotion_confidence,
        translation_confidence=translation_confidence,
        request_id=f"req_{uuid.uuid4()}"
    )
    
    tts_result = await tts_service.synthesize(tts_request)
    
    # Return combined results
    return {
        "transcript": transcript,
        "emotion": emotion_label,
        "translation": translated_text,
        "audio_path": tts_result.audio_path,
        "prosody_profile": tts_result.prosody_profile.dict(),
        "latency_breakdown": {
            "stt_ms": stt_result["latency_ms"],
            "emotion_ms": emotion_result["latency_ms"],
            "translation_ms": translation_result.latency_ms,
            "tts_ms": tts_result.latency_ms
        },
        "status": {
            "stt": "success",
            "emotion": "success",
            "translation": translation_result.status,
            "tts": tts_result.status
        }
    }
```

### 4. Standalone TTS Endpoint

For standalone TTS usage:

```python
from epmssts.services.tts_v2 import TTSRequest, TTSService

@app.post("/api/tts/synthesize-simple")
async def synthesize_simple(
    text: str,
    language: str = "en",
    emotion: str = "neutral"
):
    """Simple TTS synthesis endpoint"""
    
    request = TTSRequest(
        translated_text=text,
        target_language=language,
        emotion_label=emotion,
        emotion_confidence=0.8,
        translation_confidence=1.0
    )
    
    response = await tts_service.synthesize(request)
    
    return {
        "audio_path": response.audio_path,
        "latency_ms": response.latency_ms,
        "status": response.status
    }
```

### 5. Frontend Integration

#### Play Audio After Translation

```javascript
// Example: Process and play speech
async function processAndSpeak(audioBlob, targetLanguage) {
    const formData = new FormData();
    formData.append('audio', audioBlob);
    
    const response = await fetch(`/api/process-audio-full?target_language=${targetLanguage}`, {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    // Display results
    document.getElementById('transcript').textContent = result.transcript;
    document.getElementById('emotion').textContent = result.emotion;
    document.getElementById('translation').textContent = result.translation;
    
    // Play synthesized audio
    const audioResponse = await fetch(`/api/v2/tts/audio/${result.audio_path.split('/').pop().replace('.wav', '').replace('tts_', '')}`);
    const audioBlob = await audioResponse.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    
    const audioPlayer = new Audio(audioUrl);
    audioPlayer.play();
}
```

#### Text-to-Speech Widget

```javascript
// TTS widget
async function synthesizeAndPlay(text, language, emotion) {
    const response = await fetch('/api/v2/tts/synthesize', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            translated_text: text,
            target_language: language,
            emotion_label: emotion,
            emotion_confidence: 0.8,
            translation_confidence: 1.0
        })
    });
    
    const result = await response.json();
    
    if (result.status === 'success') {
        // Get audio file
        const audioPath = result.audio_path.split('/').pop().replace('.wav', '').replace('tts_', '');
        const audioResponse = await fetch(`/api/v2/tts/audio/${audioPath}`);
        const audioBlob = await audioResponse.blob();
        
        // Play
        const audioUrl = URL.createObjectURL(audioBlob);
        const audioPlayer = document.getElementById('audio-player');
        audioPlayer.src = audioUrl;
        audioPlayer.play();
        
        // Show prosody info
        document.getElementById('rate').textContent = result.prosody_profile.rate_multiplier.toFixed(2);
        document.getElementById('pitch').textContent = result.prosody_profile.pitch_shift.toFixed(1);
    } else {
        alert('TTS synthesis failed: ' + result.error_message);
    }
}
```

### 6. Environment Configuration

Create `.env` file:

```bash
# TTS Service Configuration
TTS_MODEL_NAME=tts_models/multilingual/multi-dataset/xtts_v2
TTS_DEVICE=cuda
TTS_ENABLE_FP16=true
TTS_OUTPUT_DIR=./tts_outputs

# Quality Thresholds
TTS_MAX_TEXT_LENGTH=5000
TTS_MIN_TRANSLATION_CONFIDENCE=0.5

# Fallback Configuration
TTS_ENABLE_RETRY=true
TTS_ENABLE_SECONDARY=true
TTS_ENABLE_SYSTEM_TTS=true
```

Load in Python:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    tts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_device: str = "cuda"
    tts_enable_fp16: bool = True
    tts_output_dir: str = "./tts_outputs"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Use in initialization
initialize_tts_service(
    model_name=settings.tts_model_name,
    device=settings.tts_device,
    enable_fp16=settings.tts_enable_fp16,
    output_dir=settings.tts_output_dir,
)
```

### 7. Monitoring Integration

#### Add to Dashboard

```python
@app.get("/api/dashboard/tts-metrics")
async def get_tts_dashboard_metrics():
    """Get TTS metrics for dashboard"""
    from epmssts.services.tts_v2.routes import get_tts_service
    
    service = get_tts_service()
    health = service.get_health()
    metrics = service.get_metrics()
    
    return {
        "health": {
            "status": health.status,
            "gpu_available": health.gpu_available,
            "gpu_memory_mb": health.gpu_memory_used_mb,
        },
        "performance": {
            "average_latency_ms": metrics.average_latency_ms,
            "latency_p95_ms": metrics.latency_p95_ms,
            "success_rate": metrics.success_count / max(metrics.total_requests, 1),
            "fallback_rate": metrics.fallback_count / max(metrics.total_requests, 1),
        },
        "usage": {
            "emotion_distribution": metrics.emotion_distribution,
            "language_distribution": metrics.language_distribution,
        }
    }
```

#### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# TTS request counter
tts_requests_total = Counter(
    'tts_requests_total',
    'Total TTS requests',
    ['status']
)

# TTS latency
tts_latency_seconds = Histogram(
    'tts_latency_seconds',
    'TTS synthesis latency',
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
)

# Fallback usage
tts_fallback_total = Counter(
    'tts_fallback_total',
    'TTS fallback usage',
    ['engine']
)

# GPU memory
tts_gpu_memory_mb = Gauge(
    'tts_gpu_memory_mb',
    'TTS GPU memory usage'
)

@app.get("/metrics")
def metrics_endpoint():
    """Prometheus metrics"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### 8. Testing Integration

Create integration tests:

```python
# tests/integration/test_tts_integration.py
import pytest
from fastapi.testclient import TestClient
from epmssts.main import app

client = TestClient(app)

def test_tts_synthesize_endpoint():
    """Test TTS synthesis endpoint"""
    response = client.post(
        "/api/v2/tts/synthesize",
        json={
            "translated_text": "Hello, how are you today?",
            "target_language": "en",
            "emotion_label": "happy",
            "emotion_confidence": 0.92,
            "translation_confidence": 0.88
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] in ["success", "partial"]
    assert data["audio_path"] is not None
    assert data["latency_ms"] > 0
    assert data["prosody_profile"]["rate_multiplier"] > 1.0  # Happy = faster

def test_full_pipeline():
    """Test complete EPMSSTS pipeline with TTS"""
    # Mock audio file
    with open("test_audio.wav", "rb") as f:
        files = {"audio": ("test.wav", f, "audio/wav")}
        response = client.post(
            "/api/process-audio-full?target_language=es",
            files=files
        )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "transcript" in data
    assert "emotion" in data
    assert "translation" in data
    assert "audio_path" in data
    assert data["status"]["tts"] in ["success", "partial"]

def test_tts_health():
    """Test TTS health endpoint"""
    response = client.get("/api/v2/tts/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["models_loaded"]["primary_tts"] == True
```

Run tests:

```bash
pytest tests/integration/test_tts_integration.py -v
```

## Common Integration Patterns

### Pattern 1: Real-time Voice Translation

```python
@app.websocket("/ws/voice-translate")
async def voice_translate_websocket(websocket: WebSocket, target_lang: str):
    await websocket.accept()
    
    while True:
        # Receive audio chunk
        audio_data = await websocket.receive_bytes()
        
        # Process pipeline
        stt_result = await stt_service.transcribe(audio_data)
        emotion_result = await emotion_service.predict(audio_data, stt_result["transcript"])
        
        translation_request = TranslationRequest(
            transcript=stt_result["transcript"],
            target_lang=target_lang,
            emotion_label=emotion_result["emotion"],
            emotion_confidence=emotion_result["confidence"]
        )
        translation_result = await translation_service.translate(translation_request)
        
        tts_request = TTSRequest(
            translated_text=translation_result.translated_text,
            target_language=target_lang,
            emotion_label=emotion_result["emotion"],
            emotion_confidence=emotion_result["confidence"]
        )
        tts_result = await tts_service.synthesize(tts_request)
        
        # Send audio file bytes
        with open(tts_result.audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        await websocket.send_bytes(audio_bytes)
```

### Pattern 2: Batch TTS Generation

```python
@app.post("/api/tts/batch")
async def synthesize_batch(requests: List[TTSRequest]):
    """Batch TTS synthesis"""
    import asyncio
    
    # Process in parallel
    tasks = [tts_service.synthesize(req) for req in requests]
    responses = await asyncio.gather(*tasks)
    
    return {
        "results": [
            {
                "audio_path": resp.audio_path,
                "status": resp.status,
                "latency_ms": resp.latency_ms
            }
            for resp in responses
        ],
        "total_count": len(responses),
        "success_count": sum(1 for r in responses if r.status == "success")
    }
```

### Pattern 3: Emotion-Controlled Voice Responses

```python
@app.post("/api/chatbot/respond-with-voice")
async def chatbot_voice_response(
    user_message: str,
    detected_emotion: str,
    target_language: str
):
    """Generate chatbot voice response matching user emotion"""
    
    # Generate text response (from chatbot/LLM)
    chatbot_response = generate_chatbot_response(user_message, detected_emotion)
    
    # Synthesize with matching emotion
    tts_request = TTSRequest(
        translated_text=chatbot_response,
        target_language=target_language,
        emotion_label=detected_emotion,  # Match user's emotion
        emotion_confidence=0.9,
        translation_confidence=1.0
    )
    
    tts_result = await tts_service.synthesize(tts_request)
    
    return {
        "text_response": chatbot_response,
        "audio_path": tts_result.audio_path,
        "emotion_used": detected_emotion,
        "prosody": tts_result.prosody_profile.dict()
    }
```

## Troubleshooting

### Issue: Model download fails

**Solution**: Pre-download before deployment

```python
from TTS.api import TTS

# Pre-download XTTS v2
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
print("Model downloaded to ~/.local/share/tts/")
```

### Issue: CUDA out of memory

**Solutions**:
1. Use CPU: `device="cpu"`
2. Disable FP16: `enable_fp16=False`
3. Reduce batch size
4. Use smaller GPU-friendly model

### Issue: Slow synthesis (> 5s)

**Solutions**:
1. Enable GPU: `device="cuda"`
2. Enable FP16: `enable_fp16=True`
3. Use model caching (warm at startup)
4. Check GPU utilization: `nvidia-smi`

### Issue: Silent audio output

**Solution**: Check fallback chain enabled
```python
initialize_tts_service(
    device="cuda",
    # Enable all fallbacks
)
```

The waveform validator catches silent audio and triggers fallback automatically.

### Issue: Audio sounds robotic

**Solution**: Adjust prosody intensity
```python
tts_request = TTSRequest(
    translated_text=text,
    target_language=language,
    emotion_label=emotion,
    emotion_confidence=0.8,
    prosody_intensity=0.7  # Reduce from 1.0 to 0.7 for more natural sound
)
```

### Issue: Missing pyrubberband

**Error**: `ImportError: pyrubberband not found`

**Solution**: Install pyrubberband
```bash
# Install system dependencies first
sudo apt-get install rubberband-cli

# Then install Python wrapper
pip install pyrubberband
```

If unavailable, prosody post-processing is skipped (still works, just less prosody control).

## Next Steps

1. ✅ Complete integration with backend
2. ⏳ Run integration tests
3. ⏳ Monitor TTS metrics in development
4. ⏳ Test all supported languages
5. ⏳ Test all emotion prosody mappings
6. ⏳ Load test (concurrent requests)
7. ⏳ Deploy to production
8. ⏳ Monitor fallback usage

## Support

For integration issues:
- [TTS Service README](README.md)
- Project documentation in `docs/`
- EPMSSTS main documentation

Contact: EPMSSTS development team
