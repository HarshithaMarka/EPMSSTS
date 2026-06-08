"""
Translation Intelligence Service v2

Production-grade translation layer with:
- Context-aware translation (NLLB-200)
- Multi-factor confidence scoring (5 factors)
- Emotion tone preservation (3 factors)
- Intelligent retry with parameter adjustment
- Drift monitoring and alerting

Usage:
    from epmssts.services.translation_v2 import TranslationService, TranslationRequest
    
    service = TranslationService(device="cuda")
    request = TranslationRequest(
        transcript="I am very happy today!",
        target_lang="es",
        emotion_label="happy",
        emotion_confidence=0.92
    )
    response = await service.translate(request)
    print(response.translated_text)  # "¡Estoy muy feliz hoy!"
    print(response.confidence_metrics.overall_confidence)  # 0.87
"""

from .translation_service import TranslationService
from .schemas import (
    TranslationRequest,
    TranslationResponse,
    TranslationHealthResponse,
    TranslationMetricsSnapshot,
    DriftAlert,
    LanguageDetectionResult,
    TranslationConfidenceMetrics,
    EmotionPreservationMetrics,
    RetryInfo,
)
from .exceptions import (
    TranslationServiceError,
    TranslationModelLoadError,
    LanguageDetectionModelLoadError,
    TranslationInferenceError,
    EmptyTranscriptError,
    TranscriptTooLongError,
    STTConfidenceTooLowError,
    UnsupportedLanguageError,
    LanguageDetectionError,
    LanguageConfidenceTooLowError,
    CodeSwitchingDetectedError,
    EmptyTranslationError,
    TranslationConfidenceTooLowError,
    RepetitiveLoopDetectedError,
    EmotionPreservationError,
    TranslationTimeoutError,
    MaxRetriesExceededError,
    FallbackModelUnavailableError,
    ConfidenceDriftError,
    EmotionPreservationDriftError,
    HighRetryRateAlertError,
)


__version__ = "2.0.0"
__all__ = [
    # Main service
    "TranslationService",
    
    # Schemas
    "TranslationRequest",
    "TranslationResponse",
    "TranslationHealthResponse",
    "TranslationMetricsSnapshot",
    "DriftAlert",
    "LanguageDetectionResult",
    "TranslationConfidenceMetrics",
    "EmotionPreservationMetrics",
    "RetryInfo",
    
    # Exceptions
    "TranslationServiceError",
    "TranslationModelLoadError",
    "LanguageDetectionModelLoadError",
    "TranslationInferenceError",
    "EmptyTranscriptError",
    "TranscriptTooLongError",
    "STTConfidenceTooLowError",
    "UnsupportedLanguageError",
    "LanguageDetectionError",
    "LanguageConfidenceTooLowError",
    "CodeSwitchingDetectedError",
    "EmptyTranslationError",
    "TranslationConfidenceTooLowError",
    "RepetitiveLoopDetectedError",
    "EmotionPreservationError",
    "TranslationTimeoutError",
    "MaxRetriesExceededError",
    "FallbackModelUnavailableError",
    "ConfidenceDriftError",
    "EmotionPreservationDriftError",
    "HighRetryRateAlertError",
]
