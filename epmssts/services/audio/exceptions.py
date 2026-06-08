"""
Custom exceptions for Audio Preprocessing Service.

Structured error handling with reason codes for observability.
"""

from enum import Enum
from typing import Optional


class ErrorReasonCode(str, Enum):
    """Standardized error reason codes for observability."""
    
    # Format errors
    UNSUPPORTED_FORMAT = "ERR_001_UNSUPPORTED_FORMAT"
    DECODE_ERROR = "ERR_002_DECODE_ERROR"
    CORRUPT_FILE = "ERR_003_CORRUPT_FILE"
    
    # Duration errors
    DURATION_TOO_SHORT = "ERR_004_DURATION_TOO_SHORT"
    DURATION_TOO_LONG = "ERR_005_DURATION_TOO_LONG"
    
    # Size errors
    FILE_TOO_LARGE = "ERR_006_FILE_TOO_LARGE"
    FILE_EMPTY = "ERR_007_FILE_EMPTY"
    
    # Quality errors
    SILENCE_RATIO_TOO_HIGH = "ERR_008_SILENCE_RATIO_TOO_HIGH"
    SNR_TOO_LOW = "ERR_009_SNR_TOO_LOW"
    EXCESSIVE_CLIPPING = "ERR_010_EXCESSIVE_CLIPPING"
    
    # Processing errors
    VAD_FAILURE = "ERR_011_VAD_FAILURE"
    METRIC_EXTRACTION_FAILURE = "ERR_012_METRIC_EXTRACTION_FAILURE"
    EMPTY_AFTER_TRIMMING = "ERR_013_EMPTY_AFTER_TRIMMING"
    
    # System errors
    INTERNAL_ERROR = "ERR_999_INTERNAL_ERROR"


class AudioPreprocessingException(Exception):
    """Base exception for audio preprocessing service."""
    
    def __init__(
        self,
        message: str,
        reason_code: ErrorReasonCode,
        details: Optional[dict] = None
    ):
        self.message = message
        self.reason_code = reason_code
        self.details = details or {}
        super().__init__(self.message)


class UnsupportedFormatError(AudioPreprocessingException):
    """Raised when file format is not supported."""
    
    def __init__(self, format_ext: str, details: Optional[dict] = None):
        super().__init__(
            f"Unsupported audio format: {format_ext}",
            ErrorReasonCode.UNSUPPORTED_FORMAT,
            details or {"format": format_ext}
        )


class DecodeError(AudioPreprocessingException):
    """Raised when audio decoding fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message,
            ErrorReasonCode.DECODE_ERROR,
            details
        )


class CorruptFileError(AudioPreprocessingException):
    """Raised when audio file is corrupted."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message,
            ErrorReasonCode.CORRUPT_FILE,
            details
        )


class DurationError(AudioPreprocessingException):
    """Raised when duration is outside acceptable range."""
    
    def __init__(
        self,
        duration: float,
        min_duration: float = 1.5,
        max_duration: float = 60.0,
        details: Optional[dict] = None
    ):
        if duration < min_duration:
            reason_code = ErrorReasonCode.DURATION_TOO_SHORT
            msg = f"Duration {duration:.2f}s is below minimum {min_duration}s"
        else:
            reason_code = ErrorReasonCode.DURATION_TOO_LONG
            msg = f"Duration {duration:.2f}s exceeds maximum {max_duration}s"
        
        super().__init__(
            msg,
            reason_code,
            details or {"duration": duration, "min": min_duration, "max": max_duration}
        )


class FileSizeError(AudioPreprocessingException):
    """Raised when file size is outside acceptable range."""
    
    def __init__(self, size_bytes: int, max_size_bytes: int = 10_000_000):
        super().__init__(
            f"File size {size_bytes / 1e6:.2f}MB exceeds maximum {max_size_bytes / 1e6:.2f}MB",
            ErrorReasonCode.FILE_TOO_LARGE,
            {"size_bytes": size_bytes, "max_size_bytes": max_size_bytes}
        )


class SilenceRatioError(AudioPreprocessingException):
    """Raised when silence ratio is too high."""
    
    def __init__(self, silence_ratio: float, threshold: float = 0.80):
        super().__init__(
            f"Silence ratio {silence_ratio:.2%} exceeds threshold {threshold:.2%}",
            ErrorReasonCode.SILENCE_RATIO_TOO_HIGH,
            {"silence_ratio": silence_ratio, "threshold": threshold}
        )


class SNRError(AudioPreprocessingException):
    """Raised when SNR is below threshold."""
    
    def __init__(self, snr: float, threshold: float = 5.0):
        super().__init__(
            f"SNR {snr:.2f}dB is below minimum threshold {threshold:.2f}dB",
            ErrorReasonCode.SNR_TOO_LOW,
            {"snr": snr, "threshold": threshold}
        )


class EmptyAudioError(AudioPreprocessingException):
    """Raised when audio is empty or becomes empty after processing."""
    
    def __init__(self, stage: str, details: Optional[dict] = None):
        super().__init__(
            f"Audio is empty at stage: {stage}",
            ErrorReasonCode.EMPTY_AFTER_TRIMMING,
            details or {"stage": stage}
        )


class ProcessingError(AudioPreprocessingException):
    """Raised for processing failures (VAD, metrics, etc.)."""
    
    def __init__(
        self,
        stage: str,
        original_error: Exception,
        reason_code: ErrorReasonCode,
        details: Optional[dict] = None
    ):
        super().__init__(
            f"Processing failed at {stage}: {str(original_error)}",
            reason_code,
            details or {"stage": stage, "original_error": type(original_error).__name__}
        )
