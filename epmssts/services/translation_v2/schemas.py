"""
Translation Service Schemas

Pydantic models for translation intelligence layer.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime


# ============================================================================
# Enums
# ============================================================================


class TranslationStatus(str, Enum):
    """Translation status"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRY = "retry"


class LanguageCode(str, Enum):
    """Supported language codes"""
    AUTO = "auto"
    ENGLISH = "en"
    TELUGU = "te"
    HINDI = "hi"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    RUSSIAN = "ru"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    DUTCH = "nl"
    TURKISH = "tr"


class EmotionLabel(str, Enum):
    """Emotion labels"""
    ANGRY = "angry"
    HAPPY = "happy"
    NEUTRAL = "neutral"
    SAD = "sad"
    EXCITED = "excited"
    FEARFUL = "fearful"


class RetryReason(str, Enum):
    """Retry trigger reasons"""
    EMPTY_OUTPUT = "empty_output"
    LOW_CONFIDENCE = "low_confidence"
    EMOTION_MISMATCH = "emotion_mismatch"
    REPETITIVE_LOOP = "repetitive_loop"
    LENGTH_MISMATCH = "length_mismatch"


# ============================================================================
# Request Schema
# ============================================================================


class TranslationRequest(BaseModel):
    """Translation request schema"""
    
    # Core fields
    transcript: str = Field(..., description="Source transcript to translate")
    source_language: str = Field(
        default="auto",
        description="Source language code ('auto' for auto-detection)"
    )
    target_language: str = Field(..., description="Target language code")
    
    # Metadata
    emotion_label: Optional[str] = Field(None, description="Emotion label from emotion service")
    emotion_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Emotion confidence score"
    )
    stt_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="STT confidence score"
    )
    
    # Context
    context_window: Optional[List[str]] = Field(
        default=None,
        description="Previous sentences for context"
    )
    
    # Request tracking
    request_id: str = Field(..., description="Unique request identifier")
    
    # Optional override thresholds
    min_stt_confidence: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum STT confidence threshold"
    )
    min_translation_confidence: Optional[float] = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum translation confidence threshold"
    )
    min_emotion_preservation: Optional[float] = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum emotion preservation score"
    )
    
    @validator("transcript")
    def validate_transcript(cls, v):
        """Validate transcript is not empty"""
        if not v or not v.strip():
            raise ValueError("Transcript cannot be empty")
        return v.strip()
    
    @validator("target_language")
    def validate_target_language(cls, v):
        """Validate target language is not 'auto'"""
        if v == "auto":
            raise ValueError("Target language cannot be 'auto'")
        return v


# ============================================================================
# Response Schemas
# ============================================================================


class LanguageDetectionResult(BaseModel):
    """Language detection result"""
    
    detected_language: str = Field(..., description="Detected language code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    alternative_languages: Optional[Dict[str, float]] = Field(
        None,
        description="Alternative language candidates with confidence"
    )
    is_code_switching: bool = Field(
        default=False,
        description="Whether code-switching was detected"
    )


class TranslationConfidenceMetrics(BaseModel):
    """Comprehensive translation confidence metrics"""
    
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall translation confidence"
    )
    model_log_probability: Optional[float] = Field(
        None,
        description="Model log probability score"
    )
    length_consistency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Source-target length consistency"
    )
    repetition_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Repetition detection score (1.0 = no repetition)"
    )
    language_consistency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Target language consistency score"
    )


class EmotionPreservationMetrics(BaseModel):
    """Emotion preservation metrics"""
    
    preservation_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall emotion preservation score"
    )
    original_emotion: Optional[str] = Field(
        None,
        description="Original emotion label"
    )
    translated_emotion_estimate: Optional[str] = Field(
        None,
        description="Estimated emotion in translated text"
    )
    polarity_match: bool = Field(
        default=True,
        description="Whether polarity (positive/negative) matches"
    )
    intensity_preserved: bool = Field(
        default=True,
        description="Whether emotional intensity is preserved"
    )
    markers_preserved: bool = Field(
        default=True,
        description="Whether emotion markers (!, ...) are preserved"
    )


class RetryInfo(BaseModel):
    """Retry attempt information"""
    
    retry_count: int = Field(default=0, description="Number of retries performed")
    retry_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for retries"
    )
    retry_adjustments: List[str] = Field(
        default_factory=list,
        description="Adjustments made during retries"
    )
    final_attempt: bool = Field(
        default=False,
        description="Whether this was the final retry attempt"
    )


class TranslationResponse(BaseModel):
    """Translation response schema"""
    
    # Request tracking
    request_id: str = Field(..., description="Request identifier")
    status: TranslationStatus = Field(..., description="Translation status")
    
    # Translation result
    translated_text: str = Field(..., description="Translated text")
    
    # Language info
    detected_source_language: Optional[str] = Field(
        None,
        description="Detected source language (if auto-detected)"
    )
    language_detection: Optional[LanguageDetectionResult] = Field(
        None,
        description="Language detection details"
    )
    
    # Confidence metrics
    translation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall translation confidence"
    )
    confidence_metrics: Optional[TranslationConfidenceMetrics] = Field(
        None,
        description="Detailed confidence metrics"
    )
    
    # Emotion preservation
    emotion_preservation_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Emotion preservation score"
    )
    emotion_metrics: Optional[EmotionPreservationMetrics] = Field(
        None,
        description="Detailed emotion preservation metrics"
    )
    
    # Model info
    model_version: str = Field(..., description="Translation model version")
    fallback_model_used: bool = Field(
        default=False,
        description="Whether fallback model was used"
    )
    
    # Retry info
    retry_info: Optional[RetryInfo] = Field(
        None,
        description="Retry attempt information"
    )
    
    # Performance
    latency_ms: float = Field(..., description="Total latency in milliseconds")
    language_detection_time_ms: Optional[float] = Field(
        None,
        description="Language detection time"
    )
    translation_time_ms: float = Field(
        ...,
        description="Translation inference time"
    )
    
    # Error info (if status is FAILED or PARTIAL)
    error_message: Optional[str] = Field(
        None,
        description="Error message if translation failed"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Warning messages"
    )


# ============================================================================
# Health & Metrics Schemas
# ============================================================================


class TranslationHealthResponse(BaseModel):
    """Translation service health response"""
    
    status: str = Field(..., description="Service status")
    models_loaded: Dict[str, bool] = Field(
        ...,
        description="Translation and language detection models status"
    )
    total_requests: int = Field(..., description="Total requests processed")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate")
    retry_rate: float = Field(..., ge=0.0, le=1.0, description="Retry rate")
    average_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average translation confidence"
    )
    average_emotion_preservation: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average emotion preservation score"
    )
    active_alerts: int = Field(..., description="Number of active drift alerts")


class TranslationMetricsSnapshot(BaseModel):
    """Translation metrics snapshot"""
    
    total_requests: int = Field(..., description="Total translation requests")
    success_count: int = Field(..., description="Successful translations")
    partial_count: int = Field(..., description="Partial translations")
    failed_count: int = Field(..., description="Failed translations")
    retry_count: int = Field(..., description="Total retries")
    
    # Confidence metrics
    average_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average translation confidence"
    )
    confidence_p50: float = Field(..., description="50th percentile confidence")
    confidence_p95: float = Field(..., description="95th percentile confidence")
    
    # Emotion preservation
    average_emotion_preservation: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average emotion preservation score"
    )
    emotion_preservation_p50: float = Field(
        ...,
        description="50th percentile emotion preservation"
    )
    
    # Language distribution
    language_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of source languages"
    )
    
    # Latency metrics
    latency_p50_ms: float = Field(..., description="50th percentile latency")
    latency_p95_ms: float = Field(..., description="95th percentile latency")
    latency_p99_ms: float = Field(..., description="99th percentile latency")
    
    # Retry metrics
    retry_rate: float = Field(..., ge=0.0, le=1.0, description="Retry rate")
    retry_reasons_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of retry reasons"
    )
    
    # Drift alerts
    active_alerts: int = Field(..., description="Number of active drift alerts")


class DriftAlert(BaseModel):
    """Drift alert model"""
    
    alert_type: str = Field(..., description="Type of drift alert")
    severity: str = Field(..., description="Alert severity (low/medium/high)")
    metric_value: float = Field(..., description="Current metric value")
    threshold: float = Field(..., description="Alert threshold")
    baseline_value: Optional[float] = Field(None, description="Baseline metric value")
    message: str = Field(..., description="Alert message")
    timestamp: str = Field(..., description="Alert timestamp")


# ============================================================================
# Model Info Schema
# ============================================================================


class ModelInfo(BaseModel):
    """Translation model information"""
    
    model_name: str = Field(..., description="Model name")
    model_version: str = Field(..., description="Model version")
    device: str = Field(..., description="Device (cpu/cuda)")
    supported_languages: List[str] = Field(
        ...,
        description="Supported language codes"
    )
    max_input_length: int = Field(..., description="Maximum input length (tokens)")
    inference_count: int = Field(..., description="Total inference count")
    average_inference_time_ms: float = Field(
        ...,
        description="Average inference time"
    )
