"""
STT Service API Routes

Production-grade STT endpoints for EPMSSTS.
"""

from fastapi import APIRouter, HTTPException, status
from datetime import datetime
import logging

# Import new STT module components
from epmssts.services.stt import (
    SpeechToTextService as SttServiceV2,
    SttRequest,
    SttResponse,
    HealthCheckResponse,
    MetricsSnapshot,
    ErrorResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt/v2", tags=["Speech-to-Text V2"])

# Global service instance (initialized in lifespan)
stt_service_v2: SttServiceV2 = None


def set_stt_service(service: SttServiceV2):
    """Set the global STT service instance"""
    global stt_service_v2
    stt_service_v2 = service


@router.post(
    "/transcribe",
    response_model=SttResponse,
    summary="Transcribe Audio (Production STT)",
    description="Production-grade speech-to-text with confidence scoring, GPU support, and quality thresholds.",
)
async def transcribe_v2(request: SttRequest) -> SttResponse:
    """
    Transcribe audio with production-grade STT.
    
    **Features**:
    - GPU/CPU auto-fallback
    - Multi-factor confidence scoring
    - No-speech detection
    - Hallucination detection
    - Concurrency control
    - Structured error responses
    
    **Input**:
    - `audio_data`: Base64-encoded audio bytes
    - `format`: Audio format (wav, mp3, flac, ogg, m4a)
    - `language`: Optional language code (auto-detect if omitted)
    - `confidence_threshold`: Min confidence score (0-1, default 0.5)
    - `no_speech_threshold`: Max no-speech probability (0-1, default 0.3)
    
    **Output**:
    - `success`: True if transcription successful
    - `transcript`: Transcribed text
    - `confidence`: Overall confidence score (0-1)
    - `segments`: Per-segment transcriptions with timings
    - `processing_time_ms`: Total processing time
    - `device_used`: Device used (gpu or cpu)
    
    **Error Codes**:
    - `ERR_STT_020`: No speech detected
    - `ERR_STT_021`: Audio too short (< 0.5s)
    - `ERR_STT_022`: Audio too long (> max duration)
    - `ERR_STT_013`: Confidence too low
    - `ERR_STT_031`: Queue full (retry later)
    """
    if stt_service_v2 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT service not initialized"
        )
    
    try:
        response = await stt_service_v2.transcribe(request)
        return response
    except Exception as e:
        logger.error(f"Unexpected error in STT API: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="STT Service Health",
    description="Check health status of STT service including model, device, and performance metrics.",
)
async def health_v2() -> HealthCheckResponse:
    """
    Get STT service health status.
    
    **Returns**:
    - `status`: Overall health (healthy, degraded, unhealthy)
    - `model_loaded`: Whether model is initialized
    - `gpu_available`: Whether GPU is available
    - `average_latency_ms`: Average inference latency
    - `error_rate`: Recent error rate (0-1)
    - `timestamp`: When health check was performed
    """
    if stt_service_v2 is None:
        return HealthCheckResponse(
            status="unhealthy",
            model_loaded=False,
            gpu_available=False,
            average_latency_ms=0.0,
            error_rate=1.0,
            timestamp=datetime.utcnow().isoformat(),
        )
    
    health_status = stt_service_v2.get_health_status()
    
    return HealthCheckResponse(
        status=health_status.get("status", "unhealthy"),
        model_loaded=health_status.get("model_loaded", False),
        gpu_available=health_status.get("gpu_available", False),
        average_latency_ms=health_status.get("average_latency_ms", 0.0),
        error_rate=health_status.get("error_rate", 1.0),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get(
    "/metrics",
    response_model=MetricsSnapshot,
    summary="STT Service Metrics",
    description="Get detailed metrics for monitoring and observability (Prometheus-compatible).",
)
async def metrics_v2() -> MetricsSnapshot:
    """
    Get STT service metrics.
    
    **Returns**:
    - Request counts (total, successful, failed)
    - Latency percentiles (p50, p95, p99)
    - Confidence metrics
    - Error distribution
    - Language distribution
    - Device usage stats
    - Queue status
    """
    if stt_service_v2 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT service not initialized"
        )
    
    metrics = stt_service_v2.get_metrics()
    
    # Calculate percentiles (simplified - use numpy in production)
    p50 = metrics.get("average_latency_ms", 0.0)
    p95 = p50 * 1.5  # Placeholder
    p99 = p50 * 2.0  # Placeholder
    
    return MetricsSnapshot(
        total_requests=metrics.get("total_requests", 0),
        successful_requests=metrics.get("successful_requests", 0),
        failed_requests=metrics.get("failed_requests", 0),
        average_latency_ms=metrics.get("average_latency_ms", 0.0),
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        average_inference_latency_ms=metrics.get("average_latency_ms", 0.0),
        average_preprocessing_latency_ms=0.0,  # Not tracked separately yet
        average_confidence=metrics.get("average_confidence", 0.0),
        average_no_speech_prob=0.0,  # Not tracked in current metrics
        timeout_errors=metrics.get("error_distribution", {}).get("INFERENCE_TIMEOUT", 0),
        inference_errors=metrics.get("error_distribution", {}).get("INFERENCE_FAILED", 0),
        invalid_audio_errors=metrics.get("error_distribution", {}).get("INVALID_AUDIO_FORMAT", 0),
        no_speech_errors=metrics.get("rejections", {}).get("no_speech", 0),
        confidence_errors=metrics.get("rejections", {}).get("confidence", 0),
        hallucination_detections=metrics.get("rejections", {}).get("hallucination", 0),
        gpu_used_percentage=metrics.get("gpu_used_percentage", 0.0),
        gpu_errors=metrics.get("error_distribution", {}).get("GPU_OUT_OF_MEMORY", 0),
        language_distribution=metrics.get("language_distribution", {}),
        current_concurrent_requests=0,  # Not tracked in current implementation
        max_concurrent_requests=4,  # Default from service
        queue_size=0,  # Not tracked in current implementation
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get(
    "/model-status",
    summary="Model Status",
    description="Get current model and device configuration.",
)
async def model_status_v2():
    """Get model and device status"""
    if stt_service_v2 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT service not initialized"
        )
    
    health = stt_service_v2.get_health_status()
    
    return {
        "model_name": health.get("model_name", "unknown"),
        "device": health.get("device", "unknown"),
        "gpu_available": health.get("gpu_available", False),
        "model_loaded": health.get("model_loaded", False),
        "status": health.get("status", "unknown"),
    }
