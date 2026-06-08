"""
TTS Service Exception Hierarchy

Structured error handling for production TTS service.
All exceptions include error codes for tracking and alerting.
"""

from enum import Enum
from typing import Optional


class TTSErrorReasonCode(Enum):
    """Standardized error codes for TTS service failures"""
    
    # Model Loading Errors (001-010)
    ERR_TTS_001 = "TTS model failed to load"
    ERR_TTS_002 = "TTS model initialization timeout"
    ERR_TTS_003 = "GPU memory allocation failed"
    ERR_TTS_004 = "Model warmup failed"
    ERR_TTS_005 = "Unsupported model version"
    
    # Input Validation Errors (011-020)
    ERR_TTS_011 = "Empty input text"
    ERR_TTS_012 = "Text exceeds maximum length"
    ERR_TTS_013 = "Translation confidence too low"
    ERR_TTS_014 = "Unsupported language"
    ERR_TTS_015 = "Invalid emotion label"
    ERR_TTS_016 = "Invalid prosody parameters"
    
    # Synthesis Errors (021-035)
    ERR_TTS_021 = "Synthesis inference failed"
    ERR_TTS_022 = "Synthesis timeout"
    ERR_TTS_023 = "GPU OOM during synthesis"
    ERR_TTS_024 = "Invalid phoneme sequence"
    ERR_TTS_025 = "Audio generation returned empty"
    ERR_TTS_026 = "Prosody application failed"
    ERR_TTS_027 = "Speaker embedding extraction failed"
    
    # Waveform Validation Errors (036-045)
    ERR_TTS_036 = "Audio duration too short"
    ERR_TTS_037 = "Audio file size too small"
    ERR_TTS_038 = "Audio RMS below threshold (likely silent)"
    ERR_TTS_039 = "Audio clipping detected"
    ERR_TTS_040 = "Audio pure tone detected (not speech)"
    ERR_TTS_041 = "Audio spectral flatness abnormal"
    ERR_TTS_042 = "Corrupted waveform detected"
    
    # Fallback Errors (046-055)
    ERR_TTS_046 = "Primary TTS engine failed"
    ERR_TTS_047 = "Secondary TTS engine failed"
    ERR_TTS_048 = "Fallback chain exhausted"
    ERR_TTS_049 = "All TTS engines unavailable"
    ERR_TTS_050 = "Retry limit exceeded"
    
    # Output Errors (056-065)
    ERR_TTS_056 = "Failed to write audio file"
    ERR_TTS_057 = "Audio format conversion failed"
    ERR_TTS_058 = "Output validation failed"
    ERR_TTS_059 = "Audio encoding error"
    
    # System Errors (066-075)
    ERR_TTS_066 = "Insufficient memory"
    ERR_TTS_067 = "Disk space exhausted"
    ERR_TTS_068 = "Service overloaded"
    ERR_TTS_069 = "Worker pool unavailable"
    ERR_TTS_070 = "GPU device unavailable"


class TTSServiceError(Exception):
    """Base exception for all TTS service errors"""
    
    def __init__(
        self,
        message: str,
        error_code: TTSErrorReasonCode,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        return {
            "error": self.message,
            "error_code": self.error_code.name,
            "error_reason": self.error_code.value,
            "details": self.details
        }


# ============ Model Loading Errors ============

class TTSModelLoadError(TTSServiceError):
    """Failed to load TTS model"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_001, details)


class TTSModelInitTimeoutError(TTSServiceError):
    """Model initialization exceeded timeout"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_002, details)


class GPUMemoryAllocationError(TTSServiceError):
    """GPU memory allocation failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_003, details)


class ModelWarmupError(TTSServiceError):
    """Model warmup failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_004, details)


class UnsupportedModelVersionError(TTSServiceError):
    """Unsupported model version"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_005, details)


# ============ Input Validation Errors ============

class EmptyInputTextError(TTSServiceError):
    """Input text is empty"""
    def __init__(self, message: str = "Input text is empty", details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_011, details)


class TextTooLongError(TTSServiceError):
    """Text exceeds maximum length"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_012, details)


class TranslationConfidenceTooLowError(TTSServiceError):
    """Translation confidence below threshold"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_013, details)


class UnsupportedLanguageError(TTSServiceError):
    """Language not supported by TTS engine"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_014, details)


class InvalidEmotionLabelError(TTSServiceError):
    """Invalid emotion label provided"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_015, details)


class InvalidProsodyParametersError(TTSServiceError):
    """Invalid prosody parameters"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_016, details)


# ============ Synthesis Errors ============

class SynthesisInferenceError(TTSServiceError):
    """Synthesis inference failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_021, details)


class SynthesisTimeoutError(TTSServiceError):
    """Synthesis exceeded timeout"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_022, details)


class GPUOOMError(TTSServiceError):
    """GPU out of memory during synthesis"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_023, details)


class InvalidPhonemeSequenceError(TTSServiceError):
    """Invalid phoneme sequence encountered"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_024, details)


class EmptyAudioGenerationError(TTSServiceError):
    """Audio generation returned empty result"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_025, details)


class ProsodyApplicationError(TTSServiceError):
    """Failed to apply prosody parameters"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_026, details)


class SpeakerEmbeddingError(TTSServiceError):
    """Speaker embedding extraction failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_027, details)


# ============ Waveform Validation Errors ============

class AudioDurationTooShortError(TTSServiceError):
    """Audio duration too short (likely failed synthesis)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_036, details)


class AudioFileSizeTooSmallError(TTSServiceError):
    """Audio file size too small (likely corrupted)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_037, details)


class SilentAudioDetectedError(TTSServiceError):
    """Audio RMS below threshold (likely silent)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_038, details)


class AudioClippingDetectedError(TTSServiceError):
    """Audio clipping detected"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_039, details)


class PureToneDetectedError(TTSServiceError):
    """Pure tone detected (not speech)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_040, details)


class AbnormalSpectralFlatnessError(TTSServiceError):
    """Spectral flatness abnormal"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_041, details)


class CorruptedWaveformError(TTSServiceError):
    """Corrupted waveform detected"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_042, details)


# ============ Fallback Errors ============

class PrimaryEngineFailedError(TTSServiceError):
    """Primary TTS engine failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_046, details)


class SecondaryEngineFailedError(TTSServiceError):
    """Secondary TTS engine failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_047, details)


class FallbackChainExhaustedError(TTSServiceError):
    """All fallback engines failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_048, details)


class AllEnginesUnavailableError(TTSServiceError):
    """All TTS engines unavailable"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_049, details)


class RetryLimitExceededError(TTSServiceError):
    """Retry limit exceeded"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_050, details)


# ============ Output Errors ============

class AudioFileWriteError(TTSServiceError):
    """Failed to write audio file"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_056, details)


class AudioFormatConversionError(TTSServiceError):
    """Audio format conversion failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_057, details)


class OutputValidationError(TTSServiceError):
    """Output validation failed"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_058, details)


class AudioEncodingError(TTSServiceError):
    """Audio encoding error"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_059, details)


# ============ System Errors ============

class InsufficientMemoryError(TTSServiceError):
    """Insufficient memory"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_066, details)


class DiskSpaceExhaustedError(TTSServiceError):
    """Disk space exhausted"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_067, details)


class ServiceOverloadedError(TTSServiceError):
    """Service overloaded"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_068, details)


class WorkerPoolUnavailableError(TTSServiceError):
    """Worker pool unavailable"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_069, details)


class GPUDeviceUnavailableError(TTSServiceError):
    """GPU device unavailable"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, TTSErrorReasonCode.ERR_TTS_070, details)
