from contextlib import asynccontextmanager
import logging
import os
from typing import Optional
from uuid import uuid4
import asyncio
from pathlib import Path
from time import perf_counter
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, status, Form, Request, Body
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    _PROM_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    CONTENT_TYPE_LATEST = "text/plain"
    generate_latest = None
    _PROM_AVAILABLE = False

from epmssts.services.stt.transcriber import SpeechToTextService, TranscriptionResult
from epmssts.services.stt.audio_handler import compute_audio_metrics, preprocess_audio_bytes
from epmssts.services.emotion.audio_emotion import AudioEmotionService, EmotionPrediction
from epmssts.services.emotion.text_emotion import TextEmotionService
from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor
from epmssts.services.emotion.debug import EmotionDebugger
from epmssts.services.dialect.classifier import DialectClassifier, DialectPrediction

# Import new production-grade STT module (Module 2)
from epmssts.services.stt import SpeechToTextService as SttServiceV2
from epmssts.api.routes.stt_routes import router as stt_v2_router, set_stt_service
from epmssts.services.translation.translator import (
    TranslationService,
    TranslationResult,
)
from epmssts.services.tts.synthesizer_edge import EdgeTtsService as TtsService, TtsSynthesisRequest
from epmssts.services.audio.preprocessing_service import AudioPreprocessingService
from epmssts.api.pipeline import run_speech_to_speech, SpeechToSpeechResult
from epmssts.services.orchestration_v2.routes import (
    router as orchestration_v2_router,
    initialize_orchestration_service,
)
from epmssts.api.routes.streaming_routes import (
    router as streaming_router,
    set_streaming_runtime,
)
from epmssts.api.observability import (
    API_SCHEMA_VERSION,
    build_meta,
    get_max_concurrency,
    log_event,
    record_request,
    record_silence_reject,
    record_stage_error,
    record_stage_fallback,
    record_stage_latency,
    record_throttle,
)
from epmssts.services.production.runtime import (
    ProductionRuntime,
    build_production_runtime,
)
from epmssts.services.production.security import SecurityError


logger = logging.getLogger("epmssts.api")

stt_service: Optional[SpeechToTextService] = None
emotion_service: Optional[AudioEmotionService] = None
text_emotion_service: Optional[TextEmotionService] = None
dialect_classifier: Optional[DialectClassifier] = None
translation_service: Optional[TranslationService] = None
tts_service: Optional[TtsService] = None
stt_service_v2: Optional[SttServiceV2] = None  # Production STT Module 2
production_runtime: Optional[ProductionRuntime] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Ensures the Whisper model is loaded once at startup
    and released cleanly on shutdown.
    """
    global stt_service, emotion_service, text_emotion_service, dialect_classifier, translation_service, tts_service, stt_service_v2, production_runtime
    app.state.shutting_down = False
    try:
        stt_service = SpeechToTextService()
        emotion_service = AudioEmotionService()
        try:
            text_emotion_service = TextEmotionService()
        except Exception as exc:
            logger.warning("Text emotion service unavailable: %s", exc)
            text_emotion_service = None
        dialect_classifier = DialectClassifier()
        translation_service = TranslationService()
        try:
            tts_service = TtsService()
        except RuntimeError as e:
            logger.warning("TTS service not available: %s", e)
            tts_service = None

        # Initialize production orchestration control plane (Module 6)
        try:
            logger.info("Initializing production orchestration service (Module 6)...")
            await initialize_orchestration_service(
                stt_service=stt_service,
                emotion_service=emotion_service,
                translation_service=translation_service,
                tts_service=tts_service,
            )
            logger.info("Production orchestration service initialized successfully")
        except Exception as exc:
            logger.warning("Production orchestration service initialization failed: %s", exc)
        
        # Initialize production STT service (Module 2)
        try:
            logger.info("Initializing production STT service (Module 2)...")
            stt_service_v2 = SttServiceV2(
                model_size="medium",  # Can be configured via env
                device_prefer_gpu=True,
                max_concurrent_inferences=4,
            )
            await stt_service_v2.initialize()
            set_stt_service(stt_service_v2)
            logger.info("Production STT service initialized successfully")
        except Exception as exc:
            logger.warning("Production STT service initialization failed: %s", exc)
            stt_service_v2 = None

        # Initialize production runtime layers (streaming, security, drift, calibration)
        try:
            logger.info("Initializing production runtime layers...")
            production_runtime = build_production_runtime(
                stt_service=stt_service,
                emotion_service=emotion_service,
                dialect_classifier=dialect_classifier,
            )
            set_streaming_runtime(production_runtime)
            logger.info("Production runtime initialized successfully")
        except SystemExit as exc:
            raise SystemExit(str(exc))
        except Exception as exc:
            logger.warning("Production runtime initialization failed: %s", exc)
            production_runtime = None
            
    except Exception as exc:  # pragma: no cover - startup failure path
        # Fail fast if the model cannot be loaded
        raise RuntimeError(f"Failed to initialize core services: {exc}") from exc

    yield

    # Teardown hook if we ever need explicit cleanup
    app.state.shutting_down = True
    stt_service = None
    emotion_service = None
    text_emotion_service = None
    dialect_classifier = None
    translation_service = None
    tts_service = None
    stt_service_v2 = None
    production_runtime = None


app = FastAPI(title="EPMSSTS API", version="0.1.0", lifespan=lifespan)

pipeline_semaphore = asyncio.Semaphore(get_max_concurrency())

# Include routers
app.include_router(stt_v2_router)
app.include_router(orchestration_v2_router)
app.include_router(streaming_router)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    if getattr(request.app.state, "shutting_down", False):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "draining", "detail": "Service is shutting down"},
        )

    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    start = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        latency_ms = int((perf_counter() - start) * 1000)
        status_code = response.status_code if response is not None else 500
        record_request(request.url.path, request.method, status_code, latency_ms)
        if response is not None:
            response.headers["x-request-id"] = request_id


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    runtime = production_runtime
    if runtime is not None:
        try:
            await runtime.security.validate_http(request)
        except SecurityError as exc:
            record_throttle(request.url.path)
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "status": "error",
                    "error": exc.code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                },
            )
    return await call_next(request)


@app.get("/health")
async def health_check():
    """
    Basic health check endpoint for readiness probes.
    """
    # Only STT is critical; other services can fail gracefully
    if stt_service is None or emotion_service is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "detail": "Critical services not initialized (STT or Emotion)",
            },
        )
    return {
        "schema_version": API_SCHEMA_VERSION,
        "status": "ok",
        "stt_available": stt_service is not None,
        "emotion_available": emotion_service is not None,
        "text_emotion_available": text_emotion_service is not None,
        "dialect_available": dialect_classifier is not None,
        "translation_available": translation_service is not None and translation_service._model is not None,
        "tts_available": tts_service is not None,
        "production_runtime": production_runtime is not None,
    }


@app.get("/health/ready")
async def readiness_check():
    runtime = production_runtime
    config_valid = runtime is not None
    if not config_valid:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "detail": "Production runtime unavailable"},
        )
    return {"status": "ready", "config_valid": True}


@app.get("/metrics")
async def metrics_endpoint():
    if not _PROM_AVAILABLE or generate_latest is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prometheus client not installed",
        )
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


# ============================================================================
# AUDIO PREPROCESSING SERVICE - Module 1 (Production-grade Ingestion & Preprocessing)
# ============================================================================

audio_preprocessing_service = AudioPreprocessingService()


@app.post(
    "/audio/preprocess",
    summary="Preprocess Audio File",
    description="Validate, clean, and extract features from audio file. Entry point for all downstream modules.",
    tags=["Audio Processing"],
)
async def preprocess_audio(file: UploadFile = File(..., description="Audio file (WAV, MP3, FLAC, M4A), max 10MB")):
    """
    Preprocess audio file end-to-end.
    
    **Input Contract**:
    - Formats: WAV, MP3, FLAC, M4A
    - Max size: 10MB
    - Max duration: 60 seconds
    - Min duration: 1.5 seconds
    
    **Processing Pipeline**:
    1. Validate input
    2. Decode to 16kHz mono
    3. Remove DC offset + highpass filter
    4. Trim silence via VAD
    5. Extract signal metrics
    6. Adaptive RMS normalization
    7. Apply soft limiter
    8. Compute mel-spectrogram
    9. Feature standardization
    
    **Output**: Structured JSON with metrics, quality score, preprocessing latency
    
    **Quality Score Factors**:
    - SNR (40%): Higher SNR = Better quality
    - Clipping (20%): Hard penalty if peaks clip
    - Silence ratio (20%): Penalize excessive silence
    - Dynamic range (10%): Minimum 10dB needed
    - Duration (10%): Optimal 3-10 seconds
    """
    try:
        # Check file size
        contents = await file.read()
        if len(contents) > 10_000_000:
            return JSONResponse(
                status_code=413,
                content={
                    "status": "error",
                    "reason_code": "ERR_006_FILE_TOO_LARGE",
                    "message": f"File size {len(contents) / 1e6:.1f}MB exceeds 10MB limit",
                    "details": {"size_bytes": len(contents), "max_size_bytes": 10_000_000},
                    "request_id": str(uuid4()),
                    "timestamp": Path(__file__).stem,  # Will be replaced by proper timestamp in production
                }
            )
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            # Process
            response, internal_data = audio_preprocessing_service.preprocess(tmp_path)
            
            # Check if error response
            if response.status == "error":
                return JSONResponse(
                    status_code=400,
                    content=response.dict(by_alias=True)
                )
            
            return response.dict(by_alias=True)
        
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preprocessing failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "reason_code": "ERR_999_INTERNAL_ERROR",
                "message": str(e),
                "details": {},
                "request_id": str(uuid4()),
                "timestamp": Path(__file__).stem,
            }
        )


@app.get(
    "/audio/health",
    summary="Audio Service Health",
    description="Check audio preprocessing service health",
    tags=["Audio Processing"],
)
async def audio_health_check():
    """Health check for audio preprocessing service."""
    return {
        "status": "healthy",
        "service": "audio-preprocessing",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get(
    "/audio/metrics",
    summary="Audio Service Metrics",
    description="Get service metrics and statistics",
    tags=["Audio Processing"],
)
async def audio_metrics():
    """Get audio preprocessing service metrics."""
    metrics = audio_preprocessing_service.get_metrics_summary()
    return metrics


@app.post("/stt/transcribe")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(..., description="Audio file to transcribe"),
):
    """
    Transcribe an uploaded audio file using faster-whisper.

    - Ensures audio is converted to 16kHz mono.
    - Uses language auto-detection.
    - Times out and aborts after 10 seconds.
    """
    if stt_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT service is not available",
        )

    # Basic content-type validation; we keep this permissive and rely on
    # decoding errors for final validation.
    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Expected audio/*.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        audio_16k, sample_rate = preprocess_audio_bytes(file_bytes)
    except ValueError as exc:
        # Explicit invalid audio errors (e.g. cannot decode)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Unexpected preprocessing errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to decode or preprocess audio: {exc}",
        ) from exc

    # Silence / near-silence check
    audio_metrics = compute_audio_metrics(audio_16k, sample_rate)
    if stt_service.is_silent(audio_16k):
        record_silence_reject("stt")
        # In Phase 1 we only handle STT. Silence-specific emotion handling
        # is deferred to the emotion module.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio appears to be silent or too quiet for transcription.",
        )

    async def _run_transcription() -> TranscriptionResult:
        return await asyncio.get_event_loop().run_in_executor(
            None, stt_service.transcribe, audio_16k, sample_rate
        )

    stage_start = perf_counter()
    try:
        result = await asyncio.wait_for(_run_transcription(), timeout=60.0)
    except asyncio.TimeoutError:
        record_stage_error("stt", "timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Transcription exceeded 60s timeout limit.",
        )
    except Exception as exc:
        record_stage_error("stt", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {exc}",
        ) from exc

    stage_latency = int((perf_counter() - stage_start) * 1000)
    record_stage_latency("stt", stage_latency)

    fallback_used = bool(getattr(stt_service, "_model_available", True) is False)
    if fallback_used:
        record_stage_fallback("stt")

    meta = build_meta(
        request_id=request.state.request_id,
        stage="stt",
        latency_ms=stage_latency,
        confidence=None,
        fallback_used=fallback_used,
        audio_metrics=audio_metrics,
    )

    log_event(
        "stage_completed",
        request_id=request.state.request_id,
        stage="stt",
        latency_ms=stage_latency,
        confidence=None,
        fallback_used=fallback_used,
    )

    return {
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            }
            for seg in result.segments
        ],
        "meta": meta,
    }


@app.post("/emotion/detect")
async def detect_emotion(
    request: Request,
    file: UploadFile = File(..., description="Audio file to analyze for emotion"),
    include_debug: bool = False,
):
    """
    Detect emotion from an uploaded audio file with comprehensive calibration.

    Features:
    - RMS-normalized preprocessing (target -20 dBFS)
    - Energy-based calibration to prevent "sad" bias
    - Pre/post processing audio metrics
    - Optional debug information for diagnostics

    Query Parameters:
    - include_debug: If true, returns detailed debug information
    """
    if emotion_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Emotion service is not available",
        )

    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Expected audio/*.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Create debug logger
    request_id = str(request.state.request_id)
    debugger = EmotionDebugger(request_id, enable_verbose=include_debug)

    try:
        audio_16k, sample_rate = preprocess_audio_bytes(file_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to decode or preprocess audio: {exc}",
        ) from exc

    # Silence handling: return neutral directly (Phase 2 requirement).
    audio_metrics = compute_audio_metrics(audio_16k, sample_rate)
    if emotion_service.is_silent(audio_16k):
        record_silence_reject("emotion")
        neutral_scores = {
            "neutral": 1.0,
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "fearful": 0.0,
        }
        meta = build_meta(
            request_id=request.state.request_id,
            stage="emotion",
            latency_ms=0,
            confidence=1.0,
            fallback_used=True,
            audio_metrics=audio_metrics,
        )
        record_stage_fallback("emotion")
        
        response = {
            "emotion": "neutral",
            "confidence": 1.0,
            "scores": neutral_scores,
            "meta": meta,
        }
        
        if include_debug:
            response["debug"] = debugger.get_summary()
        
        return response

    async def _run_emotion() -> EmotionPrediction:
        return await asyncio.get_event_loop().run_in_executor(
            None, emotion_service.predict, audio_16k, sample_rate
        )

    stage_start = perf_counter()
    try:
        result = await asyncio.wait_for(_run_emotion(), timeout=60.0)
    except asyncio.TimeoutError:
        record_stage_error("emotion", "timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Emotion detection exceeded 60s timeout limit.",
        )
    except Exception as exc:
        record_stage_error("emotion", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emotion detection failed: {exc}",
        ) from exc

    stage_latency = int((perf_counter() - stage_start) * 1000)
    record_stage_latency("emotion", stage_latency)

    fallback_used = bool(getattr(emotion_service, "_model_available", True) is False)
    if fallback_used:
        record_stage_fallback("emotion")

    meta = build_meta(
        request_id=request.state.request_id,
        stage="emotion",
        latency_ms=stage_latency,
        confidence=float(result.confidence),
        fallback_used=fallback_used,
        audio_metrics=audio_metrics,
    )

    log_event(
        "stage_completed",
        request_id=request.state.request_id,
        stage="emotion",
        latency_ms=stage_latency,
        confidence=float(result.confidence),
        fallback_used=fallback_used,
    )

    response = {
        "emotion": result.label,
        "confidence": result.confidence,
        "scores": result.scores,
        "meta": meta,
    }
    
    if include_debug:
        response["debug"] = debugger.get_summary()

    return response


@app.post("/dialect/detect")
async def detect_dialect(
    request: Request,
    transcript: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None, description="Optional audio file for dialect detection"),
):
    """
    Detect Telugu dialect from a transcript string.

    - Rule-based, text-only heuristics.
    - Dialects: telangana, andhra, standard_telugu.
    - This is METADATA ONLY and must not affect translation.
    """
    if dialect_classifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dialect classifier is not available",
        )

    if transcript is None:
        transcript = request.query_params.get("transcript")

    if transcript is None and file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'transcript' or an audio 'file'.",
        )

    resolved_transcript = transcript or ""

    audio_metrics = None
    stage_start = perf_counter()
    if file is not None:
        if stt_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="STT service is required for audio-based dialect detection",
            )

        if not file.content_type.startswith("audio/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type '{file.content_type}'. Expected audio/*.",
            )

        try:
            file_bytes = await file.read()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read uploaded file: {exc}",
            ) from exc

        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        try:
            audio_16k, sample_rate = preprocess_audio_bytes(file_bytes)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to decode or preprocess audio: {exc}",
            ) from exc

        audio_metrics = compute_audio_metrics(audio_16k, sample_rate)

        if stt_service.is_silent(audio_16k):
            record_silence_reject("dialect")
            return {
                "dialect": "standard_telugu",
                "confidence": 0.5,
                "meta": build_meta(
                    request_id=request.state.request_id,
                    stage="dialect",
                    latency_ms=int((perf_counter() - stage_start) * 1000),
                    confidence=0.5,
                    fallback_used=True,
                    audio_metrics=audio_metrics,
                ),
            }

        async def _run_transcription() -> TranscriptionResult:
            return await asyncio.get_event_loop().run_in_executor(
                None, stt_service.transcribe, audio_16k, sample_rate
            )

        try:
            stt_result = await asyncio.wait_for(_run_transcription(), timeout=60.0)
            resolved_transcript = stt_result.text
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Transcription exceeded 10s timeout limit.",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transcription failed: {exc}",
            ) from exc

    # The endpoint assumes the transcript is Telugu; callers should only use
    # this for Telugu text. For non-Telugu text, the classifier will typically
    # fall back to `standard_telugu` with modest confidence.
    prediction: DialectPrediction = dialect_classifier.detect(resolved_transcript)
    stage_latency = int((perf_counter() - stage_start) * 1000)
    record_stage_latency("dialect", stage_latency)
    fallback_used = prediction.confidence < 0.55
    if fallback_used:
        record_stage_fallback("dialect")

    meta = build_meta(
        request_id=request.state.request_id,
        stage="dialect",
        latency_ms=stage_latency,
        confidence=float(prediction.confidence),
        fallback_used=fallback_used,
        audio_metrics=audio_metrics,
    )

    return {
        "dialect": prediction.dialect,
        "confidence": prediction.confidence,
        "meta": meta,
    }


@app.post("/translate")
async def translate(
    request: Request,
    payload: dict = Body(...),
):
    """
    Pure text translation endpoint using NLLB-200.

    Input JSON:
    {
      "text": str,
      "source_lang": "te|hi|en",
      "target_lang": "te|hi|en"
    }

    Output JSON:
    {
      "translated_text": str,
      "model": "nllb-200-distilled-600M"
    }
    """
    if translation_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation service is not available",
        )

    text = payload.get("text")
    source_lang = payload.get("source_lang")
    target_lang = payload.get("target_lang")

    if text is None or not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'text' must be a non-empty string.",
        )

    if source_lang not in {"te", "hi", "en"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'source_lang' must be one of: 'te', 'hi', 'en'.",
        )

    if target_lang not in {"te", "hi", "en"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'target_lang' must be one of: 'te', 'hi', 'en'.",
        )

    stage_start = perf_counter()
    try:
        result: TranslationResult = translation_service.translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except ValueError as exc:
        record_stage_error("translation", "validation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        record_stage_error("translation", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {exc}",
        ) from exc

    stage_latency = int((perf_counter() - stage_start) * 1000)
    record_stage_latency("translation", stage_latency)

    meta = build_meta(
        request_id=request.state.request_id,
        stage="translation",
        latency_ms=stage_latency,
        confidence=None,
        fallback_used=False,
    )

    log_event(
        "stage_completed",
        request_id=request.state.request_id,
        stage="translation",
        latency_ms=stage_latency,
        confidence=None,
        fallback_used=False,
    )

    return {
        "translated_text": result.translated_text,
        "model": result.model,
        "meta": meta,
    }


@app.post("/tts/synthesize")
async def synthesize_tts(
    request: Request,
    payload: dict = Body(...),
):
    """
    Emotion-conditioned TTS endpoint.

    Input JSON:
    {
      "text": str,
      "language": "en|te|hi",
      "emotion": "neutral|happy|sad|angry|fearful"
    }

    Output:
      Audio bytes (MP3 or WAV) with appropriate content-type.
      Edge TTS returns MP3 with emotion-conditioned prosody.
    """
    # Log immediately when request arrives
    logger.info(f"[TTS ENDPOINT] ===== TTS REQUEST RECEIVED ===== from {request.client.host}")
    logger.info(f"[TTS ENDPOINT] Payload: text_len={len(payload.get('text', ''))} lang={payload.get('language')} emotion={payload.get('emotion')}")
    
    service = tts_service
    if service is None:
        # Lazy fallback init to keep endpoint working even if startup failed.
        try:
            service = TtsService()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"TTS service is not available: {exc}",
            ) from exc

    text = payload.get("text")
    language = payload.get("language")
    emotion = payload.get("emotion")

    # ===== STEP 1: Validate inputs with detailed logging =====
    logger.info(f"[TTS] Input validation: text_len={len(text) if text else 0}, lang={language}, emotion={emotion}")
    logger.debug(f"[TTS] Text content: {repr(text[:100] if text else None)}")

    if text is None or not isinstance(text, str) or not text.strip():
        logger.error(f"[TTS] INVALID INPUT: text is empty or None")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'text' must be a non-empty string.",
        )

    if language not in {"en", "te", "hi"}:
        logger.error(f"[TTS] INVALID LANGUAGE: {language}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'language' must be one of: 'en', 'te', 'hi'.",
        )

    if emotion not in {"neutral", "happy", "sad", "angry", "fearful"}:
        logger.error(f"[TTS] INVALID EMOTION: {emotion}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Field 'emotion' must be one of: "
                "'neutral', 'happy', 'sad', 'angry', 'fearful'."
            ),
        )

    tts_request = TtsSynthesisRequest(
        text=text,
        language=language,
        emotion=emotion,
    )

    # ===== STEP 2: Synthesize and validate output =====
    stage_start = perf_counter()
    try:
        logger.info(f"[TTS] Starting Edge TTS synthesis: text_len={len(text)}")
        
        # Edge TTS is async by design - no thread pool needed
        # Add timeout to prevent hanging indefinitely (30 seconds for synthesis)
        try:
            wav_bytes = await asyncio.wait_for(
                service.synthesize(tts_request),
                timeout=30.0
            )
            synthesis_time = perf_counter() - stage_start
            logger.info(
                f"[TTS] Synthesis complete: {len(wav_bytes)} bytes in {synthesis_time:.2f}s "
                f"({len(wav_bytes)/1024:.1f}KB)"
            )
        except asyncio.TimeoutError:
            logger.error(f"[TTS] Synthesis TIMEOUT after 30 seconds")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="TTS synthesis timed out after 30 seconds"
            )
        
        logger.debug(f"[TTS] WAV header: {wav_bytes[:12].hex() if wav_bytes else 'empty'}")
        
        # Validate output size (Edge TTS should produce substantial audio)
        if len(wav_bytes) < 5000:
            logger.error(
                f"[TTS] CRITICAL: Generated audio is too small "
                f"({len(wav_bytes)} bytes, expected >5KB)"
            )
            raise RuntimeError(f"TTS generated insufficient audio: {len(wav_bytes)} bytes")
            
    except ValueError as exc:
        logger.error(f"[TTS] Validation error: {exc}")
        record_stage_error("tts", "validation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"[TTS] Synthesis failed: {exc}", exc_info=True)
        record_stage_error("tts", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {exc}",
        ) from exc

    stage_latency = int((perf_counter() - stage_start) * 1000)
    record_stage_latency("tts", stage_latency)
    fallback_used = bool(getattr(service, "_engine_kind", "coqui") != "coqui")
    if fallback_used:
        logger.warning(f"[TTS] Using fallback engine: {getattr(service, '_engine_kind', 'unknown')}")
        record_stage_fallback("tts")

    logger.info(f"[TTS] Success: {len(wav_bytes)} bytes in {stage_latency}ms, fallback={fallback_used}")
    
    # Detect audio format (MP3 or WAV) and set appropriate media type
    media_type = "audio/wav"
    if len(wav_bytes) >= 4:
        # MP3 detection: ID3 tag or MPEG frame sync (0xFF 0xFB or 0xFF 0xF3)
        if wav_bytes.startswith(b'ID3') or (wav_bytes[0] == 0xFF and (wav_bytes[1] & 0xE0) == 0xE0):
            media_type = "audio/mpeg"
            logger.debug("[TTS] Detected MP3 format")
        elif wav_bytes.startswith(b'RIFF'):
            media_type = "audio/wav"
            logger.debug("[TTS] Detected WAV format")
    
    response = Response(content=wav_bytes, media_type=media_type)
    response.headers["x-schema-version"] = API_SCHEMA_VERSION
    response.headers["x-request-id"] = request.state.request_id
    response.headers["x-stage-latency-ms"] = str(stage_latency)
    response.headers["x-fallback-used"] = str(fallback_used).lower()
    return response


@app.post("/translate/speech")
async def translate_speech(
    request: Request,
    file: UploadFile = File(..., description="Input audio file for speech-to-speech translation"),
    target_lang: str = Form(..., description="Target language code: en|te|hi"),
):
    """
    End-to-end speech-to-speech translation.

    Chains:
    - STT
    - Audio-based emotion detection
    - Telugu dialect detection (metadata only)
    - Pure text translation
    - Emotion-conditioned TTS
    """
    if (
        stt_service is None
        or emotion_service is None
        or dialect_classifier is None
        or translation_service is None
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core services are not available",
        )

    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Expected audio/*.",
        )

    if target_lang not in {"en", "te", "hi"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'target_lang' must be one of: 'en', 'te', 'hi'.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    outputs_dir = Path(__file__).resolve().parents[2] / "outputs"

    async def _run_pipeline() -> SpeechToSpeechResult:
        return await run_speech_to_speech(
            file_bytes=file_bytes,
            target_lang=target_lang,  # type: ignore[arg-type]
            stt_service=stt_service,  # type: ignore[arg-type]
            emotion_service=emotion_service,  # type: ignore[arg-type]
            dialect_classifier=dialect_classifier,  # type: ignore[arg-type]
            translation_service=translation_service,  # type: ignore[arg-type]
            tts_service=tts_service,
            text_emotion_service=text_emotion_service,
            outputs_dir=outputs_dir,
        )

    queue_timeout = float(os.getenv("EPMSSTS_PIPELINE_QUEUE_TIMEOUT", "2.5"))
    acquired = False
    try:
        await asyncio.wait_for(pipeline_semaphore.acquire(), timeout=queue_timeout)
        acquired = True
    except asyncio.TimeoutError:
        record_throttle("/translate/speech")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Pipeline is busy. Please retry shortly.",
        )

    try:
        result = await asyncio.wait_for(_run_pipeline(), timeout=120.0)
    except asyncio.TimeoutError:
        print("[WARN] /translate/speech request timed out after 120s.")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="End-to-end translation exceeded 120s timeout limit.",
        )
    except ValueError as exc:
        print(f"[ERROR] /translate/speech invalid request: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        print(f"[ERROR] /translate/speech failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during speech-to-speech translation.",
        ) from exc
    finally:
        if acquired:
            pipeline_semaphore.release()

    audio_url = f"/output/{result.session_id}.wav"

    meta = build_meta(
        request_id=request.state.request_id,
        stage="pipeline",
        latency_ms=result.latency_ms,
        confidence=result.pipeline_confidence,
        fallback_used=any(result.fallback_flags.values()),
        audio_metrics=result.audio_metrics,
        stage_latencies=result.stage_latencies_ms,
        stage_confidences=result.stage_confidences,
        fallback_flags=result.fallback_flags,
        pipeline_confidence=result.pipeline_confidence,
    )

    log_event(
        "pipeline_completed",
        request_id=request.state.request_id,
        stage="pipeline",
        latency_ms=result.latency_ms,
        confidence=result.pipeline_confidence,
        fallback_used=any(result.fallback_flags.values()),
    )

    return {
        "session_id": result.session_id,
        "transcript": result.transcript,
        "detected_language": result.detected_language,
        "detected_emotion": result.detected_emotion,
        "emotion_confidence": result.emotion_confidence,
        "detected_dialect": result.detected_dialect,
        "dialect_confidence": result.dialect_confidence,
        "translated_text": result.translated_text,
        "audio_url": audio_url,
        "latency_ms": result.latency_ms,
        "meta": meta,
    }


@app.get("/output/{session_id}.wav")
async def get_output_audio(session_id: str):
    """
    Serve synthesized audio files by session ID.
    """
    outputs_dir = Path(__file__).resolve().parents[2] / "outputs"
    audio_path = outputs_dir / f"{session_id}.wav"

    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found.",
        )

    return FileResponse(path=audio_path, media_type="audio/wav")


# Additional convenience endpoints to match frontend expectations
@app.post("/emotion/analyze")
async def analyze_emotion(
    request: Request,
    file: UploadFile = File(..., description="Audio file to analyze for emotion"),
):
    """
    Alias for /emotion/detect endpoint for frontend compatibility.
    """
    return await detect_emotion(request, file)


@app.post("/process/speech-to-speech")
async def process_speech_to_speech(
    request: Request,
    file: UploadFile = File(..., description="Input audio file for speech-to-speech translation"),
    target_lang: str = Form(..., description="Target language code (en, te, hi)"),
    target_emotion: str = Form("neutral", description="Ignored; emotion is derived from input audio"),
):
    """
    Complete end-to-end speech-to-speech translation pipeline.
    
    This endpoint:
    1. Transcribes the audio
    2. Detects emotion and dialect
    3. Translates to target language
    4. Synthesizes speech with target emotion
    
    Returns both translated text and audio output.
    """
    if (
        stt_service is None
        or emotion_service is None
        or dialect_classifier is None
        or translation_service is None
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required services not initialized",
        )

    if target_lang not in {"en", "te", "hi"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'target_lang' must be one of: 'en', 'te', 'hi'.",
        )

    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Expected audio/*.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    outputs_dir = Path(__file__).resolve().parents[2] / "outputs"

    async def _run_pipeline() -> SpeechToSpeechResult:
        return await run_speech_to_speech(
            file_bytes=file_bytes,
            target_lang=target_lang,  # type: ignore[arg-type]
            stt_service=stt_service,  # type: ignore[arg-type]
            emotion_service=emotion_service,  # type: ignore[arg-type]
            dialect_classifier=dialect_classifier,  # type: ignore[arg-type]
            translation_service=translation_service,  # type: ignore[arg-type]
            tts_service=tts_service,
            text_emotion_service=text_emotion_service,
            outputs_dir=outputs_dir,
        )

    queue_timeout = float(os.getenv("EPMSSTS_PIPELINE_QUEUE_TIMEOUT", "2.5"))
    acquired = False
    try:
        await asyncio.wait_for(pipeline_semaphore.acquire(), timeout=queue_timeout)
        acquired = True
    except asyncio.TimeoutError:
        record_throttle("/process/speech-to-speech")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Pipeline is busy. Please retry shortly.",
        )

    try:
        result = await asyncio.wait_for(_run_pipeline(), timeout=120.0)
    except ValueError as exc:
        # Silence detection or invalid audio preprocessing error
        if "silent" in str(exc).lower() or "quiet" in str(exc).lower():
            record_silence_reject("pipeline")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="End-to-end translation exceeded 120s timeout limit.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {exc}",
        ) from exc
    finally:
        if acquired:
            pipeline_semaphore.release()

    output_audio_url = f"/output/{result.session_id}.wav"

    meta = build_meta(
        request_id=request.state.request_id,
        stage="pipeline",
        latency_ms=result.latency_ms,
        confidence=result.pipeline_confidence,
        fallback_used=any(result.fallback_flags.values()),
        audio_metrics=result.audio_metrics,
        stage_latencies=result.stage_latencies_ms,
        stage_confidences=result.stage_confidences,
        fallback_flags=result.fallback_flags,
        pipeline_confidence=result.pipeline_confidence,
    )

    log_event(
        "pipeline_completed",
        request_id=request.state.request_id,
        stage="pipeline",
        latency_ms=result.latency_ms,
        confidence=result.pipeline_confidence,
        fallback_used=any(result.fallback_flags.values()),
    )

    return {
        "session_id": result.session_id,
        "transcript": result.transcript,
        "detected_language": result.detected_language,
        "detected_emotion": result.detected_emotion,
        "detected_dialect": result.detected_dialect,
        "dialect_confidence": result.dialect_confidence,
        "translated_text": result.translated_text,
        "target_language": target_lang,
        "target_emotion": result.detected_emotion,
        "output_audio_url": output_audio_url,
        "confidence": result.emotion_confidence,
        "meta": meta,
    }


__all__ = ["app"]

