from __future__ import annotations

from collections import Counter as DictCounter
from dataclasses import dataclass
from time import perf_counter
from typing import Dict

try:
    from prometheus_client import Counter, Gauge, Histogram

    PROM_AVAILABLE = True
except Exception:
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    PROM_AVAILABLE = False


@dataclass
class ModuleTimer:
    metrics: "ProductionMetrics"
    module: str
    _start: float

    def stop(self, success: bool = True) -> float:
        elapsed_ms = (perf_counter() - self._start) * 1000.0
        self.metrics.record_latency(self.module, elapsed_ms)
        if not success:
            self.metrics.record_failure(self.module)
        return elapsed_ms


class ProductionMetrics:
    def __init__(self) -> None:
        self.retry_counts: DictCounter[str] = DictCounter()
        self.emotion_histogram: DictCounter[str] = DictCounter()
        self.dialect_confusion: DictCounter[tuple[str, str]] = DictCounter()

        if PROM_AVAILABLE:
            self.module_latency = Histogram(
                "epmssts_module_latency_ms",
                "Latency per module in ms",
                ["module"],
                buckets=(10, 25, 50, 100, 250, 500, 1000, 1500, 2000, 5000),
            )
            self.module_failures = Counter(
                "epmssts_module_failures_total",
                "Failure count per module",
                ["module"],
            )
            self.module_retries = Counter(
                "epmssts_module_retries_total",
                "Retry count per module",
                ["module"],
            )
            self.emotion_distribution = Gauge(
                "epmssts_emotion_distribution",
                "Emotion distribution histogram",
                ["emotion"],
            )
            self.dialect_confusion_metric = Gauge(
                "epmssts_dialect_confusion_count",
                "Dialect confusion matrix over time",
                ["true_label", "pred_label"],
            )
        else:
            self.module_latency = None
            self.module_failures = None
            self.module_retries = None
            self.emotion_distribution = None
            self.dialect_confusion_metric = None

    def timer(self, module: str) -> ModuleTimer:
        return ModuleTimer(metrics=self, module=module, _start=perf_counter())

    def record_latency(self, module: str, latency_ms: float) -> None:
        if self.module_latency is not None:
            self.module_latency.labels(module=module).observe(latency_ms)

    def record_failure(self, module: str) -> None:
        if self.module_failures is not None:
            self.module_failures.labels(module=module).inc()

    def record_retry(self, module: str) -> None:
        self.retry_counts[module] += 1
        if self.module_retries is not None:
            self.module_retries.labels(module=module).inc()

    def record_emotion(self, emotion: str) -> None:
        self.emotion_histogram[emotion] += 1
        if self.emotion_distribution is not None:
            total = max(1, sum(self.emotion_histogram.values()))
            for key, value in self.emotion_histogram.items():
                self.emotion_distribution.labels(emotion=key).set(value / total)

    def record_dialect_prediction(self, true_label: str, pred_label: str) -> None:
        self.dialect_confusion[(true_label, pred_label)] += 1
        if self.dialect_confusion_metric is not None:
            self.dialect_confusion_metric.labels(true_label=true_label, pred_label=pred_label).set(
                self.dialect_confusion[(true_label, pred_label)]
            )

    def retry_rate(self) -> Dict[str, float]:
        total = sum(self.retry_counts.values())
        if total <= 0:
            return {}
        return {module: count / total for module, count in self.retry_counts.items()}
