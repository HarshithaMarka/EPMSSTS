"""
Pydantic schemas for Audio Preprocessing Service input/output.

Strict validation contracts for API boundaries.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class EnergyBand(str, Enum):
    """Energy classification bands."""
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class AudioPreprocessRequest(BaseModel):
    """Request model for audio preprocessing endpoint."""
    
    # File handling
    file_path: Optional[str] = Field(
        None,
        description="Local file path (for file-based requests)"
    )
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate file path if provided."""
        if v is not None and len(v) > 512:
            raise ValueError("File path exceeds maximum length (512 chars)")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "/path/to/audio.wav"
            }
        }


class SignalMetrics(BaseModel):
    """Signal metrics extracted from audio."""
    
    rms_dbfs: float = Field(
        ...,
        description="RMS level in dBFS",
        ge=-120.0,
        le=0.0
    )
    peak_dbfs: float = Field(
        ...,
        description="Peak level in dBFS",
        ge=-120.0,
        le=1.0
    )
    snr_estimate: float = Field(
        ...,
        description="Estimated Signal-to-Noise Ratio in dB",
        ge=0.0,
        le=100.0
    )
    spectral_centroid: float = Field(
        ...,
        description="Spectral centroid in Hz",
        ge=0.0,
        le=8000.0
    )
    zero_crossing_rate: float = Field(
        ...,
        description="Zero crossing rate (0-1)",
        ge=0.0,
        le=1.0
    )
    energy_variance: float = Field(
        ...,
        description="Energy variance across time",
        ge=0.0
    )
    pitch_mean: float = Field(
        ...,
        description="Mean pitch in Hz",
        ge=0.0,
        le=500.0
    )
    pitch_variance: float = Field(
        ...,
        description="Pitch variance",
        ge=0.0
    )


class AudioPreprocessResponse(BaseModel):
    """Response model for successful audio preprocessing."""
    
    status: str = Field("success", description="Status of preprocessing")
    
    # Audio metadata
    duration_seconds: float = Field(
        ...,
        description="Duration of audio in seconds",
        gt=0.0,
        le=60.0
    )
    sample_rate: int = Field(
        16000,
        description="Sample rate in Hz"
    )
    
    # Signal metrics
    metrics: SignalMetrics = Field(..., description="Extracted signal metrics")
    
    # Energy classification
    energy_band: EnergyBand = Field(
        ...,
        description="Energy band classification"
    )
    
    # Quality indicators
    silence_ratio: float = Field(
        ...,
        description="Ratio of silence frames (0-1)",
        ge=0.0,
        le=1.0
    )
    quality_score: int = Field(
        ...,
        description="Quality score (0-100)",
        ge=0,
        le=100
    )
    
    # Performance metrics
    preprocessing_latency_ms: float = Field(
        ...,
        description="Total preprocessing latency in milliseconds",
        ge=0.0
    )
    
    # Data shapes (for downstream processing)
    waveform_shape: List[int] = Field(
        ...,
        description="Waveform shape [samples]"
    )
    mel_shape: List[int] = Field(
        ...,
        description="Mel-spectrogram shape [frames, bins]"
    )
    
    # Observability
    request_id: str = Field(
        ...,
        description="Unique request identifier"
    )
    timestamp: datetime = Field(
        ...,
        description="Processing timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "duration_seconds": 5.2,
                "sample_rate": 16000,
                "metrics": {
                    "rms_dbfs": -20.5,
                    "peak_dbfs": -3.2,
                    "snr_estimate": 18.5,
                    "spectral_centroid": 1200.5,
                    "zero_crossing_rate": 0.15,
                    "energy_variance": 0.25,
                    "pitch_mean": 120.5,
                    "pitch_variance": 50.2
                },
                "energy_band": "normal",
                "silence_ratio": 0.15,
                "quality_score": 82,
                "preprocessing_latency_ms": 45.3,
                "waveform_shape": [83200],
                "mel_shape": [325, 128],
                "request_id": "req_abc123def456",
                "timestamp": "2026-03-02T10:30:45.123456"
            }
        }


class AudioPreprocessErrorResponse(BaseModel):
    """Response model for preprocessing failures."""
    
    status: str = Field("error", description="Status of request")
    reason_code: str = Field(
        ...,
        description="Structured error reason code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    details: dict = Field(
        default_factory=dict,
        description="Additional error context"
    )
    
    # Observability
    request_id: str = Field(
        ...,
        description="Unique request identifier"
    )
    timestamp: datetime = Field(
        ...,
        description="Error timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "reason_code": "ERR_004_DURATION_TOO_SHORT",
                "message": "Duration 0.8s is below minimum 1.5s",
                "details": {
                    "duration": 0.8,
                    "min": 1.5,
                    "max": 60.0
                },
                "request_id": "req_abc123def456",
                "timestamp": "2026-03-02T10:30:45.123456"
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response."""
    
    status: str = Field("healthy", description="Service health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Service version")


class MetricsResponse(BaseModel):
    """Prometheus-compatible metrics response."""
    
    total_requests: int = Field(0, description="Total requests processed")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    
    p50_latency_ms: float = Field(0.0, description="P50 latency in ms")
    p95_latency_ms: float = Field(0.0, description="P95 latency in ms")
    p99_latency_ms: float = Field(0.0, description="P99 latency in ms")
    
    avg_quality_score: float = Field(0.0, description="Average quality score")
    low_quality_count: int = Field(0, description="Count of low quality (<50) samples")
    
    energy_band_distribution: dict = Field(
        default_factory=dict,
        description="Count by energy band"
    )
