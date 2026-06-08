# Emotion Intelligence Service v2

## Executive Summary

Production-grade **Ensemble-Based Emotion Recognition** service with adaptive fusion, calibration, uncertainty quantification, and drift monitoring.

**NOT a simple classifier** - enterprise ML system designed for real-world deployment.

---

## Key Features

### 🎯 Core Capabilities
- **Multi-Model Ensemble**: Wav2Vec2 (primary audio) + HuBERT (secondary audio) + DistilRoBERTa (text)
- **Adaptive Bayesian Fusion**: NO fixed weights - dynamic α/β computed per request
- **Temperature Scaling Calibration**: Prevents overconfidence, neutral collapse, volume bias
- **Comprehensive Uncertainty**: Entropy, margin, dispersion, disagreement scoring
- **Real-Time Drift Monitoring**: Alerts on neutral collapse, class imbalance, confidence degradation

### ⚡ Performance
- **Target Latency**: < 500ms (p95)
- **Concurrency**: 10 concurrent requests max
- **Test Coverage**: > 85%
- **Error Handling**: 14 structured error codes (ERR_EMO_001 - ERR_EMO_052)

### 🛡️ Production-Ready
- Edge case handling (whisper sadness, loud anger, TTS-like audio)
- Uncertainty flagging for downstream UI
- Drift alerts for model degradation
- Comprehensive observability (metrics, health checks)

---

## Architecture

### Pipeline Flow

```
Input (Audio + Text)
    ↓
[Validation]
    ↓
[Audio Ensemble Inference] ← Wav2Vec2 + HuBERT
    ↓
[Text Model Inference] ← DistilRoBERTa
    ↓
[Calibration] ← Temperature Scaling, Neutral Penalty, Volume Correction
    ↓
[Adaptive Fusion] ← Bayesian Fusion: P(final) ∝ P(audio)^α × P(text)^β
    ↓
[Uncertainty Estimation] ← Entropy, Margin, Dispersion, Disagreement
    ↓
[Drift Monitoring] ← Record for distribution tracking
    ↓
Output (Label + Confidence + Uncertainty + Explainability)
```

### Components

#### 1. **Audio Ensemble** (`audio_models.py`)
- **Primary**: Wav2Vec2 (ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition)
- **Secondary**: HuBERT (superb/hubert-base-superb-er)
- Returns: Probabilities, entropy, confidence, inference time

#### 2. **Text Model** (`text_model.py`)
- **Model**: DistilRoBERTa (j-hartmann/emotion-english-distilroberta-base)
- **Features**: Language detection, label mapping, empty text handling
- Returns: Probabilities, entropy, confidence

#### 3. **Calibration Layer** (`calibration.py`)
- **Temperature Scaling**: T_audio=1.5, T_text=1.3 (conservative)
- **Neutral Penalty**: Reduce neutral by 0.1, cap at 0.7
- **Volume Bias Correction**: Boost sad on low volume (whisper detection)
- **Per-Class Adjustments**: Balance class distribution

#### 4. **Adaptive Fusion Engine** (`fusion.py`)
- **Formula**: `P(final) ∝ P(audio)^α × P(text)^β`
- **Dynamic Weights**: Computed from 5 factors:
  1. Audio entropy (low entropy → higher audio weight)
  2. Text entropy (low entropy → higher text weight)
  3. STT confidence (high confidence → higher text weight)
  4. Audio quality score (high quality → higher audio weight)
  5. Energy band (high energy → higher audio weight)
- **NO Fixed 65/35 Rule**: Every request gets custom weights

#### 5. **Uncertainty Estimator** (`uncertainty.py`)
- **Metrics**:
  1. Shannon entropy (distribution spread)
  2. Max probability margin (top-2 gap)
  3. Confidence dispersion (inter-model variance)
  4. Disagreement score (label consistency)
- **Flagging**: Alert if ANY metric exceeds threshold

#### 6. **Drift Monitor** (`drift_monitor.py`)
- **Tracks**:
  - Emotion distribution (sliding window)
  - Average entropy trends
  - Average confidence trends
  - Uncertainty flag rate
- **Alerts**:
  - Neutral collapse (>70% neutral)
  - Class imbalance (>80% single class)
  - Entropy spike (>50% above baseline)
  - Confidence degradation (<30% average)
  - High uncertainty rate (>50% flagged)

---

## API Endpoints

### 1. POST `/emotion/v2/analyze`

**Analyze emotion from audio + text**

**Request Body**:
```json
{
  "audio_id": "audio_123",
  "waveform_ref": "storage://waveforms/audio_123.wav",
  "mel_features_ref": "storage://mels/audio_123.npy",
  "transcript": "I am very happy today",
  "stt_confidence": 0.95,
  "energy_band": "medium",
  "quality_score": 0.85,
  "duration_seconds": 2.5,
  "min_confidence_threshold": 0.6,
  "max_entropy_threshold": 1.0
}
```

**Response**:
```json
{
  "audio_id": "audio_123",
  "status": "success",
  "label": "happy",
  "confidence": 0.82,
  "probabilities": {
    "angry": 0.05,
    "happy": 0.82,
    "neutral": 0.08,
    "sad": 0.05
  },
  "uncertainty_metrics": {
    "entropy": 0.64,
    "max_prob_margin": 0.74,
    "confidence_dispersion": 0.02,
    "disagreement_score": 0.0,
    "uncertainty_flag": false
  },
  "model_predictions": [
    {
      "probabilities": {...},
      "entropy": 0.8,
      "model_confidence": 0.75,
      "model_name": "wav2vec2",
      "inference_time_ms": 120.5
    },
    {
      "probabilities": {...},
      "entropy": 0.6,
      "model_confidence": 0.85,
      "model_name": "distilroberta",
      "inference_time_ms": 85.3
    }
  ],
  "calibration_info": {
    "temperature": 1.5,
    "class_adjustments": {"neutral": -0.1, "sad": 0.05},
    "neutral_penalty_applied": false,
    "volume_bias_corrected": false
  },
  "fusion_weights": {
    "audio_weight": 0.58,
    "text_weight": 0.42,
    "fusion_method": "bayesian",
    "weight_factors": {
      "entropy_audio": 0.68,
      "entropy_text": 0.55,
      "stt_confidence": 0.95,
      "quality_score": 0.85,
      "energy_band_boost": 0.0
    }
  },
  "processing_time_ms": 320.5,
  "audio_inference_time_ms": 120.5,
  "text_inference_time_ms": 85.3,
  "fusion_time_ms": 2.1
}
```

### 2. GET `/emotion/v2/health`

**Get service health status**

**Response**:
```json
{
  "status": "healthy",
  "models_loaded": {
    "audio_primary": true,
    "audio_secondary": true,
    "text": true
  },
  "total_requests": 1523,
  "error_rate": 0.012,
  "neutral_rate": 0.32,
  "uncertainty_rate": 0.15,
  "active_alerts": 0
}
```

### 3. GET `/emotion/v2/metrics`

**Get comprehensive metrics snapshot**

**Response**:
```json
{
  "total_requests": 1523,
  "emotion_distribution": {
    "angry": 0.18,
    "happy": 0.35,
    "neutral": 0.32,
    "sad": 0.15
  },
  "average_entropy": 0.82,
  "average_confidence": 0.71,
  "uncertainty_rate": 0.15,
  "neutral_rate": 0.32,
  "active_alerts": 0,
  "latency_p50_ms": 200.0,
  "latency_p95_ms": 450.0,
  "latency_p99_ms": 600.0
}
```

### 4. GET `/emotion/v2/drift-alerts`

**Get active drift alerts**

**Response**:
```json
{
  "active_alerts": [
    {
      "alert_type": "neutral_collapse",
      "severity": "high",
      "metric_value": 0.73,
      "threshold": 0.70,
      "message": "Neutral collapse detected: 73.0% of predictions are neutral",
      "timestamp": "2024-01-15T14:30:00"
    }
  ],
  "alert_count": 1
}
```

### 5. GET `/emotion/v2/model-info`

**Get model information**

**Response**:
```json
{
  "device": "cpu",
  "models": {
    "audio_primary": "wav2vec2-lg-xlsr-en-speech-emotion-recognition",
    "audio_secondary": "hubert-base-superb-er",
    "text": "emotion-english-distilroberta-base"
  },
  "inference_count": 1523,
  "error_count": 18,
  "calibration": {
    "method": "temperature_scaling",
    "neutral_penalty": true,
    "volume_bias_correction": true
  },
  "fusion": {
    "method": "bayesian",
    "adaptive_weights": true,
    "fixed_weights": false
  }
}
```

---

## Edge Cases

### 1. **Whisper Sadness**
**Problem**: Low volume sad speech misclassified as neutral  
**Solution**: Volume bias correction - boost sad probability on low volume/energy

### 2. **Loud Anger**
**Problem**: High volume angry speech with clipping  
**Solution**: High energy band boosts audio weight in fusion

### 3. **Flat TTS-Like Audio**
**Problem**: Synthetic/monotone audio lacks emotion signal  
**Solution**: Uncertainty flagging + rely more on text model

### 4. **Code-Switching / Non-English**
**Problem**: Text model trained on English  
**Solution**: Language detection + fallback to audio-dominant fusion

### 5. **Extremely Short Utterances**
**Problem**: < 0.5s audio has insufficient signal  
**Solution**: Validation error (DurationTooShortError)

### 6. **Low Audio Quality**
**Problem**: Noisy/distorted audio  
**Solution**: Quality score check + text-dominant fusion

---

## Error Codes

| Code | Error | Trigger |
|------|-------|---------|
| ERR_EMO_001 | AudioModelLoadError | Audio model fails to load |
| ERR_EMO_002 | TextModelLoadError | Text model fails to load |
| ERR_EMO_003 | ModelInferenceError | Inference error |
| ERR_EMO_011 | InvalidAudioFeaturesError | Invalid audio input |
| ERR_EMO_012 | QualityScoreTooLowError | Quality score < 0.3 |
| ERR_EMO_013 | DurationTooShortError | Duration < 0.5s |
| ERR_EMO_021 | CalibrationError | Calibration failure |
| ERR_EMO_022 | ConfidenceCollapseError | All probabilities too low |
| ERR_EMO_031 | FusionError | Fusion computation error |
| ERR_EMO_032 | EnsembleDisagreementError | Models strongly disagree |
| ERR_EMO_041 | NeutralCollapseAlertError | Neutral rate > 70% |
| ERR_EMO_051 | UncertaintyTooHighError | Entropy exceeds threshold |
| ERR_EMO_052 | LowConfidenceOutputError | Confidence below threshold |

---

## Installation

### Requirements
```bash
pip install torch transformers librosa numpy scipy
```

### Initialize Service
```python
from epmssts.services.emotion_v2 import EmotionIntelligenceService

service = EmotionIntelligenceService(device="cpu")
await service.initialize()
```

### FastAPI Integration
```python
from fastapi import FastAPI
from epmssts.services.emotion_v2 import emotion_router

app = FastAPI()
app.include_router(emotion_router)
```

---

## Testing

### Run Tests
```bash
pytest epmssts/services/emotion_v2/tests/test_emotion_service.py -v
```

### Test Coverage
- Audio models: Initialization, inference, entropy computation
- Text model: Initialization, label mapping, empty text handling
- Calibration: Temperature scaling, neutral collapse, volume bias
- Fusion: Adaptive weights, Bayesian formula, disagreement detection
- Uncertainty: Entropy, margin, dispersion, flagging
- Drift: Neutral collapse, class imbalance, entropy spike
- Integration: Full pipeline, edge cases, performance

**Target**: > 85% coverage

---

## Configuration

### Calibration Config
```python
from epmssts.services.emotion_v2.calibration import CalibrationConfig

config = CalibrationConfig(
    temperature_audio=1.5,        # Conservative audio scaling
    temperature_text=1.3,          # Conservative text scaling
    neutral_penalty=0.1,           # Reduce neutral by 0.1
    max_neutral_prob=0.7,          # Cap neutral at 0.7
    volume_bias_threshold=0.3,     # Trigger whisper correction
    sad_boost_on_low_volume=0.15,  # Boost sad on low volume
    min_confidence_floor=0.25,     # Minimum winning probability
)
```

### Fusion Config
```python
from epmssts.services.emotion_v2.fusion import FusionConfig

config = FusionConfig(
    entropy_weight_factor=0.3,          # Entropy influence
    stt_confidence_weight_factor=0.25,  # STT confidence influence
    quality_score_weight_factor=0.2,    # Audio quality influence
    energy_band_weight_factor=0.15,     # Energy band influence
    max_kl_divergence=1.5,              # Disagreement alert threshold
    default_fusion_method="bayesian",   # Fusion method
    prior_audio_weight=0.65,            # Starting audio weight
    prior_text_weight=0.35,             # Starting text weight
)
```

---

## Monitoring

### Key Metrics
1. **Emotion Distribution**: Track class balance
2. **Neutral Rate**: Alert if > 70% (collapse)
3. **Uncertainty Rate**: Alert if > 50% (signal quality issues)
4. **Average Entropy**: Track calibration effectiveness
5. **Average Confidence**: Alert if < 30% (degradation)
6. **Latency**: Target p95 < 500ms

### Drift Alerts
- **Neutral Collapse**: Check if neutral dominates (>70%)
- **Class Imbalance**: Check if single class >80%
- **Entropy Spike**: Check if entropy >50% above baseline
- **Confidence Drop**: Check if average confidence <30%
- **Uncertainty Rate**: Check if >50% flagged

---

## Deployment

### Docker
```bash
docker build -t emotion-service-v2 .
docker run -p 8000:8000 emotion-service-v2
```

### Production Checklist
- [ ] GPU enabled (CUDA) for faster inference
- [ ] Model files cached (avoid re-download)
- [ ] Concurrency limit configured (default: 10)
- [ ] Monitoring/alerting on drift metrics
- [ ] Health check endpoint monitored
- [ ] Error rate < 2%
- [ ] Latency p95 < 500ms
- [ ] Test coverage > 85%

---

## License

MIT License - See LICENSE file for details.

---

## Support

For issues or questions, contact the EPMSSTS team or file a GitHub issue.

---

**Module 3 Status**: ✅ **COMPLETE**  
**Version**: 2.0.0  
**Last Updated**: 2024-01-15
