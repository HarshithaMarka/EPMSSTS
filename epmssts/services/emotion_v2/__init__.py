"""
Emotion Intelligence Service v2

Production-grade ensemble-based emotion recognition.

Features:
- Multi-model ensemble (Wav2Vec2, HuBERT, DistilRoBERTa)
- Adaptive Bayesian fusion (NO fixed weights)
- Temperature scaling calibration
- Comprehensive uncertainty quantification
- Real-time drift monitoring
- Edge case handling (whisper, loud anger, flat TTS-like)

Target: < 500ms p95 latency
"""

from .emotion_service import EmotionIntelligenceService
from .routes import router as emotion_router
from .schemas import (
    EmotionAnalysisRequest,
    EmotionAnalysisResponse,
    HealthCheckResponse,
    MetricsSnapshot,
    DriftAlert,
    EmotionLabel,
    AnalysisStatus,
)
from .exceptions import (
    EmotionServiceError,
    AudioModelLoadError,
    TextModelLoadError,
    ModelInferenceError,
    InvalidAudioFeaturesError,
    QualityScoreTooLowError,
    DurationTooShortError,
    CalibrationError,
    ConfidenceCollapseError,
    FusionError,
    EnsembleDisagreementError,
    NeutralCollapseAlertError,
    UncertaintyTooHighError,
    LowConfidenceOutputError,
)

__all__ = [
    # Main service
    "EmotionIntelligenceService",
    "emotion_router",
    
    # Schemas
    "EmotionAnalysisRequest",
    "EmotionAnalysisResponse",
    "HealthCheckResponse",
    "MetricsSnapshot",
    "DriftAlert",
    "EmotionLabel",
    "AnalysisStatus",
    
    # Exceptions
    "EmotionServiceError",
    "AudioModelLoadError",
    "TextModelLoadError",
    "ModelInferenceError",
    "InvalidAudioFeaturesError",
    "QualityScoreTooLowError",
    "DurationTooShortError",
    "CalibrationError",
    "ConfidenceCollapseError",
    "FusionError",
    "EnsembleDisagreementError",
    "NeutralCollapseAlertError",
    "UncertaintyTooHighError",
    "LowConfidenceOutputError",
]

__version__ = "2.0.0"
