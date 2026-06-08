"""
Production-grade orchestration schemas.

Defines strict request/response contracts, stage trace records,
confidence propagation structures, SLA contracts, and failure table entries.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class PipelineStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"


class StageName(str, Enum):
    AUDIO_PREPROCESSING = "audio_preprocessing"
    STT = "stt"
    EMOTION = "emotion"
    TRANSLATION = "translation"
    TTS = "tts"


class StageExecutionStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"


class PipelineProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_file: str = Field(..., min_length=1, description="Base64 audio payload")
    target_language: str = Field(..., min_length=2, max_length=10)
    request_id: str = Field(..., min_length=8, max_length=128)

    @field_validator("target_language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.lower().strip()


class ConfidenceSummary(BaseModel):
    stt_confidence: float = Field(0.0, ge=0.0, le=1.0)
    emotion_confidence: float = Field(0.0, ge=0.0, le=1.0)
    translation_confidence: float = Field(0.0, ge=0.0, le=1.0)
    tts_validation_confidence: float = Field(0.0, ge=0.0, le=1.0)
    system_confidence: float = Field(0.0, ge=0.0, le=1.0)
    uncertainty_flag: bool = False
    confidence_weights: Dict[str, float] = Field(default_factory=dict)


class StageTraceRecord(BaseModel):
    stage_name: StageName
    started_at: datetime
    ended_at: datetime
    latency_ms: float = Field(..., ge=0.0)
    status: StageExecutionStatus
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    retry_count: int = Field(default=0, ge=0)
    fallback_used: bool = False
    fallback_type: Optional[str] = None
    error: Optional[str] = None
    sla_target_ms: int = Field(..., ge=1)
    sla_breached: bool = False


class PipelineProcessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PipelineStatus
    transcript: str
    emotion: str
    translation: str
    audio_output_url: Optional[str] = None
    confidence_summary: ConfidenceSummary
    stage_latencies: Dict[str, float]
    total_latency_ms: float = Field(..., ge=0.0)
    request_trace_id: str


class PipelineTraceResponse(BaseModel):
    request_trace_id: str
    request_id: str
    status: PipelineStatus
    created_at: datetime
    updated_at: datetime
    total_latency_ms: float = Field(..., ge=0.0)
    stage_traces: List[StageTraceRecord]
    confidence_summary: ConfidenceSummary
    metadata: Dict[str, str] = Field(default_factory=dict)


class StageSLAConfig(BaseModel):
    stage_name: StageName
    timeout_ms: int = Field(..., ge=50)
    target_p95_ms: int = Field(..., ge=50)


class OrchestrationSLAConfig(BaseModel):
    total_pipeline_p95_ms: int = Field(default=5000, ge=500)
    stage_sla: Dict[StageName, StageSLAConfig]


class FailureModeRow(BaseModel):
    stage: StageName
    failure_type: str
    impact: str
    fallback: str
    status_returned: PipelineStatus


class PipelineStatusResponse(BaseModel):
    status: str
    active_requests: int = Field(..., ge=0)
    max_concurrency: int = Field(..., ge=1)
    total_requests: int = Field(..., ge=0)
    degraded_rate: float = Field(..., ge=0.0, le=1.0)
    failure_rate: float = Field(..., ge=0.0, le=1.0)
    sla_breach_count: int = Field(..., ge=0)
    circuit_states: Dict[str, str] = Field(default_factory=dict)


class PipelineHealthResponse(BaseModel):
    status: str
    redis_connected: bool
    dependencies: Dict[str, bool]
    uptime_seconds: float = Field(..., ge=0.0)


class PipelineMetricsResponse(BaseModel):
    pipeline_latency_histogram: Dict[str, int] = Field(default_factory=dict)
    stage_failure_rate: Dict[str, float] = Field(default_factory=dict)
    stage_retry_rate: Dict[str, float] = Field(default_factory=dict)
    degraded_response_rate: float = Field(..., ge=0.0, le=1.0)
    confidence_distribution: Dict[str, int] = Field(default_factory=dict)
    sla_breach_count: int = Field(..., ge=0)
    requests_total: int = Field(..., ge=0)
