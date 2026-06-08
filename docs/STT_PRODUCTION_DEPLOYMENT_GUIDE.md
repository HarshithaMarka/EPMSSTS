# STT Service - Production Deployment Guide

Production-grade deployment, configuration, and operational guidelines for the Speech-to-Text (STT) microservice.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation & Setup](#installation--setup)
3. [Configuration](#configuration)
4. [Deployment](#deployment)
5. [Performance Tuning](#performance-tuning)
6. [Monitoring & Observability](#monitoring--observability)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)
9. [Operational Runbooks](#operational-runbooks)

## System Requirements

### Hardware

**Minimum (CPU-only):**
- CPU: 4+ cores
- RAM: 8GB
- Storage: 5GB
- Network: 100Mbps

**Recommended (GPU):**
- GPU: NVIDIA A100 / H100 / RTX 4090 (8GB+ VRAM)
- CPU: 8+ cores
- RAM: 16GB
- Storage: 10GB (model cache)
- Network: 1Gbps

**GPU Models Tested:**
- NVIDIA GeForce RTX 3090 (24GB)
- NVIDIA A100 (40GB)
- Tesla T4 (16GB)
- NVIDIA RTX 4090 (24GB)

### Software

- Python: 3.10, 3.11, 3.12
- PyTorch: 2.0.0+
- CUDA: 11.8+ (GPU only)
- cuDNN: 8.6+ (GPU only)

### Docker

```dockerfile
FROM pytorch/pytorch:2.0-cuda11.8-cudnn8-runtime

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY epmssts /app/epmssts
WORKDIR /app

EXPOSE 8000
CMD ["uvicorn", "epmssts.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Installation & Setup

### 1. Python Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. GPU Setup (Optional)

```bash
# Verify CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Install proper PyTorch version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. Download Models

```python
# Manual download (optional, auto-downloads on first use)
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cuda", compute_type="float16")
```

## Configuration

### Environment Variables

```env
# STT Service
STT_MODEL_SIZE=medium              # tiny, base, small, medium, large, large-v3
STT_PREFER_GPU=true                # true/false
STT_MAX_CONCURRENT=4               # Concurrent inference jobs
STT_QUEUE_TIMEOUT=30               # Seconds to wait in queue
STT_INFERENCE_TIMEOUT=60           # Seconds for inference
STT_CONFIDENCE_THRESHOLD=0.5       # Default min confidence [0-1]
STT_NO_SPEECH_THRESHOLD=0.3        # Default max no-speech prob [0-1]

# Logging
LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                    # json or text
LOG_FILE=/var/log/stt/service.log  # Log file path

# Performance
STT_NUM_WORKERS=2                  # Model inference workers
STT_CPU_THREADS=4                  # CPU threads per worker
```

### Python Configuration

```python
# epmssts/config/stt_config.py
from pydantic import BaseSettings

class SttConfig(BaseSettings):
    # Model
    model_size: str = "medium"
    
    # Device
    prefer_gpu: bool = True
    
    # Concurrency
    max_concurrent_inferences: int = 4
    queue_timeout_seconds: float = 30.0
    inference_timeout_seconds: float = 60.0
    
    # Quality
    default_confidence_threshold: float = 0.5
    default_no_speech_threshold: float = 0.3
    
    # Performance
    num_workers: int = 2
    cpu_threads: int = 4
    
    class Config:
        env_prefix = "STT_"

config = SttConfig()
```

### FastAPI Integration

```python
# epmssts/api/main.py
from fastapi import FastAPI
from epmssts.services.stt import SpeechToTextService
import asyncio

app = FastAPI(title="EPMSSTS")

# Global service instance
stt_service: SpeechToTextService = None

@app.on_event("startup")
async def startup():
    global stt_service
    stt_service = SpeechToTextService(
        model_size="medium",
        device_prefer_gpu=True,
        max_concurrent_inferences=4,
    )
    await stt_service.initialize()
    print("STT service initialized")

@app.on_event("shutdown")
async def shutdown():
    # Cleanup
    pass
```

## Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  stt:
    build: .
    ports:
      - "8000:8000"
    environment:
      STT_MODEL_SIZE: medium
      STT_PREFER_GPU: "true"
      LOG_LEVEL: INFO
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
      - ./logs:/var/log/stt
    gpus:
      - all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stt-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: stt-service
  template:
    metadata:
      labels:
        app: stt-service
    spec:
      containers:
      - name: stt
        image: epmssts:latest
        ports:
        - containerPort: 8000
        env:
        - name: STT_MODEL_SIZE
          value: "medium"
        - name: STT_MAX_CONCURRENT
          value: "4"
        resources:
          limits:
            nvidia.com/gpu: "1"
            memory: "16Gi"
            cpu: "4"
          requests:
            nvidia.com/gpu: "1"
            memory: "8Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /stt/health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
```

### Systemd Service

```ini
# /etc/systemd/system/stt-service.service
[Unit]
Description=EPMSSTS STT Service
After=network.target

[Service]
Type=simple
User=stt-service
Environment="PATH=/opt/stt-venv/bin"
ExecStart=/opt/stt-venv/bin/python -m uvicorn epmssts.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl start stt-service
sudo systemctl enable stt-service
sudo systemctl status stt-service
```

## Performance Tuning

### GPU Optimization

1. **Model Size Selection:**
   - `medium` (769M): Recommended, good quality + speed
   - `large`: Best quality, needs 12GB VRAM
   - Use `large-v3` for highest accuracy with more languages

2. **Quantization:**
   - `float16` on GPU: Fastest, ~2x speedup, minimal quality loss
   - `int8` on CPU: Smaller memory footprint
   - `float32`: Maximum quality, slower

3. **Batch Processing:**
   - Set `max_concurrent_inferences=4-8` for GPU
   - Set `max_concurrent_inferences=1-2` for CPU

### CPU Optimization

```python
# CPU-specific settings
service = SpeechToTextService(
    model_size="small",  # Use smaller model on CPU
    max_concurrent_inferences=1,
    # Use int8 quantization automatically
)
```

### Memory Optimization

```bash
# Monitor GPU memory
nvidia-smi -l 1  # Update every 1 second

# Clear cache if needed
python -c "import torch; torch.cuda.empty_cache()"
```

### Caching

Models are cached in `~/.cache/huggingface/hub/`:
```bash
# Pre-download models
python -c "from faster_whisper import WhisperModel; \
    WhisperModel('medium', device='cuda', compute_type='float16')"

# Monitor cache size
du -sh ~/.cache/huggingface/hub/
```

## Monitoring & Observability

### Metrics Collection

The service exposes Prometheus-compatible metrics:

```python
@app.get("/stt/metrics")
async def stt_metrics():
    return stt_service.get_metrics()
```

**Key Metrics:**
- `total_requests`: Total requests processed
- `success_rate`: Successful transcriptions %
- `average_latency_ms`: Average transcription time
- `gpu_used_percentage`: GPU usage %
- `error_distribution`: Error counts by type
- `language_distribution`: Supported languages used

### Health Checks

```python
@app.get("/stt/health")
async def stt_health():
    return stt_service.get_health_status()
```

**Response:**
```json
{
  "status": "healthy|degraded|unhealthy",
  "model_loaded": true,
  "model_name": "whisper-medium",
  "device": "gpu",
  "gpu_available": true,
  "average_latency_ms": 245.5,
  "error_rate": 0.01,
  "total_requests": 10000,
  "queue_size": 0,
  "concurrent_capacity": 4
}
```

### Logging

Structured JSON logs for observability:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "stt",
  "message": "Transcription successful",
  "request_id": "stt-a1b2c3d4",
  "metrics": {
    "latency_ms": 245,
    "confidence": 0.92,
    "device": "gpu"
  }
}
```

### Alerting

Prometheus rules (sample):

```yaml
groups:
- name: stt_alerts
  rules:
  - alert: SttHighErrorRate
    expr: stt_error_rate > 0.05
    for: 5m
    annotations:
      summary: "STT error rate > 5%"

  - alert: SttQueueFull
    expr: stt_queue_size >= stt_max_queue_size
    for: 1m
    annotations:
      summary: "STT queue is full"

  - alert: SttHighLatency
    expr: stt_p95_latency_ms > 5000
    for: 5m
    annotations:
      summary: "STT p95 latency > 5 seconds"
```

## Scaling

### Horizontal Scaling

```yaml
# Load balance across 3 STT services
upstream stt_backend {
    server stt-1:8000;
    server stt-2:8000;
    server stt-3:8000;
}

server {
    location /stt/ {
        proxy_pass http://stt_backend;
    }
}
```

### Vertical Scaling

1. **Upgrade GPU:**
   - T4 (16GB) → A100 (40GB)
   - Increases throughput ~3-4x

2. **Increase Model Size:**
   - Change `medium` → `large`
   - Better quality, +50% latency

3. **Increase Concurrent Requests:**
   - Adjust `max_concurrent_inferences`
   - Monitor GPU memory and queue size

### Load Shedding

```python
# In SttRequest validation
if stt_service.queue_size > stt_service.max_concurrent_inferences * 2:
    return HTTPException(status_code=503, detail="Service overloaded")
```

## Troubleshooting

### Common Issues

#### 1. CUDA Out of Memory

**Symptoms:** `RuntimeError: CUDA out of memory`

**Solutions:**
```bash
# Reduce concurrent inferences
STT_MAX_CONCURRENT=2

# Use smaller model
STT_MODEL_SIZE=small

# Use int8 quantization
# (automatically selected on CPU)

# Clear cache
python -c "import torch; torch.cuda.empty_cache()"
```

#### 2. Inference Timeout

**Symptoms:** Requests timeout at 60+ seconds

**Solutions:**
```python
# Increase timeout
STT_INFERENCE_TIMEOUT=120

# Use smaller model
STT_MODEL_SIZE=small

# Check audio duration
# (very long audio naturally takes longer)
```

#### 3. Poor Transcription Quality

**Symptoms:** Low confidence scores, hallucinations

**Solutions:**
```python
# Lower confidence threshold temporarily
confidence_threshold=0.3

# Review audio quality
# - Background noise?
# - Compression artifacts?
# - Non-native speaker?

# Try different model
STT_MODEL_SIZE=large
```

#### 4. GPU Not Being Used

**Symptoms:** All requests using CPU despite GPU available

**Solutions:**
```bash
# Verify CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Check device preference
STT_PREFER_GPU=true

# Restart service to re-detect GPU
```

### Debug Commands

```bash
# Check GPU status
nvidia-smi

# Monitor service logs
tail -f /var/log/stt/service.log | jq .

# Test inference manually
curl -X POST http://localhost:8000/stt/transcribe \
  -H "Content-Type: application/json" \
  -d @request.json

# Check health
curl http://localhost:8000/stt/health | jq .

# Get metrics
curl http://localhost:8000/spt/metrics | jq .
```

## Operational Runbooks

### Daily Checks

```bash
# Check service health
curl -s http://localhost:8000/stt/health | jq '.status'

# Review error rate (should be < 1%)
curl -s http://localhost:8000/stt/metrics | jq '.error_distribution'

# Check average latency (should be < 500ms for 5s audio)
curl -s http://localhost:8000/stt/metrics | jq '.average_latency_ms'
```

### Weekly Maintenance

```bash
# Review logs for patterns
grep "ERROR\|WARNING" /var/log/stt/service.log | tail -100

# Check GPU memory leaks
nvidia-smi dmon

# Restart service if needed
sudo systemctl restart stt-service
```

### Monthly Optimization

1. Analyze language distribution
2. Review error distribution
3. Assess performance metrics
4. Update model if newer version available
5. Plan scaling needs

## Support & Documentation

- Service README: `epmssts/services/stt/README.md`
- API Documentation: `http://localhost:8000/docs`
- Error Codes: `epmssts/services/stt/exceptions.py`
- Issues & Bugs: GitHub Issues
