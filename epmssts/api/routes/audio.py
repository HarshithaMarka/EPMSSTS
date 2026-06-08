"""
Audio preprocessing API routes.

Exposes preprocessing, health check, and metrics endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os
from datetime import datetime

from epmssts.services.audio.preprocessing_service import AudioPreprocessingService
from epmssts.services.audio.schemas import (
    AudioPreprocessResponse,
    AudioPreprocessErrorResponse,
    HealthCheckResponse,
    MetricsResponse,
)
from epmssts.services.audio.logging_config import get_logger

logger = get_logger(__name__)

# Initialize service
preprocessing_service = AudioPreprocessingService()

# Create router
router = APIRouter(prefix="/audio", tags=["audio"])


@router.post(
    "/preprocess",
    response_model=AudioPreprocessResponse,
    responses={
        400: {"model": AudioPreprocessErrorResponse},
        413: {"model": AudioPreprocessErrorResponse},
        422: {"model": AudioPreprocessErrorResponse},
        500: {"model": AudioPreprocessErrorResponse},
    },
    summary="Preprocess audio file",
    description="Validate, clean, and extract features from audio file"
)
async def preprocess_audio(file: UploadFile = File(...)):
    """
    Preprocess audio file.
    
    - **file**: Audio file (WAV, MP3, FLAC, M4A), max 10MB
    
    Returns:
    - Processed waveform metadata
    - Signal metrics (RMS, peak, SNR, etc.)
    - Quality score (0-100)
    - Mel-spectrogram shape
    - Preprocessing latency
    """
    try:
        # Check file size
        contents = await file.read()
        if len(contents) > 10_000_000:
            raise HTTPException(
                status_code=413,
                detail={
                    "status": "error",
                    "reason_code": "ERR_006_FILE_TOO_LARGE",
                    "message": f"File size exceeds 10MB",
                    "request_id": "unknown",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            # Process
            response, internal_data = preprocessing_service.preprocess(tmp_path)
            
            # Check if error response
            if response.status == "error":
                raise HTTPException(
                    status_code=400,
                    detail=response.dict()
                )
            
            return response
        
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Preprocess endpoint failed", exc=e)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "reason_code": "ERR_999_INTERNAL_ERROR",
                "message": str(e),
                "request_id": "unknown",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check service health status"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
    - Service status (healthy/degraded)
    - Timestamp
    - Service version
    """
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Service metrics",
    description="Get service metrics and statistics"
)
async def get_metrics():
    """
    Get service metrics.
    
    Returns metrics for observability:
    - Total/successful/failed requests
    - Latency percentiles (p50, p95, p99)
    - Average quality score
    - Energy band distribution
    - Error code distribution
    """
    metrics_summary = preprocessing_service.get_metrics_summary()
    
    return MetricsResponse(
        total_requests=metrics_summary["total_requests"],
        successful_requests=metrics_summary["successful_requests"],
        failed_requests=metrics_summary["failed_requests"],
        p50_latency_ms=metrics_summary["latency"]["p50_ms"],
        p95_latency_ms=metrics_summary["latency"]["p95_ms"],
        p99_latency_ms=metrics_summary["latency"]["p99_ms"],
        avg_quality_score=metrics_summary["quality"]["avg_score"],
        low_quality_count=metrics_summary["quality"]["low_quality_count"],
        energy_band_distribution=metrics_summary["energy_bands"],
    )


# Import Path at module level
from pathlib import Path
