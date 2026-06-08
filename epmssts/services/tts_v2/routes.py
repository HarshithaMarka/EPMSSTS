"""
TTS Service API Routes

FastAPI endpoints for TTS service.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import FileResponse

from .tts_service import TTSService
from .schemas import (
    TTSRequest,
    TTSResponse,
    TTSHealthResponse,
    TTSMetricsSnapshot,
)


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v2/tts", tags=["Text-to-Speech"])

# Global service instance (initialized on startup)
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """Dependency to get TTS service"""
    global _tts_service
    if _tts_service is None:
        raise HTTPException(
            status_code=503,
            detail="TTS service not initialized"
        )
    return _tts_service


def initialize_tts_service(
    model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
    device: str = "cuda",
    enable_fp16: bool = True,
    output_dir: str = "./tts_outputs",
):
    """Initialize TTS service (call on app startup)"""
    global _tts_service
    logger.info("Initializing TTS service...")
    _tts_service = TTSService(
        model_name=model_name,
        device=device,
        enable_fp16=enable_fp16,
        output_dir=output_dir,
    )
    logger.info("TTS service initialized")


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(
    request: TTSRequest,
    service: TTSService = Depends(get_tts_service)
) -> TTSResponse:
    """
    Synthesize speech from text with emotion preservation.
    
    **Pipeline**:
    1. Validate input (text, language, translation confidence)
    2. Map emotion to prosody parameters
    3. Synthesize with neural TTS (Coqui XTTS v2)
    4. Validate waveform quality
    5. Fallback chain if validation fails
    6. Save audio file
    
    **Features**:
    - Emotion-aware prosody (happy, sad, angry, excited, etc.)
    - Multilingual support (16 languages)
    - Waveform validation (never returns silent audio)
    - Intelligent fallback (retry, gTTS, pyttsx3)
    - GPU acceleration
    
    **Performance**:
    - p95 latency: < 1.5s (short text)
    - p95 latency: < 3s (moderate text)
    
    **Response Status**:
    - `success`: Synthesis succeeded with primary engine
    - `partial`: Synthesis succeeded but used fallback
    - `failed`: All synthesis attempts failed
    """
    try:
        response = await service.synthesize(request)
        return response
    except Exception as e:
        logger.exception(f"TTS endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{request_id}")
async def get_audio_file(
    request_id: str,
    service: TTSService = Depends(get_tts_service)
):
    """
    Download generated audio file.
    
    Args:
        request_id: Request ID from synthesis response
    
    Returns:
        WAV audio file (16kHz, mono, PCM 16-bit)
    """
    try:
        # Find audio file
        audio_path = service.output_dir / f"tts_{request_id}.wav"
        
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        return FileResponse(
            path=str(audio_path),
            media_type="audio/wav",
            filename=f"tts_{request_id}.wav"
        )
    
    except Exception as e:
        logger.exception(f"Audio file download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=TTSHealthResponse)
def get_health(
    service: TTSService = Depends(get_tts_service)
) -> TTSHealthResponse:
    """
    Get TTS service health status.
    
    Returns:
    - Service status (healthy/unhealthy)
    - Models loaded status
    - GPU availability
    - GPU memory usage
    - Error rate
    - Fallback usage rate
    - Average latency
    - Uptime
    """
    try:
        return service.get_health()
    except Exception as e:
        logger.exception(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=TTSMetricsSnapshot)
def get_metrics(
    service: TTSService = Depends(get_tts_service)
) -> TTSMetricsSnapshot:
    """
    Get detailed TTS metrics.
    
    Returns:
    - Request counts (success/partial/failed)
    - Fallback usage statistics
    - Latency percentiles (p50, p95, p99)
    - Emotion distribution
    - Language distribution
    - Error distribution
    - Audio statistics
    """
    try:
        return service.get_metrics()
    except Exception as e:
        logger.exception(f"Metrics endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info")
def get_model_info(
    service: TTSService = Depends(get_tts_service)
):
    """
    Get TTS model information.
    
    Returns:
    - Model name
    - Device (cuda/cpu)
    - Sample rate
    - Supported languages
    - Supported emotions
    - GPU availability
    - GPU memory usage
    """
    return {
        "model": service.tts_engine.get_model_info(),
        "prosody": service.prosody_mapper.get_prosody_stats(),
        "validation": service.waveform_validator.get_validation_stats(),
        "fallback": service.fallback_handler.get_fallback_stats(),
    }


@router.get("/supported-emotions")
def get_supported_emotions(
    service: TTSService = Depends(get_tts_service)
):
    """
    Get list of supported emotion labels.
    
    Returns list of emotions with prosody descriptions.
    """
    emotions = service.prosody_mapper.get_supported_emotions()
    return {
        "emotions": [
            {
                "label": emotion,
                "description": service.prosody_mapper.get_emotion_description(emotion)
            }
            for emotion in emotions
        ]
    }


@router.get("/supported-languages")
def get_supported_languages(
    service: TTSService = Depends(get_tts_service)
):
    """
    Get list of supported languages.
    
    Returns language codes supported by TTS engine.
    """
    return {
        "languages": list(service.tts_engine.SUPPORTED_LANGUAGES),
        "total": len(service.tts_engine.SUPPORTED_LANGUAGES)
    }
