"""Production-grade orchestration control plane service."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

import numpy as np

from .circuit_breaker import CircuitBreakerManager
from .schemas import (
    ConfidenceSummary,
    FailureModeRow,
    OrchestrationSLAConfig,
    PipelineHealthResponse,
    PipelineMetricsResponse,
    PipelineProcessRequest,
    PipelineProcessResponse,
    PipelineStatus,
    PipelineStatusResponse,
    PipelineTraceResponse,
    StageExecutionStatus,
    StageName,
    StageSLAConfig,
    StageTraceRecord,
)
from .state_store import OrchestrationStateStore


logger = logging.getLogger(__name__)


@dataclass
class StageClients:
    preprocess: Callable[[bytes], Awaitable[Dict[str, Any]]]
    stt: Callable[[bytes], Awaitable[Dict[str, Any]]]
    emotion: Callable[[bytes, str], Awaitable[Dict[str, Any]]]
    translation: Callable[[str, str, str, float], Awaitable[Dict[str, Any]]]
    tts: Callable[[str, str, str, float, float], Awaitable[Dict[str, Any]]]


class OrchestrationService:
    CONFIDENCE_WEIGHTS = {
        "stt": 0.35,
        "emotion": 0.15,
        "translation": 0.30,
        "tts": 0.20,
    }

    def __init__(
        self,
        clients: StageClients,
        state_store: OrchestrationStateStore,
        circuit_breakers: CircuitBreakerManager,
        sla_config: Optional[OrchestrationSLAConfig] = None,
        max_concurrency: int = 32,
    ):
        self.clients = clients
        self.state_store = state_store
        self.circuit_breakers = circuit_breakers
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency = max_concurrency
        self._started_at = time.time()

        default_sla = {
            StageName.AUDIO_PREPROCESSING: StageSLAConfig(stage_name=StageName.AUDIO_PREPROCESSING, timeout_ms=900, target_p95_ms=700),
            StageName.STT: StageSLAConfig(stage_name=StageName.STT, timeout_ms=1700, target_p95_ms=1200),
            StageName.EMOTION: StageSLAConfig(stage_name=StageName.EMOTION, timeout_ms=1200, target_p95_ms=900),
            StageName.TRANSLATION: StageSLAConfig(stage_name=StageName.TRANSLATION, timeout_ms=1500, target_p95_ms=1000),
            StageName.TTS: StageSLAConfig(stage_name=StageName.TTS, timeout_ms=2000, target_p95_ms=1500),
        }
        self.sla_config = sla_config or OrchestrationSLAConfig(
            total_pipeline_p95_ms=5000,
            stage_sla=default_sla,
        )

        self.total_requests = 0
        self.degraded_requests = 0
        self.failed_requests = 0
        self.sla_breach_count = 0
        self.stage_failures: Counter[str] = Counter()
        self.stage_retries: Counter[str] = Counter()
        self.confidence_buckets: Counter[str] = Counter()
        self.latency_history: deque[float] = deque(maxlen=5000)

    async def process(self, request: PipelineProcessRequest) -> PipelineProcessResponse:
        start = time.perf_counter()
        trace_id = request.request_id
        stage_traces: list[StageTraceRecord] = []
        pipeline_status = PipelineStatus.SUCCESS

        transcript = ""
        emotion_label = "neutral"
        translation_text = ""
        audio_output_url: Optional[str] = None

        confidence = ConfidenceSummary(
            confidence_weights=dict(self.CONFIDENCE_WEIGHTS),
        )

        async with self._semaphore:
            self.total_requests += 1

            try:
                raw_audio = base64.b64decode(request.audio_file)
            except Exception:
                self.failed_requests += 1
                pipeline_status = PipelineStatus.FAILED
                total_ms = (time.perf_counter() - start) * 1000.0
                return self._build_response(
                    status=pipeline_status,
                    transcript="",
                    emotion="neutral",
                    translation="",
                    audio_url=None,
                    confidence=confidence,
                    stage_traces=stage_traces,
                    total_latency_ms=total_ms,
                    request_trace_id=trace_id,
                )

            preprocess_result = await self._run_stage(
                stage=StageName.AUDIO_PREPROCESSING,
                trace_id=trace_id,
                call=lambda: self.clients.preprocess(raw_audio),
                fallback=None,
            )
            stage_traces.append(preprocess_result["trace"])
            if preprocess_result["trace"].status in {StageExecutionStatus.FAILED, StageExecutionStatus.TIMEOUT, StageExecutionStatus.CIRCUIT_OPEN}:
                pipeline_status = PipelineStatus.FAILED
                self.failed_requests += 1
                return await self._finalize(trace_id, request.request_id, pipeline_status, transcript, emotion_label, translation_text, audio_output_url, confidence, stage_traces, start)

            # Parallel stage: STT + Emotion
            stt_task = asyncio.create_task(
                self._run_stage(
                    stage=StageName.STT,
                    trace_id=trace_id,
                    call=lambda: self.clients.stt(raw_audio),
                    fallback=None,
                )
            )
            emotion_task = asyncio.create_task(
                self._run_stage(
                    stage=StageName.EMOTION,
                    trace_id=trace_id,
                    call=lambda: self.clients.emotion(raw_audio, ""),
                    fallback=lambda: {"emotion": "neutral", "confidence": 0.35},
                )
            )
            stt_result, emotion_result = await asyncio.gather(stt_task, emotion_task)
            stage_traces.append(stt_result["trace"])
            stage_traces.append(emotion_result["trace"])

            # STT is critical
            if stt_result["trace"].status in {StageExecutionStatus.FAILED, StageExecutionStatus.TIMEOUT, StageExecutionStatus.CIRCUIT_OPEN}:
                pipeline_status = PipelineStatus.FAILED
                self.failed_requests += 1
                return await self._finalize(trace_id, request.request_id, pipeline_status, transcript, emotion_label, translation_text, audio_output_url, confidence, stage_traces, start)

            transcript = str(stt_result["payload"].get("transcript", ""))
            confidence.stt_confidence = float(stt_result["payload"].get("confidence", 0.0))

            if emotion_result["trace"].status in {StageExecutionStatus.DEGRADED, StageExecutionStatus.FAILED, StageExecutionStatus.TIMEOUT, StageExecutionStatus.CIRCUIT_OPEN}:
                pipeline_status = PipelineStatus.DEGRADED
                emotion_label = "neutral"
                confidence.emotion_confidence = 0.35
            else:
                emotion_label = str(emotion_result["payload"].get("emotion", "neutral"))
                confidence.emotion_confidence = float(emotion_result["payload"].get("confidence", 0.35))

            # Translation: retry once, then fallback to source text
            translation_result = await self._run_stage(
                stage=StageName.TRANSLATION,
                trace_id=trace_id,
                call=lambda: self.clients.translation(transcript, "auto", request.target_language, confidence.emotion_confidence),
                fallback=lambda: {"translated_text": transcript, "confidence": max(0.3, confidence.stt_confidence * 0.8)},
                retry_once=True,
            )
            stage_traces.append(translation_result["trace"])
            if translation_result["trace"].status in {StageExecutionStatus.DEGRADED, StageExecutionStatus.TIMEOUT, StageExecutionStatus.FAILED, StageExecutionStatus.CIRCUIT_OPEN}:
                pipeline_status = PipelineStatus.DEGRADED
            translation_text = str(translation_result["payload"].get("translated_text", transcript))
            confidence.translation_confidence = float(translation_result["payload"].get("confidence", 0.0))

            # TTS: retry + fallback; if still fails return text-only degraded
            tts_result = await self._run_stage(
                stage=StageName.TTS,
                trace_id=trace_id,
                call=lambda: self.clients.tts(
                    translation_text,
                    request.target_language,
                    emotion_label,
                    confidence.emotion_confidence,
                    confidence.translation_confidence,
                ),
                fallback=lambda: {"audio_output_url": None, "validation_confidence": 0.0},
                retry_once=True,
            )
            stage_traces.append(tts_result["trace"])

            if tts_result["trace"].status in {StageExecutionStatus.FAILED, StageExecutionStatus.TIMEOUT, StageExecutionStatus.CIRCUIT_OPEN}:
                pipeline_status = PipelineStatus.DEGRADED
                audio_output_url = None
                confidence.tts_validation_confidence = 0.0
            else:
                audio_output_url = tts_result["payload"].get("audio_output_url")
                confidence.tts_validation_confidence = float(tts_result["payload"].get("validation_confidence", 0.0))
                if tts_result["trace"].status == StageExecutionStatus.DEGRADED:
                    pipeline_status = PipelineStatus.DEGRADED

            confidence.system_confidence = self._compute_system_confidence(confidence)
            confidence.uncertainty_flag = confidence.system_confidence < 0.55
            self._record_confidence_distribution(confidence.system_confidence)

            if confidence.uncertainty_flag and pipeline_status == PipelineStatus.SUCCESS:
                pipeline_status = PipelineStatus.DEGRADED

            return await self._finalize(
                trace_id,
                request.request_id,
                pipeline_status,
                transcript,
                emotion_label,
                translation_text,
                audio_output_url,
                confidence,
                stage_traces,
                start,
            )

    async def get_trace(self, request_id: str) -> Optional[PipelineTraceResponse]:
        payload = await self.state_store.get_json(self._trace_key(request_id))
        if not payload:
            return None
        return PipelineTraceResponse.model_validate(payload)

    async def get_status(self) -> PipelineStatusResponse:
        degraded_rate = self.degraded_requests / max(self.total_requests, 1)
        failure_rate = self.failed_requests / max(self.total_requests, 1)
        circuits = await self.circuit_breakers.get_states()
        active_requests = self._max_concurrency - self._semaphore._value

        return PipelineStatusResponse(
            status="healthy" if failure_rate < 0.5 else "degraded",
            active_requests=max(0, active_requests),
            max_concurrency=self._max_concurrency,
            total_requests=self.total_requests,
            degraded_rate=degraded_rate,
            failure_rate=failure_rate,
            sla_breach_count=self.sla_breach_count,
            circuit_states=circuits,
        )

    async def get_health(self) -> PipelineHealthResponse:
        status = await self.get_status()
        deps = {
            "redis": self.state_store.redis_connected,
            "audio_preprocessing": True,
            "stt": True,
            "emotion": True,
            "translation": True,
            "tts": True,
        }
        return PipelineHealthResponse(
            status=status.status,
            redis_connected=self.state_store.redis_connected,
            dependencies=deps,
            uptime_seconds=time.time() - self._started_at,
        )

    def get_metrics(self) -> PipelineMetricsResponse:
        total = max(self.total_requests, 1)
        degraded_rate = self.degraded_requests / total

        stage_failure_rate = {
            stage: count / total for stage, count in self.stage_failures.items()
        }
        stage_retry_rate = {
            stage: count / total for stage, count in self.stage_retries.items()
        }

        histogram = self._latency_histogram()

        return PipelineMetricsResponse(
            pipeline_latency_histogram=histogram,
            stage_failure_rate=stage_failure_rate,
            stage_retry_rate=stage_retry_rate,
            degraded_response_rate=degraded_rate,
            confidence_distribution=dict(self.confidence_buckets),
            sla_breach_count=self.sla_breach_count,
            requests_total=self.total_requests,
        )

    def get_failure_mode_table(self) -> list[FailureModeRow]:
        return [
            FailureModeRow(stage=StageName.AUDIO_PREPROCESSING, failure_type="timeout", impact="pipeline blocked", fallback="none", status_returned=PipelineStatus.FAILED),
            FailureModeRow(stage=StageName.STT, failure_type="model crash", impact="no transcript", fallback="abort", status_returned=PipelineStatus.FAILED),
            FailureModeRow(stage=StageName.EMOTION, failure_type="low confidence", impact="emotion uncertain", fallback="neutral", status_returned=PipelineStatus.DEGRADED),
            FailureModeRow(stage=StageName.TRANSLATION, failure_type="empty output", impact="no translated text", fallback="retry then source text", status_returned=PipelineStatus.DEGRADED),
            FailureModeRow(stage=StageName.TTS, failure_type="gpu unavailable", impact="no rendered audio", fallback="retry then text-only", status_returned=PipelineStatus.DEGRADED),
            FailureModeRow(stage=StageName.TTS, failure_type="memory exhaustion", impact="rendering interrupted", fallback="fallback TTS", status_returned=PipelineStatus.DEGRADED),
        ]

    async def _finalize(
        self,
        trace_id: str,
        request_id: str,
        status: PipelineStatus,
        transcript: str,
        emotion: str,
        translation: str,
        audio_output_url: Optional[str],
        confidence: ConfidenceSummary,
        stage_traces: list[StageTraceRecord],
        start_time: float,
    ) -> PipelineProcessResponse:
        total_latency_ms = (time.perf_counter() - start_time) * 1000.0
        self.latency_history.append(total_latency_ms)

        if total_latency_ms > float(self.sla_config.total_pipeline_p95_ms):
            self.sla_breach_count += 1
            if status == PipelineStatus.SUCCESS:
                status = PipelineStatus.DEGRADED

        if status == PipelineStatus.DEGRADED:
            self.degraded_requests += 1

        stage_latencies = {trace.stage_name.value: trace.latency_ms for trace in stage_traces}

        trace = PipelineTraceResponse(
            request_trace_id=trace_id,
            request_id=request_id,
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            total_latency_ms=total_latency_ms,
            stage_traces=stage_traces,
            confidence_summary=confidence,
            metadata={"target_language": "unknown"},
        )
        await self.state_store.set_json(self._trace_key(request_id), trace.model_dump(mode="json"), ttl=6 * 3600)

        return self._build_response(
            status=status,
            transcript=transcript,
            emotion=emotion,
            translation=translation,
            audio_url=audio_output_url,
            confidence=confidence,
            stage_traces=stage_traces,
            total_latency_ms=total_latency_ms,
            request_trace_id=trace_id,
        )

    def _build_response(
        self,
        status: PipelineStatus,
        transcript: str,
        emotion: str,
        translation: str,
        audio_url: Optional[str],
        confidence: ConfidenceSummary,
        stage_traces: list[StageTraceRecord],
        total_latency_ms: float,
        request_trace_id: str,
    ) -> PipelineProcessResponse:
        stage_latencies = {trace.stage_name.value: trace.latency_ms for trace in stage_traces}
        return PipelineProcessResponse(
            status=status,
            transcript=transcript,
            emotion=emotion,
            translation=translation,
            audio_output_url=audio_url,
            confidence_summary=confidence,
            stage_latencies=stage_latencies,
            total_latency_ms=total_latency_ms,
            request_trace_id=request_trace_id,
        )

    async def _run_stage(
        self,
        stage: StageName,
        trace_id: str,
        call: Callable[[], Awaitable[Dict[str, Any]]],
        fallback: Optional[Callable[[], Dict[str, Any]]],
        retry_once: bool = False,
    ) -> Dict[str, Any]:
        if not await self.circuit_breakers.allow_request(stage.value):
            trace = self._make_trace(stage, StageExecutionStatus.CIRCUIT_OPEN, 0.0, None, 0, False, "circuit_open")
            self.stage_failures[stage.value] += 1
            if fallback:
                payload = fallback()
                trace.status = StageExecutionStatus.DEGRADED
                trace.fallback_used = True
                trace.fallback_type = "circuit_fallback"
                return {"payload": payload, "trace": trace}
            return {"payload": {}, "trace": trace}

        timeout_ms = self.sla_config.stage_sla[stage].timeout_ms
        started_at = datetime.now(timezone.utc)
        start = time.perf_counter()
        attempts = 0

        async def _attempt() -> Dict[str, Any]:
            return await asyncio.wait_for(call(), timeout=timeout_ms / 1000.0)

        try:
            attempts += 1
            payload = await _attempt()
            latency = (time.perf_counter() - start) * 1000.0
            trace = self._make_trace(stage, StageExecutionStatus.SUCCESS, latency, started_at, attempts - 1, False)
            await self.circuit_breakers.record_success(stage.value)
            return {"payload": payload, "trace": trace}
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start) * 1000.0
            self.stage_failures[stage.value] += 1
            await self.circuit_breakers.record_failure(stage.value)
            trace = self._make_trace(stage, StageExecutionStatus.TIMEOUT, latency, started_at, attempts - 1, False, "timeout")
            if fallback:
                trace.status = StageExecutionStatus.DEGRADED
                trace.fallback_used = True
                trace.fallback_type = "timeout_fallback"
                return {"payload": fallback(), "trace": trace}
            return {"payload": {}, "trace": trace}
        except Exception as exc:
            self.stage_failures[stage.value] += 1
            await self.circuit_breakers.record_failure(stage.value)
            if retry_once:
                self.stage_retries[stage.value] += 1
                try:
                    attempts += 1
                    payload = await _attempt()
                    latency = (time.perf_counter() - start) * 1000.0
                    trace = self._make_trace(stage, StageExecutionStatus.SUCCESS, latency, started_at, 1, False)
                    await self.circuit_breakers.record_success(stage.value)
                    return {"payload": payload, "trace": trace}
                except Exception as retry_exc:
                    latency = (time.perf_counter() - start) * 1000.0
                    trace = self._make_trace(stage, StageExecutionStatus.FAILED, latency, started_at, 1, False, str(retry_exc))
                    if fallback:
                        trace.status = StageExecutionStatus.DEGRADED
                        trace.fallback_used = True
                        trace.fallback_type = "retry_fallback"
                        return {"payload": fallback(), "trace": trace}
                    return {"payload": {}, "trace": trace}

            latency = (time.perf_counter() - start) * 1000.0
            trace = self._make_trace(stage, StageExecutionStatus.FAILED, latency, started_at, attempts - 1, False, str(exc))
            if fallback:
                trace.status = StageExecutionStatus.DEGRADED
                trace.fallback_used = True
                trace.fallback_type = "stage_fallback"
                return {"payload": fallback(), "trace": trace}
            return {"payload": {}, "trace": trace}

    def _make_trace(
        self,
        stage: StageName,
        status: StageExecutionStatus,
        latency_ms: float,
        started_at: Optional[datetime],
        retry_count: int,
        fallback_used: bool,
        error: Optional[str] = None,
    ) -> StageTraceRecord:
        now = datetime.now(timezone.utc)
        started = started_at or now
        sla_target = self.sla_config.stage_sla[stage].target_p95_ms
        breached = latency_ms > float(sla_target)
        if breached:
            self.sla_breach_count += 1

        return StageTraceRecord(
            stage_name=stage,
            started_at=started,
            ended_at=now,
            latency_ms=latency_ms,
            status=status,
            confidence=None,
            retry_count=retry_count,
            fallback_used=fallback_used,
            fallback_type=None,
            error=error,
            sla_target_ms=sla_target,
            sla_breached=breached,
        )

    def _compute_system_confidence(self, confidence: ConfidenceSummary) -> float:
        value = (
            confidence.stt_confidence * self.CONFIDENCE_WEIGHTS["stt"]
            + confidence.emotion_confidence * self.CONFIDENCE_WEIGHTS["emotion"]
            + confidence.translation_confidence * self.CONFIDENCE_WEIGHTS["translation"]
            + confidence.tts_validation_confidence * self.CONFIDENCE_WEIGHTS["tts"]
        )
        return float(np.clip(value, 0.0, 1.0))

    def _record_confidence_distribution(self, value: float):
        if value < 0.4:
            self.confidence_buckets["0.0-0.4"] += 1
        elif value < 0.6:
            self.confidence_buckets["0.4-0.6"] += 1
        elif value < 0.8:
            self.confidence_buckets["0.6-0.8"] += 1
        else:
            self.confidence_buckets["0.8-1.0"] += 1

    def _latency_histogram(self) -> Dict[str, int]:
        buckets = {
            "le_1000": 0,
            "le_2000": 0,
            "le_3000": 0,
            "le_5000": 0,
            "gt_5000": 0,
        }
        for value in self.latency_history:
            if value <= 1000:
                buckets["le_1000"] += 1
            elif value <= 2000:
                buckets["le_2000"] += 1
            elif value <= 3000:
                buckets["le_3000"] += 1
            elif value <= 5000:
                buckets["le_5000"] += 1
            else:
                buckets["gt_5000"] += 1
        return buckets

    @staticmethod
    def _trace_key(request_id: str) -> str:
        return f"orchestrator:trace:{request_id}"
