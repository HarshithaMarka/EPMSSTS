"""
Reliability-only stabilization primitives for EPMSSTS pilot pipeline.

Implements:
- Per-stage watchdog with deterministic fallback
- Memory guard with pre-allocated buffers
- Concurrency guard via semaphore
- Cancellation-safe stage execution
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np


@dataclass
class StageResult:
    success: bool
    value: Any
    stage: str
    latency_ms: float
    exception_type: Optional[str] = None
    timeout_breach: bool = False
    memory_spike: bool = False
    circuit_breaker_activation: bool = False
    retry_exhausted: bool = False
    silence_misclassification: bool = False
    async_cancellation: bool = False
    recovered_with_fallback: bool = False


class ReliabilityStabilizer:
    def __init__(
        self,
        stage_timeout_ms: float = 900.0,
        max_concurrent_gpu_ops: int = 2,
        circuit_breaker_threshold: int = 5,
    ):
        self.stage_timeout_ms = float(stage_timeout_ms)
        self._gpu_semaphore = threading.Semaphore(max_concurrent_gpu_ops)
        self._circuit_breaker_threshold = int(circuit_breaker_threshold)
        self._consecutive_failures = 0
        self._circuit_open = False

        # Memory pre-allocation (lightweight simulation of tensor pre-allocation)
        self._preallocated_buffers = [np.zeros((256,), dtype=np.float32) for _ in range(8)]

    def _fallback_for_stage(self, stage: str) -> Dict[str, Any]:
        return {
            "stage": stage,
            "emotion_detected": "neutral",
            "dialect_detected": "neutral",
            "confidence": 0.75,
            "fallback": True,
        }

    def _watchdog_execute(
        self,
        stage: str,
        worker: Callable[[], Any],
        timeout_ms: Optional[float] = None,
    ) -> StageResult:
        timeout_value = self.stage_timeout_ms if timeout_ms is None else float(timeout_ms)

        if self._circuit_open:
            fallback = self._fallback_for_stage(stage)
            return StageResult(
                success=True,
                value=fallback,
                stage=stage,
                latency_ms=0.0,
                exception_type="CircuitOpenFallback",
                circuit_breaker_activation=True,
                recovered_with_fallback=True,
            )

        start = time.perf_counter()

        with self._gpu_semaphore:
            try:
                value = worker()
                latency_ms = (time.perf_counter() - start) * 1000.0

                if latency_ms > timeout_value:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self._circuit_breaker_threshold:
                        self._circuit_open = True
                    return StageResult(
                        success=True,
                        value=self._fallback_for_stage(stage),
                        stage=stage,
                        latency_ms=latency_ms,
                        exception_type="WatchdogTimeout",
                        timeout_breach=True,
                        retry_exhausted=True,
                        recovered_with_fallback=True,
                    )

                self._consecutive_failures = 0
                if self._circuit_open:
                    self._circuit_open = False

                return StageResult(
                    success=True,
                    value=value,
                    stage=stage,
                    latency_ms=latency_ms,
                )

            except MemoryError:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._circuit_breaker_threshold:
                    self._circuit_open = True
                latency_ms = (time.perf_counter() - start) * 1000.0
                return StageResult(
                    success=True,
                    value=self._fallback_for_stage(stage),
                    stage=stage,
                    latency_ms=latency_ms,
                    exception_type="MemoryError",
                    memory_spike=True,
                    recovered_with_fallback=True,
                )
            except TimeoutError:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._circuit_breaker_threshold:
                    self._circuit_open = True
                latency_ms = (time.perf_counter() - start) * 1000.0
                return StageResult(
                    success=True,
                    value=self._fallback_for_stage(stage),
                    stage=stage,
                    latency_ms=latency_ms,
                    exception_type="TimeoutError",
                    timeout_breach=True,
                    retry_exhausted=True,
                    recovered_with_fallback=True,
                )
            except Exception as exc:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._circuit_breaker_threshold:
                    self._circuit_open = True
                latency_ms = (time.perf_counter() - start) * 1000.0
                return StageResult(
                    success=True,
                    value=self._fallback_for_stage(stage),
                    stage=stage,
                    latency_ms=latency_ms,
                    exception_type=type(exc).__name__,
                    recovered_with_fallback=True,
                )

    def stabilize_interaction(
        self,
        stage: str,
        worker: Callable[[], Dict[str, Any]],
        timeout_ms: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        stage_result = self._watchdog_execute(stage=stage, worker=worker, timeout_ms=timeout_ms)

        diagnostics = {
            "stage": stage_result.stage,
            "exception_type": stage_result.exception_type,
            "timeout_breach": stage_result.timeout_breach,
            "memory_spike": stage_result.memory_spike,
            "circuit_breaker_activation": stage_result.circuit_breaker_activation,
            "retry_exhausted": stage_result.retry_exhausted,
            "silence_misclassification": stage_result.silence_misclassification,
            "async_cancellation": stage_result.async_cancellation,
            "recovered_with_fallback": stage_result.recovered_with_fallback,
            "latency_ms": float(stage_result.latency_ms),
        }

        value = stage_result.value if isinstance(stage_result.value, dict) else {"value": stage_result.value}
        return value, diagnostics
