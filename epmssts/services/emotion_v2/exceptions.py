"""
Emotion Intelligence Service Exceptions

Production-grade exception hierarchy for ensemble-based emotion classification.
"""

from enum import Enum
from typing import Optional, Dict, Any


class EmotionErrorReasonCode(str, Enum):
    """Structured error codes for emotion service failures"""
    
    # Model errors (ERR_EMO_001 - ERR_EMO_010)
    ERR_EMO_001 = "AUDIO_MODEL_LOAD_FAILED"
    ERR_EMO_002 = "TEXT_MODEL_LOAD_FAILED"
    ERR_EMO_003 = "MODEL_NOT_INITIALIZED"
    ERR_EMO_004 = "MODEL_INFERENCE_FAILED"
    ERR_EMO_005 = "ENSEMBLE_DISAGREEMENT_HIGH"
    
    # Input validation errors (ERR_EMO_010 - ERR_EMO_020)
    ERR_EMO_010 = "INVALID_AUDIO_FEATURES"
    ERR_EMO_011 = "INVALID_MEL_FEATURES"
    ERR_EMO_012 = "QUALITY_SCORE_TOO_LOW"
    ERR_EMO_013 = "DURATION_TOO_SHORT"
    ERR_EMO_014 = "EMPTY_TRANSCRIPT_AND_BAD_AUDIO"
    ERR_EMO_015 = "FEATURE_DIMENSION_MISMATCH"
    
    # Calibration errors (ERR_EMO_020 - ERR_EMO_030)
    ERR_EMO_020 = "CALIBRATION_FAILED"
    ERR_EMO_021 = "TEMPERATURE_OUT_OF_BOUNDS"
    ERR_EMO_022 = "PROBABILITY_SUM_INVALID"
    ERR_EMO_023 = "CONFIDENCE_COLLAPSE"
    
    # Fusion errors (ERR_EMO_030 - ERR_EMO_040)
    ERR_EMO_030 = "FUSION_FAILED"
    ERR_EMO_031 = "WEIGHT_COMPUTATION_FAILED"
    ERR_EMO_032 = "BAYESIAN_FUSION_INVALID"
    
    # Drift/monitoring errors (ERR_EMO_040 - ERR_EMO_050)
    ERR_EMO_040 = "DRIFT_DETECTION_FAILED"
    ERR_EMO_041 = "NEUTRAL_COLLAPSE_DETECTED"
    ERR_EMO_042 = "ENTROPY_SPIKE_DETECTED"
    ERR_EMO_043 = "DISTRIBUTION_SHIFT_DETECTED"
    
    # Uncertainty errors (ERR_EMO_050 - ERR_EMO_060)
    ERR_EMO_050 = "UNCERTAINTY_TOO_HIGH"
    ERR_EMO_051 = "ENTROPY_THRESHOLD_EXCEEDED"
    ERR_EMO_052 = "LOW_CONFIDENCE_OUTPUT"


class EmotionServiceException(Exception):
    """Base exception for emotion service"""
    
    def __init__(
        self,
        reason_code: EmotionErrorReasonCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_friendly_message: Optional[str] = None,
    ):
        self.reason_code = reason_code
        self.message = message
        self.details = details or {}
        self.user_friendly_message = user_friendly_message or message
        super().__init__(self.message)


class AudioModelLoadError(EmotionServiceException):
    """Raised when audio model initialization fails"""
    
    def __init__(self, message: str, model_name: Optional[str] = None):
        details = {"model_name": model_name} if model_name else {}
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_001,
            message=message,
            details=details,
            user_friendly_message="Failed to initialize audio emotion model",
        )


class TextModelLoadError(EmotionServiceException):
    """Raised when text model initialization fails"""
    
    def __init__(self, message: str, model_name: Optional[str] = None):
        details = {"model_name": model_name} if model_name else {}
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_002,
            message=message,
            details=details,
            user_friendly_message="Failed to initialize text emotion model",
        )


class ModelNotInitializedError(EmotionServiceException):
    """Raised when service called before models ready"""
    
    def __init__(self, message: str = "Emotion models not initialized"):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_003,
            message=message,
            user_friendly_message="Emotion service not ready",
        )


class ModelInferenceError(EmotionServiceException):
    """Raised when model inference fails"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        details = {}
        if model_name:
            details["model_name"] = model_name
        if original_error:
            details["original_error"] = str(original_error)
        
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_004,
            message=message,
            details=details,
            user_friendly_message="Failed to predict emotion",
        )


class EnsembleDisagreementError(EmotionServiceException):
    """Raised when ensemble models strongly disagree"""
    
    def __init__(self, disagreement_score: float, threshold: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_005,
            message=f"High ensemble disagreement: {disagreement_score:.2f} > {threshold:.2f}",
            details={
                "disagreement_score": disagreement_score,
                "threshold": threshold,
            },
            user_friendly_message="Inconsistent emotion predictions - low confidence",
        )


class InvalidAudioFeaturesError(EmotionServiceException):
    """Raised when audio features invalid"""
    
    def __init__(self, message: str):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_010,
            message=message,
            user_friendly_message="Invalid audio features provided",
        )


class QualityScoreTooLowError(EmotionServiceException):
    """Raised when audio quality insufficient for reliable emotion detection"""
    
    def __init__(self, quality_score: int, threshold: int):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_012,
            message=f"Quality score {quality_score} below threshold {threshold}",
            details={
                "quality_score": quality_score,
                "threshold": threshold,
            },
            user_friendly_message="Audio quality too low for emotion detection",
        )


class DurationTooShortError(EmotionServiceException):
    """Raised when audio too short for reliable emotion detection"""
    
    def __init__(self, duration: float, minimum: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_013,
            message=f"Duration {duration:.2f}s < minimum {minimum:.2f}s",
            details={
                "duration_seconds": duration,
                "minimum_seconds": minimum,
            },
            user_friendly_message=f"Audio must be at least {minimum:.1f} seconds",
        )


class EmptyTranscriptAndBadAudioError(EmotionServiceException):
    """Raised when both transcript empty and audio unusable"""
    
    def __init__(self):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_014,
            message="Empty transcript and audio quality insufficient",
            user_friendly_message="No usable data for emotion detection",
        )


class CalibrationError(EmotionServiceException):
    """Raised when calibration fails"""
    
    def __init__(self, message: str):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_020,
            message=message,
            user_friendly_message="Emotion calibration failed",
        )


class ConfidenceCollapseError(EmotionServiceException):
    """Raised when confidence collapses to unusable levels"""
    
    def __init__(self, max_prob: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_023,
            message=f"Confidence collapsed: max_prob={max_prob:.2f}",
            details={"max_probability": max_prob},
            user_friendly_message="Unable to determine emotion with confidence",
        )


class FusionError(EmotionServiceException):
    """Raised when ensemble fusion fails"""
    
    def __init__(self, message: str):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_030,
            message=message,
            user_friendly_message="Failed to combine emotion predictions",
        )


class NeutralCollapseAlertError(EmotionServiceException):
    """Raised when neutral predictions dominate (drift alert)"""
    
    def __init__(self, neutral_rate: float, threshold: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_041,
            message=f"Neutral collapse: {neutral_rate:.1%} > {threshold:.1%}",
            details={
                "neutral_rate": neutral_rate,
                "threshold": threshold,
            },
            user_friendly_message="System drift detected - neutral bias",
        )


class UncertaintyTooHighError(EmotionServiceException):
    """Raised when uncertainty exceeds acceptable threshold"""
    
    def __init__(self, entropy: float, threshold: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_050,
            message=f"High uncertainty: entropy={entropy:.2f} > {threshold:.2f}",
            details={
                "entropy": entropy,
                "threshold": threshold,
            },
            user_friendly_message="Emotion prediction uncertain",
        )


class LowConfidenceOutputError(EmotionServiceException):
    """Raised when output confidence too low for production use"""
    
    def __init__(self, confidence: float, threshold: float):
        super().__init__(
            reason_code=EmotionErrorReasonCode.ERR_EMO_052,
            message=f"Low confidence: {confidence:.2f} < {threshold:.2f}",
            details={
                "confidence": confidence,
                "threshold": threshold,
            },
            user_friendly_message="Low confidence in emotion prediction",
        )
