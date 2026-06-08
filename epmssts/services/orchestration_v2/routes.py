"""API routes for orchestration v2 control plane."""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, status

from epmssts.config import settings
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.stt.audio_handler import compute_audio_metrics, preprocess_audio_bytes
from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.translation.translator import TranslationService
from epmssts.services.tts.synthesizer_edge import EdgeTtsService, TtsSynthesisRequest

from .circuit_breaker import CircuitBreakerManager, CircuitConfig
from .orchestrator_service import OrchestrationService, StageClients
from .schemas import (
    PipelineHealthResponse,
    PipelineMetricsResponse,
    PipelineProcessRequest,
    PipelineProcessResponse,
    PipelineStatusResponse,
    PipelineTraceResponse,
)
from .security import (
    RedisRateLimiter,
    enforce_payload_size,
    enforce_request_id,
    validate_jwt_token,
)
from .state_store import OrchestrationStateStore


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["orchestration-v2"])

_orchestration_service: Optional[OrchestrationService] = None
_rate_limiter: Optional[RedisRateLimiter] = None


async def _ensure_rate_limit(request: Request):
    if not settings.rate_limit_enabled:
        return
    if _rate_limiter is None:
        return
    await _rate_limiter.enforce(request)


def get_orchestration_service() -> OrchestrationService:
    if _orchestration_service is None:
        raise HTTPException(status_code=503, detail="Orchestration service not initialized")
    return _orchestration_service


async def _default_preprocess(audio_bytes: bytes):
    loop = asyncio.get_running_loop()

    def _run_sync():
        waveform, sample_rate = preprocess_audio_bytes(audio_bytes)
        metrics = compute_audio_metrics(waveform, sample_rate)
        return {
            "waveform": waveform,
            "sample_rate": sample_rate,
            "duration_seconds": metrics.get("duration_sec", 0.0),
            "quality_score": 80,
            "energy_band": "normal",
        }

    return await loop.run_in_executor(None, _run_sync)


async def _default_stt(audio_bytes: bytes, stt_service: SpeechToTextService):
    loop = asyncio.get_running_loop()

    def _run_sync():
        waveform, sample_rate = preprocess_audio_bytes(audio_bytes)
        result = stt_service.transcribe(waveform, sample_rate)
        conf = 0.9 if result.text else 0.0
        return {
            "transcript": result.text,
            "confidence": conf,
            "language": result.language,
        }

    return await loop.run_in_executor(None, _run_sync)


async def _default_emotion(audio_bytes: bytes, transcript: str, emotion_service: AudioEmotionService):
    loop = asyncio.get_running_loop()

    def _run_sync():
        waveform, sample_rate = preprocess_audio_bytes(audio_bytes)
        result = emotion_service.predict(waveform, sample_rate)
        return {
            "emotion": result.label,
            "confidence": result.confidence,
        }

    return await loop.run_in_executor(None, _run_sync)


async def _default_translation(
    transcript: str,
    source_language: str,
    target_language: str,
    emotion_confidence: float,
    translation_service: TranslationService,
):
    loop = asyncio.get_running_loop()

    def _run_sync():
        src = source_language if source_language in {"en", "te", "hi"} else "en"
        tgt = target_language if target_language in {"en", "te", "hi"} else "en"
        translated = translation_service.translate(transcript, src, tgt)
        confidence = 0.9 if translated.translated_text else 0.0
        return {
            "translated_text": translated.translated_text,
            "confidence": confidence,
        }

    return await loop.run_in_executor(None, _run_sync)


async def _default_tts(
    translated_text: str,
    target_language: str,
    emotion_label: str,
    emotion_confidence: float,
    translation_confidence: float,
    tts_service: EdgeTtsService,
):
    lang = target_language if target_language in {"en", "te", "hi"} else "en"
    mapped = emotion_label if emotion_label in {"neutral", "happy", "sad", "angry", "fearful"} else "neutral"

    request = TtsSynthesisRequest(
        text=translated_text,
        language=lang,
        emotion=mapped,
        dialect=None,
    )
    audio_bytes = await tts_service.synthesize(request)

    outputs_dir = Path(settings.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir=outputs_dir) as temp:
        temp.write(audio_bytes)
        output_path = Path(temp.name)

    return {
        "audio_output_url": str(output_path),
        "validation_confidence": 1.0 if len(audio_bytes) > 0 else 0.0,
    }


async def initialize_orchestration_service(
    stt_service: Optional[SpeechToTextService] = None,
    emotion_service: Optional[AudioEmotionService] = None,
    translation_service: Optional[TranslationService] = None,
    tts_service: Optional[EdgeTtsService] = None,
):
    global _orchestration_service, _rate_limiter

    state_store = OrchestrationStateStore(settings.redis_url, ttl_seconds=settings.redis_ttl_seconds)
    await state_store.connect()

    limiter = RedisRateLimiter(
        state_store=state_store,
        requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    _rate_limiter = limiter

    if stt_service is None:
        stt_service = SpeechToTextService(model_size="base")
    if emotion_service is None:
        emotion_service = AudioEmotionService()
    if translation_service is None:
        translation_service = TranslationService()
    if tts_service is None:
        tts_service = EdgeTtsService()

    clients = StageClients(
        preprocess=_default_preprocess,
        stt=lambda audio: _default_stt(audio, stt_service),
        emotion=lambda audio, transcript: _default_emotion(audio, transcript, emotion_service),
        translation=lambda transcript, source, target, emo_conf: _default_translation(
            transcript,
            source,
            target,
            emo_conf,
            translation_service,
        ),
        tts=lambda text, language, emotion, e_conf, t_conf: _default_tts(
            text,
            language,
            emotion,
            e_conf,
            t_conf,
            tts_service,
        ),
    )

    circuit_breakers = CircuitBreakerManager(
        state_store=state_store,
        config=CircuitConfig(failure_threshold=5, recovery_timeout_seconds=30, half_open_max_calls=2),
    )

    _orchestration_service = OrchestrationService(
        clients=clients,
        state_store=state_store,
        circuit_breakers=circuit_breakers,
        max_concurrency=32,
    )

    logger.info("Orchestration v2 service initialized")


@router.post(
    "/process",
    response_model=PipelineProcessResponse,
    dependencies=[Depends(validate_jwt_token), Depends(_ensure_rate_limit)],
)
async def process_pipeline(
    payload: PipelineProcessRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
):
    enforce_request_id(payload.request_id)
    enforce_payload_size(payload.audio_file)

    try:
        return await asyncio.wait_for(
            service.process(payload),
            timeout=settings.timeout_pipeline,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Pipeline request timed out",
        )


@router.get(
    "/trace/{request_id}",
    response_model=PipelineTraceResponse,
    dependencies=[Depends(validate_jwt_token)],
)
async def get_trace(
    request_id: str,
    service: OrchestrationService = Depends(get_orchestration_service),
):
    trace = await service.get_trace(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(service: OrchestrationService = Depends(get_orchestration_service)):
    return await service.get_status()


@router.get("/health", response_model=PipelineHealthResponse)
async def get_pipeline_health(service: OrchestrationService = Depends(get_orchestration_service)):
    return await service.get_health()


@router.get("/metrics", response_model=PipelineMetricsResponse)
async def get_pipeline_metrics(service: OrchestrationService = Depends(get_orchestration_service)):
    return service.get_metrics()


@router.get("/failure-modes")
async def get_failure_modes(service: OrchestrationService = Depends(get_orchestration_service)):
    return {"rows": [row.model_dump(mode="json") for row in service.get_failure_mode_table()]}
