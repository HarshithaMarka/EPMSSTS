"""
Emotion-Aware Text-to-Speech Service v2

Production-grade neural TTS with:
- Emotion preservation (prosody control)
- Multilingual support (16 languages)
- Waveform validation (never silent)
- Intelligent fallback chain
- GPU acceleration
- Observable and scalable

Usage:
    from epmssts.services.tts_v2 import TTSService, TTSRequest
    
    service = TTSService(device="cuda")
    request = TTSRequest(
        translated_text="I am very happy!",
        target_language="en",
        emotion_label="happy",
        emotion_confidence=0.92
    )
    response = await service.synthesize(request)
    print(response.audio_path)
"""

from .tts_service import TTSService
from .schemas import (
    TTSRequest,
    TTSResponse,
    TTSHealthResponse,
    TTSMetricsSnapshot,
    ProsodyProfile,
    WaveformQualityMetrics,
    FallbackInfo,
)
from .exceptions import (
    TTSServiceError,
    TTSModelLoadError,
    EmptyInputTextError,
    TextTooLongError,
    TranslationConfidenceTooLowError,
    UnsupportedLanguageError,
    SynthesisInferenceError,
    SynthesisTimeoutError,
    SilentAudioDetectedError,
    AudioClippingDetectedError,
    FallbackChainExhaustedError,
)


__version__ = "2.0.0"
__all__ = [
    # Main service
    "TTSService",
    
    # Schemas
    "TTSRequest",
    "TTSResponse",
    "TTSHealthResponse",
    "TTSMetricsSnapshot",
    "ProsodyProfile",
    "WaveformQualityMetrics",
    "FallbackInfo",
    
    # Exceptions
    "TTSServiceError",
    "TTSModelLoadError",
    "EmptyInputTextError",
    "TextTooLongError",
    "TranslationConfidenceTooLowError",
    "UnsupportedLanguageError",
    "SynthesisInferenceError",
    "SynthesisTimeoutError",
    "SilentAudioDetectedError",
    "AudioClippingDetectedError",
    "FallbackChainExhaustedError",
]
