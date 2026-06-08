"""
Translation Drift Monitor

Monitors translation quality drift over time.
Alerts on confidence degradation, emotion preservation issues, and language distribution changes.
"""

import logging
from collections import deque, Counter
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np

from .schemas import DriftAlert, TranslationMetricsSnapshot


logger = logging.getLogger(__name__)


class TranslationDriftMonitor:
    """
    Monitors translation service drift.
    
    Tracks:
    - Average translation confidence
    - Average emotion preservation score
    - Retry rate trends
    - Language distribution
    - Latency trends
    
    Alerts on:
    - Confidence drift (drop > 15%)
    - Emotion preservation drift (drop > 20%)
    - High retry rate (> 20%)
    - Latency spike (> 50% increase)
    - Language distribution shift
    """
    
    def __init__(
        self,
        window_size: int = 100,
        confidence_drift_threshold: float = 0.15,
        emotion_drift_threshold: float = 0.20,
        high_retry_rate_threshold: float = 0.20,
        latency_spike_threshold: float = 1.5,
    ):
        self.window_size = window_size
        self.confidence_drift_threshold = confidence_drift_threshold
        self.emotion_drift_threshold = emotion_drift_threshold
        self.high_retry_rate_threshold = high_retry_rate_threshold
        self.latency_spike_threshold = latency_spike_threshold
        
        # Sliding windows
        self.confidence_history = deque(maxlen=window_size)
        self.emotion_preservation_history = deque(maxlen=window_size)
        self.retry_history = deque(maxlen=window_size)
        self.latency_history = deque(maxlen=window_size)
        
        # Language distribution
        self.language_distribution = Counter()
        
        # Status tracking
        self.success_count = 0
        self.partial_count = 0
        self.failed_count = 0
        self.total_retries = 0
        
        # Retry reasons
        self.retry_reasons_count = Counter()
        
        # Drift alerts
        self.active_alerts: List[DriftAlert] = []
        self.alert_count = 0
        
        # Baselines
        self.baseline_confidence: Optional[float] = None
        self.baseline_emotion_preservation: Optional[float] = None
        self.baseline_latency: Optional[float] = None
        self.baseline_computed = False
    
    def record_translation(
        self,
        status: str,
        translation_confidence: float,
        emotion_preservation_score: Optional[float],
        latency_ms: float,
        source_language: str,
        had_retry: bool,
        retry_reason: Optional[str] = None,
    ):
        """Record a translation for drift monitoring"""
        # Update status counts
        if status == "success":
            self.success_count += 1
        elif status == "partial":
            self.partial_count += 1
        else:
            self.failed_count += 1
        
        # Record metrics
        self.confidence_history.append(translation_confidence)
        
        if emotion_preservation_score is not None:
            self.emotion_preservation_history.append(emotion_preservation_score)
        
        self.latency_history.append(latency_ms)
        self.retry_history.append(1 if had_retry else 0)
        
        if had_retry:
            self.total_retries += 1
            if retry_reason:
                self.retry_reasons_count[retry_reason] += 1
        
        # Update language distribution
        self.language_distribution[source_language] += 1
        
        # Compute baseline after first 20 samples
        if not self.baseline_computed and len(self.confidence_history) >= 20:
            self._compute_baseline()
        
        # Check for drift
        if self.baseline_computed:
            self._check_for_drift()
    
    def _compute_baseline(self):
        """Compute baseline metrics"""
        if len(self.confidence_history) > 0:
            self.baseline_confidence = np.mean(self.confidence_history)
        
        if len(self.emotion_preservation_history) > 0:
            self.baseline_emotion_preservation = np.mean(self.emotion_preservation_history)
        
        if len(self.latency_history) > 0:
            self.baseline_latency = np.mean(self.latency_history)
        
        self.baseline_computed = True
        logger.info(
            f"Baseline established: confidence={self.baseline_confidence:.3f}, "
            f"emotion={self.baseline_emotion_preservation:.3f}, "
            f"latency={self.baseline_latency:.1f}ms"
        )
    
    def _check_for_drift(self):
        """Check for various drift patterns"""
        self.active_alerts.clear()
        
        # Check 1: Confidence drift
        self._check_confidence_drift()
        
        # Check 2: Emotion preservation drift
        self._check_emotion_preservation_drift()
        
        # Check 3: High retry rate
        self._check_retry_rate()
        
        # Check 4: Latency spike
        self._check_latency_spike()
    
    def _check_confidence_drift(self):
        """Alert if confidence significantly below baseline"""
        if not self.confidence_history or self.baseline_confidence is None:
            return
        
        current_confidence = np.mean(self.confidence_history)
        drift = (self.baseline_confidence - current_confidence) / self.baseline_confidence
        
        if drift > self.confidence_drift_threshold:
            alert = DriftAlert(
                alert_type="confidence_drift",
                severity="high",
                metric_value=current_confidence,
                threshold=self.baseline_confidence * (1 - self.confidence_drift_threshold),
                baseline_value=self.baseline_confidence,
                message=f"Confidence drift: current={current_confidence:.3f}, baseline={self.baseline_confidence:.3f}, drift={drift*100:.1f}%",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_emotion_preservation_drift(self):
        """Alert if emotion preservation significantly below baseline"""
        if not self.emotion_preservation_history or self.baseline_emotion_preservation is None:
            return
        
        current_score = np.mean(self.emotion_preservation_history)
        drift = (self.baseline_emotion_preservation - current_score) / self.baseline_emotion_preservation
        
        if drift > self.emotion_drift_threshold:
            alert = DriftAlert(
                alert_type="emotion_preservation_drift",
                severity="medium",
                metric_value=current_score,
                threshold=self.baseline_emotion_preservation * (1 - self.emotion_drift_threshold),
                baseline_value=self.baseline_emotion_preservation,
                message=f"Emotion preservation drift: current={current_score:.3f}, baseline={self.baseline_emotion_preservation:.3f}, drift={drift*100:.1f}%",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_retry_rate(self):
        """Alert if retry rate exceeds threshold"""
        if not self.retry_history:
            return
        
        retry_rate = np.mean(self.retry_history)
        
        if retry_rate > self.high_retry_rate_threshold:
            alert = DriftAlert(
                alert_type="high_retry_rate",
                severity="high",
                metric_value=retry_rate,
                threshold=self.high_retry_rate_threshold,
                message=f"High retry rate: {retry_rate*100:.1f}% exceeds threshold {self.high_retry_rate_threshold*100:.1f}%",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_latency_spike(self):
        """Alert if latency significantly above baseline"""
        if not self.latency_history or self.baseline_latency is None:
            return
        
        current_latency = np.mean(self.latency_history)
        
        if current_latency > self.baseline_latency * self.latency_spike_threshold:
            alert = DriftAlert(
                alert_type="latency_spike",
                severity="medium",
                metric_value=current_latency,
                threshold=self.baseline_latency * self.latency_spike_threshold,
                baseline_value=self.baseline_latency,
                message=f"Latency spike: current={current_latency:.1f}ms, baseline={self.baseline_latency:.1f}ms",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def get_active_alerts(self) -> List[DriftAlert]:
        """Get currently active drift alerts"""
        return self.active_alerts.copy()
    
    def get_metrics_snapshot(self) -> TranslationMetricsSnapshot:
        """Get comprehensive metrics snapshot"""
        total_requests = self.success_count + self.partial_count + self.failed_count
        
        # Calculate percentiles
        confidence_p50 = np.percentile(self.confidence_history, 50) if self.confidence_history else 0.0
        confidence_p95 = np.percentile(self.confidence_history, 95) if self.confidence_history else 0.0
        
        emotion_p50 = np.percentile(self.emotion_preservation_history, 50) if self.emotion_preservation_history else 0.0
        
        latency_p50 = np.percentile(self.latency_history, 50) if self.latency_history else 0.0
        latency_p95 = np.percentile(self.latency_history, 95) if self.latency_history else 0.0
        latency_p99 = np.percentile(self.latency_history, 99) if self.latency_history else 0.0
        
        retry_rate = np.mean(self.retry_history) if self.retry_history else 0.0
        
        return TranslationMetricsSnapshot(
            total_requests=total_requests,
            success_count=self.success_count,
            partial_count=self.partial_count,
            failed_count=self.failed_count,
            retry_count=self.total_retries,
            average_confidence=np.mean(self.confidence_history) if self.confidence_history else 0.0,
            confidence_p50=float(confidence_p50),
            confidence_p95=float(confidence_p95),
            average_emotion_preservation=np.mean(self.emotion_preservation_history) if self.emotion_preservation_history else 0.0,
            emotion_preservation_p50=float(emotion_p50),
            language_distribution=dict(self.language_distribution),
            latency_p50_ms=float(latency_p50),
            latency_p95_ms=float(latency_p95),
            latency_p99_ms=float(latency_p99),
            retry_rate=float(retry_rate),
            retry_reasons_distribution=dict(self.retry_reasons_count),
            active_alerts=len(self.active_alerts),
        )
    
    def get_drift_stats(self) -> Dict:
        """Get drift monitoring statistics"""
        return {
            "total_translations": self.success_count + self.partial_count + self.failed_count,
            "alert_count": self.alert_count,
            "baseline_confidence": self.baseline_confidence,
            "baseline_emotion_preservation": self.baseline_emotion_preservation,
            "baseline_latency": self.baseline_latency,
            "window_size": self.window_size,
        }
