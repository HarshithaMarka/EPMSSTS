"""
STT Service Schemas

Pydantic models for Speech-to-Text service input validation and output contracts.
Designed for production-grade API contracts.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import json


class AudioFormat(str, Enum):
    """Supported audio formats"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"


class LanguageCode(str, Enum):
    """ISO 639-1 language codes"""
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    IT = "it"
    PT = "pt"
    JA = "ja"
    ZH = "zh"
    RU = "ru"
    AR = "ar"
    HI = "hi"
    KO = "ko"


class DeviceType(str, Enum):
    """Available compute devices"""
    GPU = "gpu"
    CPU = "cpu"
    AUTO = "auto"


class ModelSize(str, Enum):
    """Whisper model sizes"""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGE_V3 = "large-v3"


class SttRequest(BaseModel):
    """HTTP request contract for STT service"""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "audio_data": "base64_encoded_audio_bytes",
            "format": "wav",
            "language": "en",
            "confidence_threshold": 0.5
        }
    })
    
    # Required audio data
    audio_data: str = Field(
        description="Base64 encoded audio bytes",
        min_length=1,
    )
    
    # Audio format specification
    format: AudioFormat = Field(
        default=AudioFormat.WAV,
        description="Audio format (wav, mp3, flac, ogg, m4a)",
    )
    
    # Language specification (optional - will detect if not provided)
    language: Optional[LanguageCode] = Field(
        default=None,
        description="Expected language (ISO 639-1). If empty, auto-detect.",
    )
    
    # Quality thresholds
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score required (0-1)",
    )
    
    no_speech_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Maximum no-speech probability accepted (0-1)",
    )
    
    # Optional settings
    request_id: Optional[str] = Field(
        default=None,
        description="Client request ID for correlation and debugging",
    )
    
    max_duration_seconds: float = Field(
        default=600.0,
        gt=0,
        le=3600,
        description="Maximum allowed audio duration in seconds",
    )
    
    @field_validator("confidence_threshold", "no_speech_threshold")
    @classmethod
    def validate_thresholds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Threshold must be between 0 and 1")
        return v


class TranscriptionSegment(BaseModel):
    """Individual segment in transcription"""
    
    text: str = Field(description="Transcribed text for this segment")
    start_time: float = Field(description="Segment start time in seconds")
    end_time: float = Field(description="Segment end time in seconds")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this segment (0-1)",
    )
    no_speech_prob: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability this segment contains no speech (0-1)",
    )


class ModelStatusInfo(BaseModel):
    """Information about current model status"""
    
    is_loaded: bool = Field(description="Whether model is loaded and ready")
    model_name: str = Field(description="Name of loaded model")
    model_size: str = Field(description="Size of model (tiny, base, small, medium, large, large-v3)")
    device_type: str = Field(description="Current compute device (gpu, cpu)")
    is_gpu_available: bool = Field(description="Whether GPU is available")
    model_memory_mb: Optional[float] = Field(
        default=None,
        description="Approximate model memory usage in MB",
    )
    quantization: Optional[str] = Field(
        default=None,
        description="Quantization method if applied (e.g., int8, float16)",
    )


class SttResponse(BaseModel):
    """HTTP response contract for STT service"""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "transcript": "Hello, how are you today?",
            "confidence": 0.92,
            "language": "en",
            "processing_time_ms": 245,
            "device_used": "gpu"
        }
    })
    
    # Core output
    success: bool = Field(description="Whether transcription succeeded")
    
    # Transcription result
    transcript: str = Field(
        default="",
        description="Full transcribed text (empty if failed)",
    )
    
    # Confidence metrics
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0-1)",
    )
    
    no_speech_prob: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probability of no speech in audio (0-1)",
    )
    
    # Language detection
    language: str = Field(
        default="en",
        description="Detected language (ISO 639-1 code)",
    )
    
    # Temporal breakdown
    segments: List[TranscriptionSegment] = Field(
        default_factory=list,
        description="Per-segment transcriptions with timings",
    )
    
    # Processing metrics
    processing_time_ms: float = Field(
        description="Total processing time in milliseconds",
    )
    
    device_used: str = Field(
        description="Compute device used (gpu, cpu)",
    )
    
    audio_duration_seconds: float = Field(
        description="Duration of input audio in seconds",
    )
    
    # Error information
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if failed (ERR_STT_*)",
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error message if failed",
    )
    
    user_friendly_message: Optional[str] = Field(
        default=None,
        description="User-friendly error message if failed",
    )
    
    # Observability
    request_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracking",
    )
    
    # Quality indicators
    is_hallucination_detected: bool = Field(
        default=False,
        description="Whether potential hallucination detected",
    )
    
    hallucination_indicators: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Details about hallucination detection",
    )
    
    # Metadata
    model_name: Optional[str] = Field(
        default=None,
        description="Model used for this transcription",
    )
    
    inference_duration_ms: Optional[float] = Field(
        default=None,
        description="Inference only duration (excluding preprocessing)",
    )


class HealthCheckResponse(BaseModel):
    """Response for health check endpoint"""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "healthy",
            "model_loaded": True,
            "gpu_available": True,
            "average_latency_ms": 234.5,
            "error_rate": 0.01
        }
    })
    
    status: str = Field(description="Overall health status (healthy, degraded, unhealthy)")
    model_loaded: bool = Field(description="Whether model is loaded")
    gpu_available: bool = Field(description="Whether GPU is available")
    average_latency_ms: float = Field(description="Average inference latency in ms")
    error_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Recent error rate (0-1)",
    )
    timestamp: str = Field(description="ISO 8601 timestamp of check")


class MetricsSnapshot(BaseModel):
    """Snapshot of service metrics for Prometheus-compatible endpoint"""
    
    # Request counts
    total_requests: int = Field(description="Total requests processed")
    successful_requests: int = Field(description="Successful requests")
    failed_requests: int = Field(description="Failed requests")
    
    # Performance
    average_latency_ms: float = Field(description="Average request latency in ms")
    p50_latency_ms: float = Field(description="50th percentile latency")
    p95_latency_ms: float = Field(description="95th percentile latency")
    p99_latency_ms: float = Field(description="99th percentile latency")
    
    # Inference
    average_inference_latency_ms: float = Field(description="Average inference time")
    average_preprocessing_latency_ms: float = Field(description="Average preprocessing time")
    
    # Confidence metrics
    average_confidence: float = Field(description="Average confidence score")
    average_no_speech_prob: float = Field(description="Average no-speech probability")
    
    # Failures
    timeout_errors: int = Field(description="Number of timeout errors")
    inference_errors: int = Field(description="Number of inference errors")
    invalid_audio_errors: int = Field(description="Number of invalid audio errors")
    no_speech_errors: int = Field(description="Number of no-speech errors")
    confidence_errors: int = Field(description="Number of low-confidence errors")
    hallucination_detections: int = Field(description="Number of hallucinations detected")
    
    # Device usage
    gpu_used_percentage: float = Field(description="Percentage of requests using GPU")
    gpu_errors: int = Field(description="Number of GPU-related errors")
    
    # Language distribution
    language_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Language code -> count",
    )
    
    # Concurrency
    current_concurrent_requests: int = Field(description="Currently processing requests")
    max_concurrent_requests: int = Field(description="Max concurrent capacity")
    queue_size: int = Field(description="Requests waiting in queue")
    
    timestamp: str = Field(description="ISO 8601 timestamp of snapshot")


class ModelConfigRequest(BaseModel):
    """Request to update model configuration"""
    
    model_size: Optional[ModelSize] = Field(
        default=None,
        description="Desired model size",
    )
    
    device_type: Optional[DeviceType] = Field(
        default=DeviceType.AUTO,
        description="Desired compute device",
    )
    
    quantization: Optional[str] = Field(
        default=None,
        description="Quantization method (int8, float16, None)",
    )
    
    reload: bool = Field(
        default=False,
        description="Whether to reload model immediately",
    )


class ModelConfigResponse(BaseModel):
    """Response for model configuration change"""
    
    success: bool = Field(description="Whether config was applied")
    message: str = Field(description="Status message")
    previous_config: ModelStatusInfo = Field(description="Previous model config")
    new_config: Optional[ModelStatusInfo] = Field(description="New model config after change")
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


class ErrorResponse(BaseModel):
    """Standardized error response format"""
    
    success: bool = Field(default=False, description="Will always be False for errors")
    error_code: str = Field(description="Error code (ERR_STT_*)")
    error_message: str = Field(description="Technical error message")
    user_friendly_message: str = Field(description="User-friendly error message")
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details",
    )
    timestamp: str = Field(description="When error occurred (ISO 8601)")
