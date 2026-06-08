"""
Emotion Intelligence Service API Routes

FastAPI routes for emotion analysis endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict

from .emotion_service import EmotionIntelligenceService
from .schemas import (
    EmotionAnalysisRequest,
    EmotionAnalysisResponse,
    HealthCheckResponse,
    MetricsSnapshot,
    DriftAlert,
)


logger = logging.getLogger(__name__)

# Router for emotion endpoints
router = APIRouter(prefix="/emotion/v2", tags=["emotion-v2"])

# Global service instance (singleton)
_service_instance: EmotionIntelligenceService = None


async def get_service() -> EmotionIntelligenceService:
    """Get or create service instance"""
    global _service_instance
    
    if _service_instance is None:
        _service_instance = EmotionIntelligenceService(device="cpu")
        await _service_instance.initialize()
    
    return _service_instance


@router.post("/analyze", response_model=EmotionAnalysisResponse)
async def analyze_emotion(request: EmotionAnalysisRequest) -> EmotionAnalysisResponse:
    """
    Analyze emotion from audio and text features.
    
    Pipeline:
    - Audio ensemble inference (Wav2Vec2 + HuBERT)
    - Text model inference (DistilRoBERTa)
    - Temperature scaling calibration
    - Adaptive Bayesian fusion (NO fixed weights)
    - Uncertainty quantification
    - Drift monitoring
    
    Returns comprehensive response with:
    - Final emotion label and confidence
    - Full probability distribution
    - Uncertainty metrics (entropy, margin, disagreement)
    - Model predictions (individual model outputs)
    - Calibration info (temperature, adjustments)
    - Fusion weights (adaptive α, β)
    """
    try:
        service = await get_service()
        response = await service.analyze_emotion(request)
        return response
    
    except Exception as e:
        logger.error(f"Emotion analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emotion analysis failed: {str(e)}",
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Get service health status.
    
    Returns:
    - Service status (healthy/initializing/error)
    - Models loaded status
    - Error rate
    - Neutral rate (neutral collapse detection)
    - Uncertainty rate
    - Active drift alerts count
    """
    try:
        service = await get_service()
        health = await service.health_check()
        return health
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/metrics", response_model=MetricsSnapshot)
async def get_metrics() -> MetricsSnapshot:
    """
    Get comprehensive metrics snapshot.
    
    Returns:
    - Total requests
    - Emotion label distribution
    - Average entropy and confidence
    - Uncertainty rate
    - Neutral rate
    - Latency percentiles (p50, p95, p99)
    - Active alerts count
    """
    try:
        service = await get_service()
        metrics = service.get_metrics_snapshot()
        return metrics
    
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Metrics retrieval failed: {str(e)}",
        )


@router.get("/drift-alerts", response_model=Dict)
async def get_drift_alerts():
    """
    Get active drift alerts.
    
    Returns list of active alerts for:
    - Neutral collapse (neutral > 70%)
    - Class imbalance (single class > 80%)
    - Entropy spike (>50% above baseline)
    - Confidence degradation (<30% average)
    - High uncertainty rate (>50% flagged)
    """
    try:
        service = await get_service()
        alerts = service.get_drift_alerts()
        
        return {
            "active_alerts": [alert.dict() for alert in alerts],
            "alert_count": len(alerts),
        }
    
    except Exception as e:
        logger.error(f"Drift alerts retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Drift alerts retrieval failed: {str(e)}",
        )


@router.get("/model-info", response_model=Dict)
async def get_model_info():
    """
    Get information about loaded models.
    
    Returns:
    - Model names and versions
    - Device (CPU/GPU)
    - Inference counts
    - Average inference times
    """
    try:
        service = await get_service()
        
        return {
            "device": service.device,
            "models": {
                "audio_primary": "wav2vec2-lg-xlsr-en-speech-emotion-recognition",
                "audio_secondary": "hubert-base-superb-er",
                "text": "emotion-english-distilroberta-base",
            },
            "inference_count": service.inference_count,
            "error_count": service.error_count,
            "calibration": {
                "method": "temperature_scaling",
                "neutral_penalty": True,
                "volume_bias_correction": True,
            },
            "fusion": {
                "method": "bayesian",
                "adaptive_weights": True,
                "fixed_weights": False,
            },
        }
    
    except Exception as e:
        logger.error(f"Model info retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model info retrieval failed: {str(e)}",
        )
