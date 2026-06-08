from __future__ import annotations

"""
End-to-end speech-to-speech orchestration for EPMSSTS.

This module wires together the existing services:
- STT (faster-whisper)
- Audio-based emotion detection
- Rule-based dialect detection
- Pure text translation
- Emotion-conditioned TTS

Service implementations themselves must not be modified.
"""

from dataclasses import dataclass
from time import perf_counter
import logging
from typing import Literal, Optional, Tuple

import asyncio
from pathlib import Path
from uuid import uuid4

import numpy as np

from epmssts.services.stt.audio_handler import (
    compute_audio_metrics,
    detect_voice_activity,
    preprocess_audio_bytes,
)
from epmssts.api.observability import record_stage_fallback, record_stage_latency, record_stage_retry
from epmssts.services.stt.transcriber import SpeechToTextService, TranscriptionResult
from epmssts.services.emotion.audio_emotion import AudioEmotionService, EmotionPrediction
from epmssts.services.emotion.text_emotion import TextEmotionService
from epmssts.services.emotion.fusion import fuse_emotions
from epmssts.services.dialect.classifier import DialectClassifier, DialectPrediction
from epmssts.services.translation.translator import TranslationService, TranslationResult
from epmssts.services.tts.synthesizer_edge import EdgeTtsService as TtsService, TtsSynthesisRequest


TargetLang = Literal["en", "te", "hi"]

logger = logging.getLogger("epmssts.pipeline")


@dataclass
class SpeechToSpeechResult:
    session_id: str
    transcript: str
    detected_language: str
    detected_emotion: str
    emotion_confidence: float
    detected_dialect: str
    dialect_confidence: float
    translated_text: str
    audio_path: Path
    latency_ms: int
    stage_latencies_ms: dict[str, int]
    stage_confidences: dict[str, Optional[float]]
    fallback_flags: dict[str, bool]
    audio_metrics: dict[str, float]
    pipeline_confidence: float


async def _run_stt_and_emotion(
    audio_16k: np.ndarray,
    sample_rate: int,
    stt_service: SpeechToTextService,
    emotion_service: AudioEmotionService,
) -> Tuple[TranscriptionResult, EmotionPrediction]:
    loop = asyncio.get_event_loop()

    async def _stt() -> TranscriptionResult:
        return await loop.run_in_executor(
            None, stt_service.transcribe, audio_16k, sample_rate
        )

    async def _emotion() -> EmotionPrediction:
        return await loop.run_in_executor(
            None, emotion_service.predict, audio_16k, sample_rate
        )

    return await asyncio.gather(_stt(), _emotion())


async def run_speech_to_speech(
    file_bytes: bytes,
    target_lang: TargetLang,
    *,
    stt_service: SpeechToTextService,
    emotion_service: AudioEmotionService,
    dialect_classifier: DialectClassifier,
    translation_service: TranslationService,
    tts_service: Optional[TtsService],
    text_emotion_service: Optional[TextEmotionService] = None,
    outputs_dir: Path,
    timeout_seconds: float = 120.0,
) -> SpeechToSpeechResult:
    """
    Run the complete speech-to-speech pipeline.

    The entire orchestration is wrapped in an outer timeout in the API
    layer; this function focuses on chaining the existing services.
    """
    start = perf_counter()
    session_id = str(uuid4())
    stage_latencies: dict[str, int] = {}
    stage_confidences: dict[str, Optional[float]] = {
        "stt": None,
        "emotion": None,
        "dialect": None,
        "translation": None,
        "tts": None,
    }
    fallback_flags: dict[str, bool] = {
        "silence_short_circuit": False,
        "stt_fallback": False,
        "emotion_fallback": False,
        "dialect_fallback": False,
        "translation_retry": False,
        "tts_fallback": False,
    }

    # Ensure outputs directory exists.
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # 1) Audio preprocessing (16kHz mono).
    try:
        audio_16k, sample_rate = preprocess_audio_bytes(file_bytes)
    except ValueError as exc:
        raise ValueError(f"Invalid audio: {exc}") from exc
    except Exception as exc:  # Unexpected decode errors
        raise RuntimeError(f"Unable to decode or preprocess audio: {exc}") from exc

    audio_metrics = compute_audio_metrics(audio_16k, sample_rate)
    logger.info(
        "[session=%s] audio metrics duration=%.3fs rms=%.6f peak=%.4f speech_ratio=%.2f clipped=%.3f",
        session_id,
        audio_metrics["duration_sec"],
        audio_metrics["rms"],
        audio_metrics["peak"],
        audio_metrics["speech_ratio"],
        audio_metrics["clipped_ratio"],
    )

    # Early silence/VAD rejection: consistent with individual STT endpoint behavior.
    # Prevents unnecessary processing of silent or near-silent audio.
    if stt_service.is_silent(audio_16k) or detect_voice_activity(audio_16k, sample_rate) < 0.05:
        logger.warning(
            "[session=%s] Rejecting silent/near-silent audio: rms=%.6f speech_ratio=%.2f",
            session_id,
            audio_metrics["rms"],
            audio_metrics["speech_ratio"],
        )
        raise ValueError("Audio appears to be silent or too quiet for processing.")

    # 2) STT + Emotion in parallel.
    try:
        stage_start = perf_counter()
        stt_result, emotion_result = await asyncio.wait_for(
            _run_stt_and_emotion(audio_16k, sample_rate, stt_service, emotion_service),
            timeout=timeout_seconds,
        )
        stage_latencies["stt_emotion"] = int((perf_counter() - stage_start) * 1000)
        record_stage_latency("stt_emotion", stage_latencies["stt_emotion"])
    except asyncio.TimeoutError as exc:
        raise TimeoutError("STT + emotion phase exceeded time limit") from exc

    transcript = stt_result.text or ""
    detected_language = (stt_result.language or "").lower()
    if detected_language not in {"en", "te", "hi"}:
        # Fallback to English if Whisper returns an unsupported code.
        detected_language = "en"

    if not transcript.strip():
        try:
            retry_audio, _ = preprocess_audio_bytes(
                file_bytes, trim_silence=False, reduce_noise=False
            )
            stt_retry = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, stt_service.transcribe, retry_audio, sample_rate
                ),
                timeout=timeout_seconds,
            )
            transcript = stt_retry.text or transcript
            stt_result = stt_retry
            fallback_flags["stt_fallback"] = True
            record_stage_retry("stt")
            if transcript:
                logger.info("[session=%s] STT retry recovered transcript", session_id)
        except Exception:
            logger.warning("[session=%s] STT retry failed; continuing", session_id)

    if hasattr(stt_service, "_model_available") and not getattr(stt_service, "_model_available"):
        fallback_flags["stt_fallback"] = True
        record_stage_fallback("stt")

    detected_emotion = emotion_result.label
    stage_confidences["emotion"] = float(emotion_result.confidence)
    if emotion_result.confidence < 0.4:
        detected_emotion = "neutral"
        emotion_result = EmotionPrediction(
            label="neutral",
            confidence=0.4,
            scores={"neutral": 1.0, "happy": 0.0, "sad": 0.0, "angry": 0.0, "fearful": 0.0},
        )
        stage_confidences["emotion"] = float(emotion_result.confidence)
        fallback_flags["emotion_fallback"] = True
        record_stage_fallback("emotion")

    if hasattr(emotion_service, "_model_available") and not getattr(emotion_service, "_model_available"):
        fallback_flags["emotion_fallback"] = True
        record_stage_fallback("emotion")

    # Optional text emotion for English, with fusion.
    if (
        text_emotion_service is not None
        and detected_language == "en"
        and transcript.strip()
    ):
        loop = asyncio.get_event_loop()

        async def _text_emotion() -> EmotionPrediction:
            return await loop.run_in_executor(
                None, text_emotion_service.predict, transcript
            )

        try:
            text_pred = await asyncio.wait_for(_text_emotion(), timeout=timeout_seconds)
            fused = fuse_emotions(emotion_result, text_pred)
            detected_emotion = fused.label
            emotion_result = fused
        except asyncio.TimeoutError:
            # Keep audio emotion if text emotion is too slow
            pass
        except Exception:
            # Keep audio emotion if text emotion fails
            pass

    # 3) Dialect detection (Telugu only, metadata only).
    dialect_confidence = 1.0
    if detected_language == "te" and transcript.strip():
        try:
            dialect_prediction: DialectPrediction = dialect_classifier.detect(transcript)
            dialect_confidence = float(dialect_prediction.confidence)
            detected_dialect = (
                dialect_prediction.dialect
                if dialect_prediction.confidence >= 0.55
                else "standard_telugu"
            )
            if dialect_prediction.confidence < 0.55:
                fallback_flags["dialect_fallback"] = True
                record_stage_fallback("dialect")
        except Exception:
            detected_dialect = "standard_telugu"
            dialect_confidence = 0.5
            fallback_flags["dialect_fallback"] = True
            record_stage_fallback("dialect")
    else:
        detected_dialect = "standard_telugu"
        dialect_confidence = 1.0

    stage_confidences["dialect"] = dialect_confidence

    # 4) Translation (pure text).
    if not transcript.strip():
        translated_text = ""
    elif detected_language == target_lang:
        translated_text = transcript
    else:
        loop = asyncio.get_event_loop()

        async def _translate() -> TranslationResult:
            return await loop.run_in_executor(
                None,
                translation_service.translate,
                transcript,
                detected_language,
                target_lang,
            )

        try:
            stage_start = perf_counter()
            translation_result = await asyncio.wait_for(_translate(), timeout=timeout_seconds)
            stage_latencies["translation"] = int((perf_counter() - stage_start) * 1000)
            record_stage_latency("translation", stage_latencies["translation"])
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Translation phase exceeded time limit") from exc

        translated_text = translation_result.translated_text

        if transcript.strip() and not translated_text.strip():
            try:
                translation_result = await asyncio.wait_for(
                    _translate(), timeout=timeout_seconds
                )
                translated_text = translation_result.translated_text
                fallback_flags["translation_retry"] = True
                record_stage_retry("translation")
            except Exception:
                logger.warning("[session=%s] Translation retry failed", session_id)

    # 5) TTS with emotion-conditioned speed (target language).
    if not translated_text.strip():
        # If there is no text to speak, we still complete the session but
        # skip audio synthesis and return an empty (zero-length) WAV file.
        audio_path = outputs_dir / f"{session_id}.wav"
        audio_path.touch()
    elif tts_service is None:
        # TTS is optional in dev environments; attempt a lazy fallback synth.
        try:
            fallback_tts = TtsService()
            tts_request = TtsSynthesisRequest(
                text=translated_text,
                language=target_lang,
                emotion=detected_emotion,
                dialect=detected_dialect if detected_dialect != "unknown" else None,
            )
            wav_bytes = await fallback_tts.synthesize(tts_request)
            audio_path = outputs_dir / f"{session_id}.wav"
            audio_path.write_bytes(wav_bytes)
        except Exception:
            audio_path = outputs_dir / f"{session_id}.wav"
            audio_path.touch()
    else:
        tts_request = TtsSynthesisRequest(
            text=translated_text,
            language=target_lang,
            emotion=detected_emotion,
            dialect=detected_dialect if detected_dialect != "unknown" else None,
        )

        # Edge TTS is async by design - call directly
        try:
            stage_start = perf_counter()
            wav_bytes = await asyncio.wait_for(
                tts_service.synthesize(tts_request),
                timeout=30.0
            )
            stage_latencies["tts"] = int((perf_counter() - stage_start) * 1000)
            record_stage_latency("tts", stage_latencies["tts"])
        except asyncio.TimeoutError as exc:
            raise TimeoutError("TTS phase exceeded time limit") from exc

        audio_path = outputs_dir / f"{session_id}.wav"
        audio_path.write_bytes(wav_bytes)

        if hasattr(tts_service, "_engine_kind") and getattr(tts_service, "_engine_kind") != "coqui":
            fallback_flags["tts_fallback"] = True
            record_stage_fallback("tts")

    latency_ms = int((perf_counter() - start) * 1000)
    confidences = [value for value in stage_confidences.values() if value is not None]
    pipeline_confidence = float(min(confidences)) if confidences else 1.0
    if stage_latencies:
        logger.info("[session=%s] stage latencies ms=%s", session_id, stage_latencies)

    return SpeechToSpeechResult(
        session_id=session_id,
        transcript=transcript,
        detected_language=detected_language,
        detected_emotion=detected_emotion,
        emotion_confidence=emotion_result.confidence,
        detected_dialect=detected_dialect,
        dialect_confidence=dialect_confidence,
        translated_text=translated_text,
        audio_path=audio_path,
        latency_ms=latency_ms,
        stage_latencies_ms=stage_latencies,
        stage_confidences=stage_confidences,
        fallback_flags=fallback_flags,
        audio_metrics=audio_metrics,
        pipeline_confidence=pipeline_confidence,
    )


__all__ = ["run_speech_to_speech", "SpeechToSpeechResult", "TargetLang"]

