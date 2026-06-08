# Translation Service v2 - Integration Guide

This guide explains how to integrate the Translation Intelligence Service v2 into the EPMSSTS backend.

## Integration Steps

### 1. Update Main FastAPI Application

Edit your main FastAPI application file (likely `epmssts/main.py` or `main.py`):

```python
from fastapi import FastAPI
from epmssts.services.translation_v2.routes import router as translation_router, initialize_translation_service

app = FastAPI(title="EPMSSTS API")

# Startup event: Initialize translation service
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    
    # Initialize Translation Service v2
    initialize_translation_service(
        model_name="facebook/nllb-200-distilled-600M",
        device="cuda",  # Use "cpu" if no GPU available
        fasttext_model_path=None  # Auto-download FastText model
    )
    
    print("✅ Translation Service v2 initialized")

# Include translation routes
app.include_router(translation_router)
```

### 2. Update Requirements

Add to `requirements.txt`:

```txt
# Translation Intelligence v2 dependencies
transformers>=4.35.0
torch>=2.0.0
fasttext>=0.9.2
langdetect>=1.0.9
sentencepiece>=0.1.99  # Required for NLLB tokenizer
```

Install:

```bash
pip install -r requirements.txt
```

### 3. Connect to Existing Pipeline

#### Option A: As Standalone Service

Translation service can be called independently:

```python
from epmssts.services.translation_v2 import TranslationService, TranslationRequest

# In your endpoint handler
@app.post("/translate")
async def translate_endpoint(data: dict):
    request = TranslationRequest(
        transcript=data["text"],
        target_lang=data["target_language"],
        emotion_label=data.get("emotion"),
        emotion_confidence=data.get("emotion_confidence"),
    )
    
    response = await translation_service.translate(request)
    return response
```

#### Option B: Integrated with Full EPMSSTS Pipeline

Connect translation after STT and Emotion services:

```python
# Example full pipeline endpoint
@app.post("/api/process-audio")
async def process_audio_full_pipeline(audio: UploadFile, target_lang: str):
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
    
    # Step 4: Translation (NEW)
    translation_request = TranslationRequest(
        transcript=transcript,
        target_lang=target_lang,
        emotion_label=emotion_label,
        emotion_confidence=emotion_confidence,
        stt_confidence=stt_confidence,
        request_id=f"req_{uuid.uuid4()}"
    )
    
    translation_result = await translation_service.translate(translation_request)
    
    # Return combined results
    return {
        "transcript": transcript,
        "emotion": emotion_label,
        "translation": translation_result.translated_text,
        "translation_confidence": translation_result.confidence_metrics.overall_confidence,
        "emotion_preserved": translation_result.emotion_metrics.preservation_score,
        "status": translation_result.status
    }
```

### 4. Environment Configuration

Create `.env` file or set environment variables:

```bash
# Translation Service Configuration
TRANSLATION_MODEL_NAME=facebook/nllb-200-distilled-600M
TRANSLATION_DEVICE=cuda
TRANSLATION_ENABLE_DRIFT_MONITORING=true

# Quality Thresholds
TRANSLATION_MIN_CONFIDENCE=0.75
TRANSLATION_MIN_EMOTION_PRESERVATION=0.70
TRANSLATION_MIN_STT_CONFIDENCE=0.4

# Drift Monitoring
TRANSLATION_CONFIDENCE_DRIFT_THRESHOLD=0.15
TRANSLATION_EMOTION_DRIFT_THRESHOLD=0.20
TRANSLATION_HIGH_RETRY_RATE_THRESHOLD=0.20
```

Load in Python:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    translation_model_name: str = "facebook/nllb-200-distilled-600M"
    translation_device: str = "cuda"
    translation_min_confidence: float = 0.75
    
    class Config:
        env_file = ".env"

settings = Settings()

# Use in initialization
initialize_translation_service(
    model_name=settings.translation_model_name,
    device=settings.translation_device,
)
```

### 5. Frontend Integration

Update frontend to call new translation endpoint:

```javascript
// Example: Translate button handler
async function translateText(text, targetLanguage, emotion) {
    const response = await fetch('/api/v2/translation/translate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            transcript: text,
            target_lang: targetLanguage,
            emotion_label: emotion.label,
            emotion_confidence: emotion.confidence
        })
    });
    
    const result = await response.json();
    
    // Display translation
    document.getElementById('translated-text').textContent = result.translated_text;
    
    // Show confidence metrics
    document.getElementById('confidence').textContent = 
        `Confidence: ${(result.confidence_metrics.overall_confidence * 100).toFixed(1)}%`;
    
    // Show emotion preservation
    document.getElementById('emotion-preserved').textContent = 
        `Emotion preserved: ${(result.emotion_metrics.preservation_score * 100).toFixed(1)}%`;
}
```

### 6. Monitoring Integration

#### Prometheus Metrics

Add metrics export endpoint:

```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Define metrics
translation_requests = Counter(
    'translation_requests_total',
    'Total translation requests',
    ['status']
)

translation_confidence = Histogram(
    'translation_confidence',
    'Translation confidence scores'
)

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

#### Dashboard Integration

Connect to existing monitoring dashboard:

```python
@app.get("/api/dashboard/translation-metrics")
async def get_translation_dashboard_metrics():
    """Get translation metrics for dashboard"""
    service = get_translation_service()
    metrics = service.get_metrics()
    alerts = service.get_drift_alerts()
    
    return {
        "metrics": {
            "total_requests": metrics.total_requests,
            "success_rate": metrics.success_count / max(metrics.total_requests, 1),
            "average_confidence": metrics.average_confidence,
            "average_emotion_preservation": metrics.average_emotion_preservation,
            "retry_rate": metrics.retry_rate,
            "p95_latency_ms": metrics.latency_p95_ms
        },
        "alerts": [
            {
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message
            }
            for alert in alerts
        ],
        "language_distribution": metrics.language_distribution
    }
```

### 7. Testing Integration

Create integration tests:

```python
# tests/integration/test_translation_integration.py
import pytest
from fastapi.testclient import TestClient
from epmssts.main import app

client = TestClient(app)

def test_translation_endpoint():
    """Test translation endpoint integration"""
    response = client.post(
        "/api/v2/translation/translate",
        json={
            "transcript": "I am very happy with this service!",
            "target_lang": "spa_Latn",
            "emotion_label": "happy",
            "emotion_confidence": 0.92
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert len(data["translated_text"]) > 0
    assert data["confidence_metrics"]["overall_confidence"] > 0.7
    assert data["emotion_metrics"]["preservation_score"] > 0.6

def test_health_endpoint():
    """Test translation health endpoint"""
    response = client.get("/api/v2/translation/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["models_loaded"]["translation_engine"] == True
```

Run tests:

```bash
pytest tests/integration/test_translation_integration.py -v
```

## Common Integration Patterns

### Pattern 1: Real-time Chat Translation

```python
@app.websocket("/ws/chat/translate")
async def chat_translate_websocket(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        # Receive message
        data = await websocket.receive_json()
        
        # Translate
        request = TranslationRequest(
            transcript=data["message"],
            target_lang=data["target_lang"],
            emotion_label=data.get("emotion"),
            emotion_confidence=data.get("emotion_confidence")
        )
        
        response = await translation_service.translate(request)
        
        # Send back translation
        await websocket.send_json({
            "original": data["message"],
            "translated": response.translated_text,
            "confidence": response.confidence_metrics.overall_confidence
        })
```

### Pattern 2: Batch Translation

```python
@app.post("/api/translate-batch")
async def translate_batch(requests: List[TranslationRequest]):
    """Translate multiple texts in parallel"""
    tasks = [translation_service.translate(req) for req in requests]
    responses = await asyncio.gather(*tasks)
    return responses
```

### Pattern 3: Translation with Context History

```python
@app.post("/api/translate-with-history")
async def translate_with_history(
    text: str,
    target_lang: str,
    session_id: str
):
    """Translate with conversation context"""
    # Get conversation history from session
    history = get_conversation_history(session_id)
    
    # Use last 2 messages as context
    context_window = [msg["text"] for msg in history[-2:]]
    
    request = TranslationRequest(
        transcript=text,
        target_lang=target_lang,
        context_window=context_window
    )
    
    response = await translation_service.translate(request)
    
    # Save to history
    save_to_conversation_history(session_id, text, response.translated_text)
    
    return response
```

## Migration from Translation v1

If you have an existing translation service (v1), migrate gradually:

### Step 1: Parallel Deployment

Run both services side-by-side:

```python
# Keep v1 service
from epmssts.services.translation import TranslationService as TranslationServiceV1

# Add v2 service
from epmssts.services.translation_v2 import TranslationService as TranslationServiceV2

# Initialize both
translation_service_v1 = TranslationServiceV1()
translation_service_v2 = TranslationServiceV2()
```

### Step 2: A/B Testing

```python
import random

@app.post("/api/translate")
async def translate_with_ab_test(request: TranslationRequest):
    # 50/50 split
    use_v2 = random.random() < 0.5
    
    if use_v2:
        response = await translation_service_v2.translate(request)
        response.metadata = {"version": "v2"}
    else:
        response = await translation_service_v1.translate(request)
        response.metadata = {"version": "v1"}
    
    # Log metrics for comparison
    log_translation_metrics(response, version="v2" if use_v2 else "v1")
    
    return response
```

### Step 3: Gradual Rollout

```python
# Traffic percentage to v2 (increase over time)
V2_TRAFFIC_PERCENTAGE = 0.10  # Start with 10%

@app.post("/api/translate")
async def translate_gradual_rollout(request: TranslationRequest):
    if random.random() < V2_TRAFFIC_PERCENTAGE:
        return await translation_service_v2.translate(request)
    else:
        return await translation_service_v1.translate(request)
```

### Step 4: Full Migration

Once v2 proves stable:

```python
# Remove v1
# from epmssts.services.translation import TranslationService as TranslationServiceV1

# Use only v2
from epmssts.services.translation_v2 import TranslationService

translation_service = TranslationService()
```

## Troubleshooting

### Issue: Model download fails

**Solution**: Pre-download models before deployment

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

model_name = "facebook/nllb-200-distilled-600M"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
```

### Issue: CUDA out of memory

**Solutions**:
1. Use CPU mode: `device="cpu"`
2. Reduce batch size in translation engine
3. Use smaller model: `facebook/nllb-200-distilled-1.3B` → `facebook/nllb-200-distilled-600M`

### Issue: Slow response times

**Solutions**:
1. Enable GPU: `device="cuda"`
2. Reduce beam size: `beam_size=4` → `beam_size=2`
3. Use caching for repeated translations
4. Consider batch processing for multiple requests

### Issue: Low emotion preservation scores

**Solutions**:
1. Lower threshold: `min_emotion_preservation=0.60` (from 0.70)
2. Verify emotion keywords are present in source text
3. Check if target language has emotion keyword dictionary

## Next Steps

1. ✅ Complete integration with existing backend
2. ⏳ Run integration tests
3. ⏳ Monitor metrics in development
4. ⏳ A/B test against v1 (if applicable)
5. ⏳ Deploy to production
6. ⏳ Monitor drift alerts
7. ⏳ Fine-tune quality thresholds based on real data

## Support

For integration issues, check:
- [Translation Service v2 README](README.md)
- Project documentation in `docs/`
- EPMSSTS main documentation

Contact: EPMSSTS development team
