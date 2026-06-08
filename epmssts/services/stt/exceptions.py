"""
STT Service Exceptions

Production-grade exception hierarchy for Speech-to-Text service.
All exceptions include error codes for structured logging and observability.
"""

from enum import Enum
from typing import Optional, Any, Dict


class SttErrorReasonCode(str, Enum):
    """Structured error codes for STT service failures"""
    
    # Model/GPU errors (ERR_STT_001 - ERR_STT_010)
    ERR_STT_001 = "MODEL_LOAD_FAILED"
    ERR_STT_002 = "MODEL_NOT_INITIALIZED"
    ERR_STT_003 = "GPU_OUT_OF_MEMORY"
    ERR_STT_004 = "GPU_INITIALIZATION_FAILED"
    ERR_STT_005 = "DEVICE_FALLBACK_FAILED"
    ERR_STT_006 = "MODEL_TOO_LARGE_FOR_DEVICE"
    
    # Inference errors (ERR_STT_010 - ERR_STT_020)
    ERR_STT_010 = "INFERENCE_TIMEOUT"
    ERR_STT_011 = "INFERENCE_FAILED"
    ERR_STT_012 = "INFERENCE_QUEUE_FULL"
    ERR_STT_013 = "CONFIDENCE_TOO_LOW"
    
    # Input validation errors (ERR_STT_020 - ERR_STT_030)
    ERR_STT_020 = "NO_SPEECH_DETECTED"
    ERR_STT_021 = "AUDIO_TOO_SHORT"
    ERR_STT_022 = "AUDIO_TOO_LONG"
    ERR_STT_023 = "INVALID_AUDIO_FORMAT"
    ERR_STT_024 = "EMPTY_TRANSCRIPT"
    ERR_STT_025 = "HALLUCINATION_DETECTED"
    
    # Concurrency errors (ERR_STT_030 - ERR_STT_040)
    ERR_STT_030 = "QUEUE_TIMEOUT"
    ERR_STT_031 = "CONCURRENT_LIMIT_EXCEEDED"
    
    # Configuration errors (ERR_STT_040 - ERR_STT_050)
    ERR_STT_040 = "INVALID_MODEL_CONFIG"
    ERR_STT_041 = "MISSING_MODEL_CONFIG"
    ERR_STT_042 = "INVALID_DEVICE_CONFIG"


class SttServiceException(Exception):
    """Base exception for STT service"""
    
    def __init__(
        self,
        reason_code: SttErrorReasonCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_friendly_message: Optional[str] = None,
    ):
        self.reason_code = reason_code
        self.message = message
        self.details = details or {}
        self.user_friendly_message = user_friendly_message or message
        super().__init__(self.message)


class ModelLoadError(SttServiceException):
    """Raised when model initialization fails"""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_friendly_message: Optional[str] = None,
    ):
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_001,
            message=message,
            details=details,
            user_friendly_message=user_friendly_message or "Failed to initialize speech model",
        )


class ModelNotInitializedError(SttServiceException):
    """Raised when service called before model is ready"""
    
    def __init__(self, message: str = "STT model not initialized"):
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_002,
            message=message,
            user_friendly_message="Speech model not ready. Try again shortly.",
        )


class GpuOutOfMemoryError(SttServiceException):
    """Raised when GPU memory exhausted"""
    
    def __init__(
        self,
        message: str,
        available_memory: Optional[float] = None,
        required_memory: Optional[float] = None,
    ):
        details = {}
        if available_memory is not None:
            details["available_memory_gb"] = available_memory
        if required_memory is not None:
            details["required_memory_gb"] = required_memory
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_003,
            message=message,
            details=details,
            user_friendly_message="Service temporarily overloaded. Please retry.",
        )


class GpuInitializationError(SttServiceException):
    """Raised when GPU detection/initialization fails"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        details = {}
        if original_error:
            details["original_error"] = str(original_error)
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_004,
            message=message,
            details=details,
            user_friendly_message="GPU initialization failed, using CPU fallback",
        )


class DeviceFallbackError(SttServiceException):
    """Raised when both GPU and CPU fallback fail"""
    
    def __init__(self, message: str):
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_005,
            message=message,
            user_friendly_message="Inference not available. Service unavailable.",
        )


class InferenceTimeoutError(SttServiceException):
    """Raised when inference takes too long"""
    
    def __init__(self, timeout_seconds: float, audio_duration: Optional[float] = None):
        details = {"timeout_seconds": timeout_seconds}
        if audio_duration:
            details["audio_duration_seconds"] = audio_duration
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_010,
            message=f"Inference exceeded {timeout_seconds}s timeout",
            details=details,
            user_friendly_message="Speech processing took too long. Try shorter audio.",
        )


class InferenceError(SttServiceException):
    """Raised when inference fails"""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        if details is None:
            details = {}
        if original_error:
            details["original_error"] = str(original_error)
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_011,
            message=message,
            details=details,
            user_friendly_message="Failed to process speech",
        )


class InferenceQueueFullError(SttServiceException):
    """Raised when queue is at capacity"""
    
    def __init__(self, queue_size: int, max_size: int):
        details = {
            "current_queue_size": queue_size,
            "max_queue_size": max_size,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_012,
            message=f"Inference queue full ({queue_size}/{max_size})",
            details=details,
            user_friendly_message="Service temporarily at capacity. Please retry.",
        )


class ConfidenceTooLowError(SttServiceException):
    """Raised when confidence score below threshold"""
    
    def __init__(
        self,
        confidence: float,
        threshold: float,
        reason: Optional[str] = None,
    ):
        details = {
            "confidence": confidence,
            "threshold": threshold,
        }
        if reason:
            details["reason"] = reason
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_013,
            message=f"Confidence {confidence:.2f} below threshold {threshold:.2f}",
            details=details,
            user_friendly_message="Confidence in speech recognition too low. Try clearer audio.",
        )


class NoSpeechDetectedError(SttServiceException):
    """Raised when no speech probability too high"""
    
    def __init__(self, no_speech_prob: float, threshold: float):
        details = {
            "no_speech_probability": no_speech_prob,
            "threshold": threshold,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_020,
            message=f"No speech detected (prob={no_speech_prob:.3f})",
            details=details,
            user_friendly_message="No speech detected. Check audio input.",
        )


class AudioTooShortError(SttServiceException):
    """Raised when audio duration below minimum"""
    
    def __init__(self, duration: float, minimum: float):
        details = {
            "duration_seconds": duration,
            "minimum_seconds": minimum,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_021,
            message=f"Audio too short: {duration:.2f}s < {minimum:.2f}s minimum",
            details=details,
            user_friendly_message=f"Audio must be at least {minimum:.1f} seconds",
        )


class AudioTooLongError(SttServiceException):
    """Raised when audio duration exceeds maximum"""
    
    def __init__(self, duration: float, maximum: float):
        details = {
            "duration_seconds": duration,
            "maximum_seconds": maximum,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_022,
            message=f"Audio too long: {duration:.2f}s > {maximum:.2f}s maximum",
            details=details,
            user_friendly_message=f"Audio must be at most {maximum:.1f} seconds",
        )


class InvalidAudioFormatError(SttServiceException):
    """Raised when audio format not supported"""
    
    def __init__(self, format_detected: str, supported_formats: list):
        details = {
            "format_detected": format_detected,
            "supported_formats": supported_formats,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_023,
            message=f"Unsupported audio format: {format_detected}",
            details=details,
            user_friendly_message=f"Use WAV, MP3, or FLAC audio",
        )


class EmptyTranscriptError(SttServiceException):
    """Raised when transcription is empty after processing"""
    
    def __init__(self, message: str = "Transcription returned empty"):
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_024,
            message=message,
            user_friendly_message="No text detected in speech",
        )


class HallucinationDetectedError(SttServiceException):
    """Raised when hallucination detected in transcript"""
    
    def __init__(
        self,
        message: str,
        hallucination_score: Optional[float] = None,
        detector_reason: Optional[str] = None,
    ):
        details = {}
        if hallucination_score is not None:
            details["hallucination_score"] = hallucination_score
        if detector_reason:
            details["detector_reason"] = detector_reason
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_025,
            message=message,
            details=details,
            user_friendly_message="Unreliable transcription detected",
        )


class QueueTimeoutError(SttServiceException):
    """Raised when queue acquisition times out"""
    
    def __init__(self, timeout_seconds: float):
        details = {"timeout_seconds": timeout_seconds}
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_030,
            message=f"Queue timeout after {timeout_seconds}s",
            details=details,
            user_friendly_message="Service busy. Please retry.",
        )


class ConcurrentLimitExceededError(SttServiceException):
    """Raised when concurrent request limit exceeded"""
    
    def __init__(self, current_count: int, max_concurrent: int):
        details = {
            "current_concurrent": current_count,
            "max_concurrent": max_concurrent,
        }
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_031,
            message=f"Concurrent limit exceeded: {current_count}/{max_concurrent}",
            details=details,
            user_friendly_message="Too many simultaneous requests. Try again soon.",
        )


class InvalidModelConfigError(SttServiceException):
    """Raised when model config invalid"""
    
    def __init__(self, message: str, config_issue: Optional[str] = None):
        details = {}
        if config_issue:
            details["config_issue"] = config_issue
            
        super().__init__(
            reason_code=SttErrorReasonCode.ERR_STT_040,
            message=message,
            details=details,
        )
