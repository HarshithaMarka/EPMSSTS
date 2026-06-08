"""
Translation Service Exceptions

Structured error hierarchy for translation intelligence layer.
Error codes: ERR_TRANS_001 - ERR_TRANS_065
"""

from enum import Enum
from typing import Optional, Dict, Any


class TranslationErrorReasonCode(Enum):
    """Error reason codes for translation service"""
    
    # Model errors (001-010)
    ERR_TRANS_001 = "Translation model load failed"
    ERR_TRANS_002 = "Language detection model load failed"
    ERR_TRANS_003 = "Translation inference failed"
    ERR_TRANS_004 = "Model initialization timeout"
    ERR_TRANS_005 = "GPU memory error"
    
    # Input validation errors (011-020)
    ERR_TRANS_011 = "Empty transcript"
    ERR_TRANS_012 = "Transcript too long"
    ERR_TRANS_013 = "STT confidence too low"
    ERR_TRANS_014 = "Unsupported source language"
    ERR_TRANS_015 = "Unsupported target language"
    ERR_TRANS_016 = "Invalid language code"
    ERR_TRANS_017 = "Missing required field"
    
    # Language detection errors (021-030)
    ERR_TRANS_021 = "Language detection failed"
    ERR_TRANS_022 = "Language confidence too low"
    ERR_TRANS_023 = "Ambiguous language detection"
    ERR_TRANS_024 = "Code-switching detected"
    
    # Translation errors (031-045)
    ERR_TRANS_031 = "Empty translation output"
    ERR_TRANS_032 = "Translation confidence too low"
    ERR_TRANS_033 = "Repetitive loop detected"
    ERR_TRANS_034 = "Length mismatch detected"
    ERR_TRANS_035 = "Emotion preservation failed"
    ERR_TRANS_036 = "Translation timeout"
    ERR_TRANS_037 = "Token overflow"
    ERR_TRANS_038 = "Named entity loss"
    
    # Retry errors (046-055)
    ERR_TRANS_046 = "Max retries exceeded"
    ERR_TRANS_047 = "Retry strategy failed"
    ERR_TRANS_048 = "Fallback model unavailable"
    ERR_TRANS_049 = "Retry loop detected"
    
    # Monitoring/Drift errors (056-065)
    ERR_TRANS_056 = "Confidence drift detected"
    ERR_TRANS_057 = "Emotion preservation drift"
    ERR_TRANS_058 = "High retry rate alert"
    ERR_TRANS_059 = "Latency spike detected"
    ERR_TRANS_060 = "Language distribution drift"


class TranslationServiceError(Exception):
    """Base exception for translation service"""
    
    def __init__(
        self,
        message: str,
        reason_code: Optional[TranslationErrorReasonCode] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.details = details or {}
        
        # Generate user-friendly message
        self.user_friendly_message = self._generate_user_message()
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly error message"""
        if self.reason_code:
            return f"Translation error: {self.reason_code.value}"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "reason_code": self.reason_code.name if self.reason_code else None,
            "user_message": self.user_friendly_message,
            "details": self.details,
        }


# ============================================================================
# Model Errors
# ============================================================================


class TranslationModelLoadError(TranslationServiceError):
    """Translation model failed to load"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            reason_code=TranslationErrorReasonCode.ERR_TRANS_001,
            details={
                "model_name": model_name,
                "original_error": str(original_error) if original_error else None,
            },
        )


class LanguageDetectionModelLoadError(TranslationServiceError):
    """Language detection model failed to load"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            reason_code=TranslationErrorReasonCode.ERR_TRANS_002,
            details={
                "model_name": model_name,
                "original_error": str(original_error) if original_error else None,
            },
        )


class TranslationInferenceError(TranslationServiceError):
    """Translation inference failed"""
    
    def __init__(
        self,
        message: str,
        transcript: Optional[str] = None,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            reason_code=TranslationErrorReasonCode.ERR_TRANS_003,
            details={
                "transcript_length": len(transcript) if transcript else 0,
                "source_language": source_lang,
                "target_language": target_lang,
                "original_error": str(original_error) if original_error else None,
            },
        )


# ============================================================================
# Input Validation Errors
# ============================================================================


class EmptyTranscriptError(TranslationServiceError):
    """Transcript is empty"""
    
    def __init__(self):
        super().__init__(
            message="Transcript cannot be empty",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_011,
        )


class TranscriptTooLongError(TranslationServiceError):
    """Transcript exceeds maximum length"""
    
    def __init__(
        self,
        transcript_length: int,
        max_length: int,
    ):
        super().__init__(
            message=f"Transcript length {transcript_length} exceeds maximum {max_length}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_012,
            details={
                "transcript_length": transcript_length,
                "max_length": max_length,
            },
        )


class STTConfidenceTooLowError(TranslationServiceError):
    """STT confidence below minimum threshold"""
    
    def __init__(
        self,
        stt_confidence: float,
        threshold: float,
    ):
        super().__init__(
            message=f"STT confidence {stt_confidence:.3f} below threshold {threshold:.3f}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_013,
            details={
                "stt_confidence": stt_confidence,
                "threshold": threshold,
            },
        )


class UnsupportedLanguageError(TranslationServiceError):
    """Language not supported"""
    
    def __init__(
        self,
        language: str,
        language_type: str = "source",
    ):
        super().__init__(
            message=f"Unsupported {language_type} language: {language}",
            reason_code=(
                TranslationErrorReasonCode.ERR_TRANS_014
                if language_type == "source"
                else TranslationErrorReasonCode.ERR_TRANS_015
            ),
            details={
                "language": language,
                "language_type": language_type,
            },
        )


# ============================================================================
# Language Detection Errors
# ============================================================================


class LanguageDetectionError(TranslationServiceError):
    """Language detection failed"""
    
    def __init__(
        self,
        message: str,
        transcript: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            reason_code=TranslationErrorReasonCode.ERR_TRANS_021,
            details={
                "transcript_length": len(transcript) if transcript else 0,
                "original_error": str(original_error) if original_error else None,
            },
        )


class LanguageConfidenceTooLowError(TranslationServiceError):
    """Language detection confidence too low"""
    
    def __init__(
        self,
        detected_language: str,
        confidence: float,
        threshold: float,
    ):
        super().__init__(
            message=f"Language detection confidence {confidence:.3f} below threshold {threshold:.3f}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_022,
            details={
                "detected_language": detected_language,
                "confidence": confidence,
                "threshold": threshold,
            },
        )


class CodeSwitchingDetectedError(TranslationServiceError):
    """Code-switching detected in transcript"""
    
    def __init__(
        self,
        detected_languages: list,
    ):
        super().__init__(
            message=f"Code-switching detected: {', '.join(detected_languages)}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_024,
            details={
                "detected_languages": detected_languages,
            },
        )


# ============================================================================
# Translation Errors
# ============================================================================


class EmptyTranslationError(TranslationServiceError):
    """Translation produced empty output"""
    
    def __init__(
        self,
        transcript: str,
        source_lang: str,
        target_lang: str,
    ):
        super().__init__(
            message="Translation produced empty output",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_031,
            details={
                "transcript": transcript[:100],
                "source_language": source_lang,
                "target_language": target_lang,
            },
        )


class TranslationConfidenceTooLowError(TranslationServiceError):
    """Translation confidence below threshold"""
    
    def __init__(
        self,
        confidence: float,
        threshold: float,
        translation: Optional[str] = None,
    ):
        super().__init__(
            message=f"Translation confidence {confidence:.3f} below threshold {threshold:.3f}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_032,
            details={
                "confidence": confidence,
                "threshold": threshold,
                "translation": translation[:100] if translation else None,
            },
        )


class RepetitiveLoopDetectedError(TranslationServiceError):
    """Repetitive loop detected in translation"""
    
    def __init__(
        self,
        translation: str,
        repetition_pattern: Optional[str] = None,
    ):
        super().__init__(
            message="Repetitive loop detected in translation output",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_033,
            details={
                "translation": translation[:100],
                "repetition_pattern": repetition_pattern,
            },
        )


class EmotionPreservationError(TranslationServiceError):
    """Emotion preservation score too low"""
    
    def __init__(
        self,
        emotion_preservation_score: float,
        threshold: float,
        original_emotion: Optional[str] = None,
        translated_emotion: Optional[str] = None,
    ):
        super().__init__(
            message=f"Emotion preservation score {emotion_preservation_score:.3f} below threshold {threshold:.3f}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_035,
            details={
                "emotion_preservation_score": emotion_preservation_score,
                "threshold": threshold,
                "original_emotion": original_emotion,
                "translated_emotion": translated_emotion,
            },
        )


class TranslationTimeoutError(TranslationServiceError):
    """Translation exceeded timeout"""
    
    def __init__(
        self,
        timeout_seconds: float,
        transcript_length: Optional[int] = None,
    ):
        super().__init__(
            message=f"Translation exceeded timeout of {timeout_seconds}s",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_036,
            details={
                "timeout_seconds": timeout_seconds,
                "transcript_length": transcript_length,
            },
        )


# ============================================================================
# Retry Errors
# ============================================================================


class MaxRetriesExceededError(TranslationServiceError):
    """Maximum retry attempts exceeded"""
    
    def __init__(
        self,
        max_retries: int,
        last_error: Optional[str] = None,
    ):
        super().__init__(
            message=f"Maximum retry attempts ({max_retries}) exceeded",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_046,
            details={
                "max_retries": max_retries,
                "last_error": last_error,
            },
        )


class FallbackModelUnavailableError(TranslationServiceError):
    """Fallback model not available"""
    
    def __init__(self):
        super().__init__(
            message="Fallback translation model not available",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_048,
        )


# ============================================================================
# Monitoring/Drift Errors
# ============================================================================


class ConfidenceDriftError(TranslationServiceError):
    """Translation confidence drift detected"""
    
    def __init__(
        self,
        current_confidence: float,
        baseline_confidence: float,
        drift_percentage: float,
    ):
        super().__init__(
            message=f"Confidence drift detected: {drift_percentage:.1f}% below baseline",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_056,
            details={
                "current_confidence": current_confidence,
                "baseline_confidence": baseline_confidence,
                "drift_percentage": drift_percentage,
            },
        )


class EmotionPreservationDriftError(TranslationServiceError):
    """Emotion preservation drift detected"""
    
    def __init__(
        self,
        current_score: float,
        baseline_score: float,
        drift_percentage: float,
    ):
        super().__init__(
            message=f"Emotion preservation drift detected: {drift_percentage:.1f}% below baseline",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_057,
            details={
                "current_score": current_score,
                "baseline_score": baseline_score,
                "drift_percentage": drift_percentage,
            },
        )


class HighRetryRateAlertError(TranslationServiceError):
    """High retry rate alert"""
    
    def __init__(
        self,
        retry_rate: float,
        threshold: float,
    ):
        super().__init__(
            message=f"High retry rate: {retry_rate:.1%} exceeds threshold {threshold:.1%}",
            reason_code=TranslationErrorReasonCode.ERR_TRANS_058,
            details={
                "retry_rate": retry_rate,
                "threshold": threshold,
            },
        )
