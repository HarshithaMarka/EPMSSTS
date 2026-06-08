"""
TTS Service API Schemas

Pydantic models for TTS service request/response contracts.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List
from datetime import datetime


# ============ Request Models ============

class TTSRequest(BaseModel):
    """TTS synthesis request"""
    
    translated_text: str = Field(
        ...,
        description="Translated text to synthesize",
        min_length=1,
        max_length=5000
    )
    
    target_language: str = Field(
        ...,
        description="Target language code (e.g., 'en', 'es', 'fr')",
        pattern=r"^[a-z]{2}(-[A-Z]{2})?$"
    )
    
    emotion_label: Optional[str] = Field(
        None,
        description="Emotion label (happy, sad, angry, neutral, excited)"
    )
    
    emotion_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score of emotion prediction"
    )
    
    translation_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Translation quality confidence score"
    )
    
    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for tracking"
    )
    
    min_translation_confidence: Optional[float] = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum translation confidence threshold"
    )
    
    speaker_id: Optional[str] = Field(
        None,
        description="Speaker voice identifier (if multi-speaker TTS)"
    )
    
    prosody_intensity: Optional[float] = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Prosody adjustment intensity multiplier"
    )
    
    @field_validator("emotion_label")
    @classmethod
    def validate_emotion(cls, v):
        if v is not None:
            valid_emotions = {"happy", "sad", "angry", "neutral", "excited", "fear", "surprise", "disgust"}
            if v.lower() not in valid_emotions:
                raise ValueError(f"Invalid emotion label. Must be one of {valid_emotions}")
        return v.lower() if v else None


# ============ Response Models ============

class ProsodyProfile(BaseModel):
    """Prosody parameters applied to synthesis"""
    
    rate_multiplier: float = Field(
        1.0,
        description="Speech rate multiplier (1.0 = normal)"
    )
    
    pitch_shift: float = Field(
        0.0,
        description="Pitch shift in semitones"
    )
    
    energy_scale: float = Field(
        1.0,
        description="Energy/volume scale factor"
    )
    
    pitch_variance: float = Field(
        1.0,
        description="Pitch variance scaling"
    )
    
    emotion_intensity: float = Field(
        1.0,
        description="Overall emotion intensity applied"
    )


class WaveformQualityMetrics(BaseModel):
    """Audio waveform quality validation metrics"""
    
    duration_seconds: float = Field(
        ...,
        description="Audio duration in seconds"
    )
    
    file_size_kb: float = Field(
        ...,
        description="Audio file size in kilobytes"
    )
    
    rms_amplitude: float = Field(
        ...,
        description="RMS amplitude (root mean square)"
    )
    
    peak_amplitude: float = Field(
        ...,
        description="Peak amplitude"
    )
    
    is_clipping: bool = Field(
        ...,
        description="Whether audio clipping detected"
    )
    
    spectral_flatness: float = Field(
        ...,
        description="Spectral flatness measure (0=tonal, 1=noise)"
    )
    
    is_valid: bool = Field(
        ...,
        description="Overall waveform validity"
    )
    
    validation_errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors if any"
    )


class FallbackInfo(BaseModel):
    """Information about fallback usage"""
    
    fallback_used: bool = Field(
        ...,
        description="Whether fallback engine was used"
    )
    
    primary_engine_error: Optional[str] = Field(
        None,
        description="Primary engine failure reason"
    )
    
    engine_used: str = Field(
        ...,
        description="Engine that successfully generated audio"
    )
    
    retry_count: int = Field(
        0,
        description="Number of retries attempted"
    )


class TTSResponse(BaseModel):
    """TTS synthesis response"""
    
    status: str = Field(
        ...,
        description="Response status: success, partial, failed"
    )
    
    audio_path: Optional[str] = Field(
        None,
        description="Path to generated audio file"
    )
    
    audio_base64: Optional[str] = Field(
        None,
        description="Base64-encoded audio data (if requested)"
    )
    
    prosody_profile: ProsodyProfile = Field(
        ...,
        description="Prosody parameters applied"
    )
    
    waveform_quality: Optional[WaveformQualityMetrics] = Field(
        None,
        description="Waveform quality validation metrics"
    )
    
    fallback_info: FallbackInfo = Field(
        ...,
        description="Fallback chain information"
    )
    
    latency_ms: float = Field(
        ...,
        description="Total synthesis latency in milliseconds"
    )
    
    latency_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Latency breakdown by stage"
    )
    
    model_version: str = Field(
        ...,
        description="TTS model version used"
    )
    
    request_id: Optional[str] = Field(
        None,
        description="Request identifier"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if synthesis failed"
    )


# ============ Health & Metrics Models ============

class TTSHealthResponse(BaseModel):
    """TTS service health status"""
    
    status: str = Field(
        ...,
        description="Service status: healthy, degraded, unhealthy"
    )
    
    models_loaded: Dict[str, bool] = Field(
        ...,
        description="Status of loaded models"
    )
    
    gpu_available: bool = Field(
        ...,
        description="Whether GPU is available"
    )
    
    gpu_memory_used_mb: Optional[float] = Field(
        None,
        description="GPU memory used in MB"
    )
    
    error_rate: float = Field(
        ...,
        description="Recent error rate (0-1)"
    )
    
    fallback_rate: float = Field(
        ...,
        description="Fallback usage rate (0-1)"
    )
    
    average_latency_ms: float = Field(
        ...,
        description="Average synthesis latency"
    )
    
    uptime_seconds: float = Field(
        ...,
        description="Service uptime in seconds"
    )


class TTSMetricsSnapshot(BaseModel):
    """TTS service metrics snapshot"""
    
    total_requests: int = Field(
        ...,
        description="Total synthesis requests"
    )
    
    success_count: int = Field(
        ...,
        description="Successful syntheses"
    )
    
    partial_count: int = Field(
        ...,
        description="Partial success (fallback used)"
    )
    
    failed_count: int = Field(
        ...,
        description="Failed syntheses"
    )
    
    fallback_count: int = Field(
        ...,
        description="Number of fallback uses"
    )
    
    average_latency_ms: float = Field(
        ...,
        description="Average synthesis latency"
    )
    
    latency_p50_ms: float = Field(
        ...,
        description="50th percentile latency"
    )
    
    latency_p95_ms: float = Field(
        ...,
        description="95th percentile latency"
    )
    
    latency_p99_ms: float = Field(
        ...,
        description="99th percentile latency"
    )
    
    emotion_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of emotions rendered"
    )
    
    language_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of languages synthesized"
    )
    
    error_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of error types"
    )
    
    average_audio_duration_seconds: float = Field(
        ...,
        description="Average generated audio duration"
    )
    
    average_audio_size_kb: float = Field(
        ...,
        description="Average audio file size"
    )
    
    waveform_validation_failures: int = Field(
        ...,
        description="Number of waveform validation failures"
    )


# ============ Configuration Models ============

class ProsodyConfig(BaseModel):
    """Prosody configuration for emotions"""
    
    emotion: str
    rate_multiplier: float = 1.0
    pitch_shift: float = 0.0
    energy_scale: float = 1.0
    pitch_variance: float = 1.0
    description: str = ""


class TTSEngineConfig(BaseModel):
    """TTS engine configuration"""
    
    model_name: str
    device: str = "cuda"
    sample_rate: int = 16000
    channels: int = 1
    bit_depth: int = 16
    max_text_length: int = 5000
    synthesis_timeout_seconds: float = 10.0
    enable_gpu: bool = True
    enable_fp16: bool = True
