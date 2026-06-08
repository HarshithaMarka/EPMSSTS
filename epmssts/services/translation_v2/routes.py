"""
Translation Intelligence API Routes

FastAPI endpoints for translation service.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from .translation_service import TranslationService
from .schemas import (
    TranslationRequest,
    TranslationResponse,
    TranslationHealthResponse,
    TranslationMetricsSnapshot,
    DriftAlert,
)


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v2/translation", tags=["Translation Intelligence"])

# Global service instance (initialized on startup)
_translation_service: TranslationService = None


def get_translation_service() -> TranslationService:
    """Dependency to get translation service"""
    global _translation_service
    if _translation_service is None:
        raise HTTPException(
            status_code=503,
            detail="Translation service not initialized"
        )
    return _translation_service


def initialize_translation_service(
    model_name: str = "facebook/nllb-200-distilled-600M",
    device: str = "cuda",
    fasttext_model_path: str = None,
):
    """Initialize translation service (call on app startup)"""
    global _translation_service
    logger.info("Initializing translation service...")
    _translation_service = TranslationService(
        model_name=model_name,
        device=device,
        fasttext_model_path=fasttext_model_path,
    )
    logger.info("Translation service initialized")


@router.post("/translate", response_model=TranslationResponse)
async def translate_text(
    request: TranslationRequest,
    service: TranslationService = Depends(get_translation_service)
) -> TranslationResponse:
    """
    Translate text with emotion preservation and confidence scoring.
    
    **Pipeline**:
    1. Detect source language (if not provided)
    2. Translate with NLLB-200 (beam search)
    3. Score translation confidence (5 factors)
    4. Validate emotion preservation (3 factors)
    5. Retry if quality insufficient (max 2 retries)
    
    **Quality Thresholds**:
    - Translation confidence: 0.75 (default)
    - Emotion preservation: 0.70 (default)
    
    **Performance**:
    - p95 latency: < 1s (short), < 2s (moderate)
    
    **Response Status**:
    - `success`: Translation meets quality thresholds
    - `partial`: Translation exists but below thresholds
    - `failed`: Translation failed or very low quality
    """
    try:
        response = await service.translate(request)
        return response
    except Exception as e:
        logger.exception(f"Translation endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=TranslationHealthResponse)
def get_health(
    service: TranslationService = Depends(get_translation_service)
) -> TranslationHealthResponse:
    """
    Get translation service health status.
    
    Returns:
    - Models loaded status
    - Error rate
    - Retry rate
    - Average confidence
    - Average emotion preservation
    - Uptime
    """
    try:
        return service.get_health()
    except Exception as e:
        logger.exception(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=TranslationMetricsSnapshot)
def get_metrics(
    service: TranslationService = Depends(get_translation_service)
) -> TranslationMetricsSnapshot:
    """
    Get detailed translation metrics.
    
    Returns:
    - Request counts (success/partial/failed)
    - Confidence percentiles (p50, p95)
    - Emotion preservation scores
    - Language distribution
    - Latency percentiles (p50, p95, p99)
    - Retry metrics (rate, reasons)
    - Active alerts
    """
    try:
        return service.get_metrics()
    except Exception as e:
        logger.exception(f"Metrics endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drift-alerts", response_model=List[DriftAlert])
def get_drift_alerts(
    service: TranslationService = Depends(get_translation_service)
) -> List[DriftAlert]:
    """
    Get active drift alerts.
    
    Alert types:
    - `confidence_drift`: Confidence dropped > 15% below baseline
    - `emotion_preservation_drift`: Emotion preservation dropped > 20%
    - `high_retry_rate`: Retry rate > 20%
    - `latency_spike`: Latency > 50% above baseline
    """
    try:
        return service.get_drift_alerts()
    except Exception as e:
        logger.exception(f"Drift alerts endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-status")
def get_model_status(
    service: TranslationService = Depends(get_translation_service)
):
    """
    Get translation model status.
    
    Returns:
    - Model name
    - Device (cuda/cpu)
    - Language detector status
    - Translation engine status
    """
    return {
        "model_name": service.model_name,
        "device": service.device,
        "language_detector_loaded": service.language_detector.fasttext_model is not None,
        "translation_engine_loaded": service.translation_engine.model is not None,
        "uptime_seconds": service.service_start_time,
    }
