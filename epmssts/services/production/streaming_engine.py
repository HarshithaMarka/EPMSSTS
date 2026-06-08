from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter, time
from typing import Any, Dict, Optional

import numpy as np
import soundfile as sf

from epmssts.services.dialect.classifier import DialectClassifier
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.stt.transcriber import SpeechToTextService

from .calibration import ConfidenceCalibrator
from .diarization import SpeakerDiarizer
from .drift_monitor import DriftMonitor
from .edge_defense import EdgeCaseDefenseSystem
from .metrics import ProductionMetrics
from .session_memory import SessionMemoryEngine


@dataclass
class StreamingSession:
    session_id: str
    audio_buffer: list[np.ndarray] = field(default_factory=list)
    emotion_state: Dict[str, float] = field(default_factory=dict)
    dialect_state: Optional[str] = None
    speaker_embedding: Optional[np.ndarray] = None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=32))
    created_at: float = field(default_factory=time)
    last_activity: float = field(default_factory=time)


class StreamingInferenceEngine:
    def __init__(
        self,
        stt_service: SpeechToTextService,
        emotion_service: AudioEmotionService,
        dialect_classifier: DialectClassifier,
        *,
        session_memory: SessionMemoryEngine,
        edge_defense: EdgeCaseDefenseSystem,
        diarizer: SpeakerDiarizer,
        drift_monitor: DriftMonitor,
        calibrator: ConfidenceCalibrator,
        metrics: ProductionMetrics,
        max_latency_seconds: float = 2.0,
        queue_size: int = 32,
        session_ttl_seconds: int = 1800,
    ) -> None:
        self.stt_service = stt_service
        self.emotion_service = emotion_service
        self.dialect_classifier = dialect_classifier
        self.session_memory = session_memory
        self.edge_defense = edge_defense
        self.diarizer = diarizer
        self.drift_monitor = drift_monitor
        self.calibrator = calibrator
        self.metrics = metrics
        self.max_latency_seconds = max_latency_seconds
        self.queue_size = queue_size
        self.session_ttl_seconds = session_ttl_seconds

        self._sessions: dict[str, StreamingSession] = {}

    def get_or_create_session(self, session_id: str) -> StreamingSession:
        session = self._sessions.get(session_id)
        if session is None:
            session = StreamingSession(session_id=session_id)
            session.queue = asyncio.Queue(maxsize=self.queue_size)
            self._sessions[session_id] = session
        session.last_activity = time()
        return session

    def cleanup_sessions(self) -> int:
        now = time()
        expired = [sid for sid, sess in self._sessions.items() if now - sess.last_activity > self.session_ttl_seconds]
        for sid in expired:
            self._sessions.pop(sid, None)
        self.session_memory.cleanup_expired(self.session_ttl_seconds)
        return len(expired)

    async def enqueue_chunk(self, session_id: str, chunk_bytes: bytes, sample_rate: int) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)

        if session.queue.full():
            return {
                "status": "degraded",
                "reason": "backpressure_queue_full",
                "partial_transcript": "",
                "emotion": self.session_memory.dominant_emotion(session_id),
                "dialect": session.dialect_state or "standard_telugu",
                "confidence": 0.0,
            }

        timer = self.metrics.timer("streaming_enqueue")
        await session.queue.put((chunk_bytes, sample_rate, perf_counter()))
        timer.stop(success=True)

        return await self._process_next(session)

    async def _process_next(self, session: StreamingSession) -> Dict[str, Any]:
        timer = self.metrics.timer("streaming_inference")
        try:
            chunk_bytes, sample_rate, enqueue_ts = await asyncio.wait_for(
                session.queue.get(),
                timeout=self.max_latency_seconds,
            )
        except asyncio.TimeoutError:
            timer.stop(success=False)
            return {
                "status": "degraded",
                "reason": "queue_timeout",
                "partial_transcript": "",
                "emotion": self.session_memory.dominant_emotion(session.session_id),
                "dialect": session.dialect_state or "standard_telugu",
                "confidence": 0.0,
            }

        decode_timer = self.metrics.timer("streaming_decode")
        audio, sr = self._decode_chunk(chunk_bytes)
        decode_timer.stop(success=True)

        guard = self.edge_defense.validate_audio(audio, sr)
        if not guard.valid:
            timer.stop(success=False)
            return {
                "status": guard.status,
                "reason": guard.reason,
            }

        session.audio_buffer.append(audio)
        if len(session.audio_buffer) > 8:
            session.audio_buffer = session.audio_buffer[-8:]
        buffered = np.concatenate(session.audio_buffer, axis=0)

        try:
            inference = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, self._run_inference_sync, buffered, sr, session.session_id),
                timeout=self.max_latency_seconds,
            )
        except asyncio.TimeoutError:
            self.metrics.record_failure("streaming_inference")
            timer.stop(success=False)
            return {
                "status": "degraded",
                "reason": "inference_timeout",
                "partial_transcript": "",
                "emotion": self.session_memory.dominant_emotion(session.session_id),
                "dialect": session.dialect_state or "standard_telugu",
                "confidence": 0.0,
            }
        except Exception:
            self.metrics.record_failure("streaming_inference")
            timer.stop(success=False)
            return {
                "status": "degraded",
                "reason": "inference_failure",
                "partial_transcript": "",
                "emotion": self.session_memory.dominant_emotion(session.session_id),
                "dialect": session.dialect_state or "standard_telugu",
                "confidence": 0.0,
            }

        end_latency = perf_counter() - enqueue_ts
        if end_latency > self.max_latency_seconds:
            self.metrics.record_failure("streaming_latency")
            inference["status"] = "degraded"
            inference["reason"] = "latency_budget_exceeded"

        if inference.get("status") == "ok":
            session.dialect_state = inference.get("dialect")
            speaker_norm = inference.get("speaker_state", {}).get("centroid_norm")
            if speaker_norm is not None:
                session.speaker_embedding = np.array([float(speaker_norm)], dtype=np.float32)

        session.last_activity = time()
        timer.stop(success=True)
        return inference

    def _decode_chunk(self, chunk_bytes: bytes) -> tuple[np.ndarray, int]:
        from io import BytesIO

        data, sr = sf.read(BytesIO(chunk_bytes), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data.astype(np.float32), int(sr)

    def _run_inference_sync(self, audio: np.ndarray, sample_rate: int, session_id: str) -> Dict[str, Any]:
        stt_timer = self.metrics.timer("streaming_stt")
        stt_result = self.stt_service.transcribe(audio, sample_rate)
        stt_timer.stop(success=True)

        transcript = stt_result.text or ""
        transcript_guard = self.edge_defense.validate_transcript(transcript)
        if not transcript_guard.valid:
            return transcript_guard.to_dict()

        language_guard = self.edge_defense.validate_language((stt_result.language or "").lower())
        if not language_guard.valid:
            return language_guard.to_dict()

        emotion_timer = self.metrics.timer("streaming_emotion")
        emotion_prediction = self.emotion_service.predict(audio, sample_rate)
        emotion_timer.stop(success=True)

        dialect_timer = self.metrics.timer("streaming_dialect")
        dialect_prediction = self.dialect_classifier.detect(transcript)
        dialect_timer.stop(success=True)

        speaker_embedding = self.diarizer.extract_embedding(audio, sample_rate)
        speaker_id = self.diarizer.assign_speaker(speaker_embedding)
        self.diarizer.update_emotion_trend(speaker_id, emotion_prediction.label)

        smoothed_emotions = self.session_memory.update_emotion(session_id, emotion_prediction.scores)
        emotion_label = max(smoothed_emotions.items(), key=lambda item: item[1])[0] if smoothed_emotions else emotion_prediction.label
        dialect_label = self.session_memory.update_dialect(session_id, dialect_prediction.dialect)
        self.session_memory.update_speaker_state(session_id, speaker_id, float(np.linalg.norm(speaker_embedding)))

        raw_conf = float(min(emotion_prediction.confidence, dialect_prediction.confidence))
        calibrated_conf = self.calibrator.calibrate_probability(raw_conf)

        self.metrics.record_emotion(emotion_label)
        self.metrics.record_dialect_prediction(dialect_prediction.dialect, dialect_label)

        self.drift_monitor.add_sample(
            emotion=emotion_label,
            dialect=dialect_label,
            confidence=calibrated_conf,
            embedding_norm=float(np.linalg.norm(speaker_embedding)),
        )

        return {
            "status": "ok",
            "partial_transcript": transcript,
            "emotion": emotion_label,
            "dialect": dialect_label,
            "confidence": calibrated_conf,
            "speaker_id": speaker_id,
            "speaker_state": self.diarizer.snapshot().get(speaker_id, {}),
        }
