"""
Speech-to-Text (STT) Service Module

Production-grade Whisper-based microservice for speech transcription.
Includes GPU/CPU support, confidence scoring, concurrency control, and observability.
"""

from .exceptions import (
    SttServiceException,
    SttErrorReasonCode,
    ModelLoadError,
    ModelNotInitializedError,
    GpuOutOfMemoryError,
    GpuInitializationError,
    DeviceFallbackError,
    InferenceTimeoutError,
    InferenceError,
    InferenceQueueFullError,
    ConfidenceTooLowError,
    NoSpeechDetectedError,
    AudioTooShortError,
    AudioTooLongError,
    InvalidAudioFormatError,
    EmptyTranscriptError,
    HallucinationDetectedError,
    QueueTimeoutError,
    ConcurrentLimitExceededError,
    InvalidModelConfigError,
)

from .schemas import (
    SttRequest,
    SttResponse,
    TranscriptionSegment,
    AudioFormat,
    LanguageCode,
    DeviceType,
    ModelSize,
    ModelStatusInfo,
    HealthCheckResponse,
    MetricsSnapshot,
    ErrorResponse,
)

from .device_manager import DeviceManager, DeviceConfig
from .model_manager import ModelManager
from .confidence_scorer import TranscriptionConfidenceScorer, ConfidenceFactors
from .stt_service import SpeechToTextService, InferenceMetrics
from .logging_config import configure_logging, StructuredLogger, StructuredJsonFormatter

__all__ = [
    # Exceptions
    "SttServiceException",
    "SttErrorReasonCode",
    "ModelLoadError",
    "ModelNotInitializedError",
    "GpuOutOfMemoryError",
    "GpuInitializationError",
    "DeviceFallbackError",
    "InferenceTimeoutError",
    "InferenceError",
    "InferenceQueueFullError",
    "ConfidenceTooLowError",
    "NoSpeechDetectedError",
    "AudioTooShortError",
    "AudioTooLongError",
    "InvalidAudioFormatError",
    "EmptyTranscriptError",
    "HallucinationDetectedError",
    "QueueTimeoutError",
    "ConcurrentLimitExceededError",
    "InvalidModelConfigError",
    
    # Schemas
    "SttRequest",
    "SttResponse",
    "TranscriptionSegment",
    "AudioFormat",
    "LanguageCode",
    "DeviceType",
    "ModelSize",
    "ModelStatusInfo",
    "HealthCheckResponse",
    "MetricsSnapshot",
    "ErrorResponse",
    
    # Components
    "DeviceManager",
    "DeviceConfig",
    "ModelManager",
    "TranscriptionConfidenceScorer",
    "ConfidenceFactors",
    "SpeechToTextService",
    "InferenceMetrics",
    
    # Logging
    "configure_logging",
    "StructuredLogger",
    "StructuredJsonFormatter",
]
