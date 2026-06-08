"""
Emotion Intelligence Service Schemas

Pydantic models for input validation and output contracts.
Enterprise-grade emotion classification with uncertainty quantification.
"""

from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class EmotionLabel(str, Enum):
    """Supported emotion labels"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    EXCITED = "excited"
    FEARFUL = "fearful"  # Optional, if model supports
    SURPRISED = "surprised"  # Optional, if model supports


class EnergyBand(str, Enum):
    """Energy band classification from audio preprocessing"""
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class AnalysisStatus(str, Enum):
    """Status of emotion analysis"""
    SUCCESS = "success"
    LOW_CONFIDENCE = "low_confidence"
    HIGH_UNCERTAINTY = "high_uncertainty"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


class EmotionAnalysisRequest(BaseModel):
    """HTTP request contract for emotion analysis"""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "audio_id": "req-12345",
            "waveform_ref": "base64_or_internal_ref",
            "mel_features_ref": "base64_or_internal_ref",
            "transcript": "I am feeling great today",
            "stt_confidence": 0.92,
            "energy_band": "normal",
            "quality_score": 85,
            "duration_seconds": 3.5
        }
    })
    
    # Required identifiers
    audio_id: str = Field(
        description="Unique audio identifier for tracking",
        min_length=1,
    )
    
    # Audio features
    waveform_ref: Optional[str] = Field(
        default=None,
        description="Waveform data reference (base64 or internal storage ref)",
    )
    
    mel_features_ref: Optional[str] = Field(
        default=None,
        description="Mel-spectrogram features reference",
    )
    
    # Text features
    transcript: str = Field(
        default="",
        description="Transcribed text from STT service",
    )
    
    # STT metadata
    stt_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from STT service (0-1)",
    )
    
    # Audio metadata
    energy_band: EnergyBand = Field(
        default=EnergyBand.NORMAL,
        description="Energy band classification (very_low, low, normal, high)",
    )
    
    quality_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Audio quality score from preprocessing (0-100)",
    )
    
    duration_seconds: float = Field(
        default=0.0,
        gt=0.0,
        description="Audio duration in seconds",
    )
    
    # Optional overrides
    min_confidence_threshold: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for accepting results",
    )
    
    max_entropy_threshold: Optional[float] = Field(
        default=0.8,
        ge=0.0,
        description="Maximum entropy before flagging as uncertain",
    )
    
    @field_validator("waveform_ref", "mel_features_ref")
    @classmethod
    def validate_features(cls, v: Optional[str]) -> Optional[str]:
        """Validate feature references not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("Feature reference cannot be empty string")
        return v


class ModelPrediction(BaseModel):
    """Single model prediction result"""
    
    probabilities: Dict[str, float] = Field(
        description="Probability distribution over emotion classes",
    )
    
    entropy: float = Field(
        ge=0.0,
        description="Shannon entropy of prediction distribution (higher = more uncertain)",
    )
    
    model_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model-specific confidence score",
    )
    
    model_name: str = Field(
        description="Name of model that produced this prediction",
    )
    
    inference_time_ms: float = Field(
        description="Inference latency in milliseconds",
    )


class UncertaintyMetrics(BaseModel):
    """Uncertainty quantification metrics"""
    
    entropy: float = Field(
        ge=0.0,
        description="Shannon entropy of final distribution",
    )
    
    max_prob_margin: float = Field(
        ge=0.0,
        le=1.0,
        description="Difference between top-1 and top-2 probabilities",
    )
    
    confidence_dispersion: float = Field(
        ge=0.0,
        description="Standard deviation of probability distribution",
    )
    
    disagreement_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Inter-model disagreement metric (0=perfect agreement, 1=complete disagreement)",
    )
    
    uncertainty_flag: bool = Field(
        description="True if uncertainty exceeds acceptable threshold",
    )


class CalibrationInfo(BaseModel):
    """Calibration adjustments applied"""
    
    temperature_audio: float = Field(
        description="Temperature scaling factor for audio model",
    )
    
    temperature_text: float = Field(
        description="Temperature scaling factor for text model",
    )
    
    per_class_adjustments: Dict[str, float] = Field(
        description="Per-class threshold adjustments applied",
    )
    
    calibration_version: str = Field(
        description="Version of calibration parameters",
    )


class FusionWeights(BaseModel):
    """Adaptive fusion weights computed""" 
    
    audio_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="Weight assigned to audio model predictions",
    )
    
    text_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="Weight assigned to text model predictions",
    )
    
    fusion_method: str = Field(
        description="Method used for fusion (e.g., 'bayesian_adaptive')",
    )
    
    weight_factors: Dict[str, float] = Field(
        description="Factors that influenced weight computation",
    )


class EmotionAnalysisResponse(BaseModel):
    """HTTP response contract for emotion analysis"""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "success",
            "label": "happy",
            "confidence": 0.87,
            "probabilities": {
                "happy": 0.87,
                "excited": 0.08,
                "neutral": 0.03,
                "sad": 0.01,
                "angry": 0.01
            },
            "uncertainty_metrics": {
                "entropy": 0.23,
                "max_prob_margin": 0.79,
                "uncertainty_flag": False
            }
        }
    })
    
    # Core results
    status: AnalysisStatus = Field(
        description="Analysis status",
    )
    
    label: str = Field(
        description="Predicted emotion label",
    )
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0-1)",
    )
    
    probabilities: Dict[str, float] = Field(
        description="Final probability distribution over all emotion classes",
    )
    
    # Uncertainty quantification
    uncertainty_metrics: UncertaintyMetrics = Field(
        description="Detailed uncertainty metrics",
    )
    
    # Model details
    model_predictions: Optional[List[ModelPrediction]] = Field(
        default=None,
        description="Individual model predictions (for debugging/interpretability)",
    )
    
    calibration_info: Optional[CalibrationInfo] = Field(
        default=None,
        description="Calibration adjustments applied",
    )
    
    fusion_weights: Optional[FusionWeights] = Field(
        default=None,
        description="Adaptive fusion weights used",
    )
    
    # Timing
    processing_time_ms: float = Field(
        description="Total processing time in milliseconds",
    )
    
    audio_inference_time_ms: float = Field(
        description="Audio model inference time",
    )
    
    text_inference_time_ms: float = Field(
        description="Text model inference time",
    )
    
    fusion_time_ms: float = Field(
        description="Fusion computation time",
    )
    
    # Observability
    audio_id: str = Field(
        description="Audio identifier from request",
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request tracking ID",
    )
    
    # Error information
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if status is error",
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is error",
    )
    
    user_friendly_message: Optional[str] = Field(
        default=None,
        description="User-friendly status message",
    )
    
    # Model versioning
    model_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Versions of models used",
    )


class HealthCheckResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(description="Overall health status (healthy, degraded, unhealthy)")
    models_loaded: Dict[str, bool] = Field(description="Which models are loaded")
    average_latency_ms: float = Field(description="Average inference latency")
    error_rate: float = Field(ge=0.0, le=1.0, description="Recent error rate")
    neutral_rate: float = Field(ge=0.0, le=1.0, description="Rate of neutral predictions")
    uncertainty_rate: float = Field(ge=0.0, le=1.0, description="Rate of high-uncertainty predictions")
    timestamp: str = Field(description="ISO 8601 timestamp")


class MetricsSnapshot(BaseModel):
    """Prometheus-compatible metrics snapshot"""
    
    # Request counts
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Latency
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    
    # Inference breakdown
    average_audio_inference_ms: float
    average_text_inference_ms: float
    average_fusion_ms: float
    
    # Emotion distribution
    emotion_distribution: Dict[str, int] = Field(
        description="Count of each emotion predicted",
    )
    
    # Quality metrics
    average_confidence: float
    average_entropy: float
    uncertainty_rate: float
    
    # Drift metrics
    neutral_collapse_rate: float = Field(
        description="Rate of neutral predictions (drift indicator)",
    )
    
    entropy_spike_count: int = Field(
        description="Count of entropy spikes detected",
    )
    
    disagreement_high_count: int = Field(
        description="Count of high inter-model disagreement",
    )
    
    # Ensemble metrics
    average_audio_weight: float
    average_text_weight: float
    
    # Error distribution
    error_distribution: Dict[str, int]
    
    timestamp: str


class ModelVersionInfo(BaseModel):
    """Model version information"""
    
    audio_model_primary: str = Field(description="Primary audio model name and version")
    audio_model_secondary: Optional[str] = Field(description="Secondary audio model (if used)")
    text_model: str = Field(description="Text model name and version")
    calibration_version: str = Field(description="Calibration parameters version")
    fusion_version: str = Field(description="Fusion algorithm version")
    service_version: str = Field(description="Emotion service version")


class DriftAlert(BaseModel):
    """Drift detection alert"""
    
    alert_type: str = Field(description="Type of drift detected")
    severity: str = Field(description="Severity level (low, medium, high)")
    metric_value: float = Field(description="Value of metric that triggered alert")
    threshold: float = Field(description="Threshold that was exceeded")
    timestamp: str = Field(description="When alert was triggered")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


# Import for type annotations
from typing import Any
