from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, Optional

try:
    from prometheus_client import Counter, Histogram

    PROMETHEUS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    PROMETHEUS_AVAILABLE = False

API_SCHEMA_VERSION = "1.1"

logger = logging.getLogger("epmssts.observability")


@dataclass
class StageMetrics:
    stage: str
    latency_ms: int
    confidence: Optional[float]
    fallback_used: bool


if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        "epmssts_request_total",
        "Total API requests",
        ["endpoint", "method", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "epmssts_request_latency_ms",
        "Request latency in milliseconds",
        ["endpoint"],
        buckets=(50, 100, 200, 400, 800, 1200, 2000, 5000, 10000),
    )
    STAGE_LATENCY = Histogram(
        "epmssts_stage_latency_ms",
        "Pipeline stage latency in milliseconds",
        ["stage"],
        buckets=(50, 100, 200, 400, 800, 1200, 2000, 5000, 10000),
    )
    STAGE_ERRORS = Counter(
        "epmssts_stage_errors_total",
        "Stage error count",
        ["stage", "error_type"],
    )
    STAGE_FALLBACK = Counter(
        "epmssts_stage_fallback_total",
        "Stage fallback usage count",
        ["stage"],
    )
    STAGE_RETRIES = Counter(
        "epmssts_stage_retry_total",
        "Stage retry count",
        ["stage"],
    )
    SILENCE_REJECT = Counter(
        "epmssts_silence_reject_total",
        "Silence rejection count",
        ["stage"],
    )
    THROTTLE_COUNT = Counter(
        "epmssts_throttled_total",
        "Throttled request count",
        ["endpoint"],
    )
else:  # pragma: no cover - noop metrics
    REQUEST_COUNT = REQUEST_LATENCY = STAGE_LATENCY = None
    STAGE_ERRORS = STAGE_FALLBACK = STAGE_RETRIES = None
    SILENCE_REJECT = THROTTLE_COUNT = None


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, separators=(",", ":")))


def record_request(endpoint: str, method: str, status: int, latency_ms: int) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    REQUEST_COUNT.labels(endpoint=endpoint, method=method, status=str(status)).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency_ms)


def record_stage_latency(stage: str, latency_ms: int) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    STAGE_LATENCY.labels(stage=stage).observe(latency_ms)


def record_stage_error(stage: str, error_type: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    STAGE_ERRORS.labels(stage=stage, error_type=error_type).inc()


def record_stage_fallback(stage: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    STAGE_FALLBACK.labels(stage=stage).inc()


def record_stage_retry(stage: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    STAGE_RETRIES.labels(stage=stage).inc()


def record_silence_reject(stage: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    SILENCE_REJECT.labels(stage=stage).inc()


def record_throttle(endpoint: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    THROTTLE_COUNT.labels(endpoint=endpoint).inc()


def get_max_concurrency(default: int = 4) -> int:
    try:
        return int(os.getenv("EPMSSTS_MAX_CONCURRENT_PIPELINES", str(default)))
    except ValueError:
        return default


def now_ms() -> int:
    return int(perf_counter() * 1000)


def build_meta(
    *,
    request_id: str,
    stage: str,
    latency_ms: int,
    confidence: Optional[float],
    fallback_used: bool,
    audio_metrics: Optional[Dict[str, float]] = None,
    stage_latencies: Optional[Dict[str, int]] = None,
    stage_confidences: Optional[Dict[str, Optional[float]]] = None,
    fallback_flags: Optional[Dict[str, bool]] = None,
    pipeline_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": API_SCHEMA_VERSION,
        "request_id": request_id,
        "stage": stage,
        "latency_ms": latency_ms,
        "confidence": confidence,
        "fallback_used": fallback_used,
    }

    if audio_metrics is not None:
        payload["audio_metrics"] = audio_metrics
    if stage_latencies is not None:
        payload["stage_latencies_ms"] = stage_latencies
    if stage_confidences is not None:
        payload["stage_confidences"] = stage_confidences
    if fallback_flags is not None:
        payload["fallbacks"] = fallback_flags
    if pipeline_confidence is not None:
        payload["pipeline_confidence"] = pipeline_confidence

    return payload
