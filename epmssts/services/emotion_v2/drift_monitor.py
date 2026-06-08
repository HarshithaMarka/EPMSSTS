"""
Drift Monitoring

Tracks emotion distribution shifts, entropy spikes, and class imbalances.
Alerts on neutral collapse, class bias, and confidence degradation.
"""

import logging
from collections import deque, Counter
from typing import Dict, List, Optional
from datetime import datetime

from .schemas import DriftAlert, MetricsSnapshot, EmotionLabel


logger = logging.getLogger(__name__)


class DriftMonitor:
    """
    Monitors emotion prediction drift over time.
    
    Tracks:
    - Emotion label distribution
    - Average entropy trends
    - Class imbalance (neutral collapse)
    - Confidence degradation
    
    Alerts on:
    - Neutral rate > 70% (neutral collapse)
    - Entropy spike (>50% increase)
    - Class imbalance (single class > 80%)
    - Confidence drop (<30% average)
    """
    
    def __init__(
        self,
        window_size: int = 100,
        neutral_collapse_threshold: float = 0.70,
        class_imbalance_threshold: float = 0.80,
        entropy_spike_threshold: float = 1.5,
        confidence_floor: float = 0.30,
    ):
        self.window_size = window_size
        self.neutral_collapse_threshold = neutral_collapse_threshold
        self.class_imbalance_threshold = class_imbalance_threshold
        self.entropy_spike_threshold = entropy_spike_threshold
        self.confidence_floor = confidence_floor
        
        # Sliding windows for tracking
        self.emotion_history = deque(maxlen=window_size)
        self.entropy_history = deque(maxlen=window_size)
        self.confidence_history = deque(maxlen=window_size)
        self.uncertainty_flag_history = deque(maxlen=window_size)
        
        # Drift alerts
        self.active_alerts: List[DriftAlert] = []
        
        # Statistics
        self.total_predictions = 0
        self.alert_count = 0
        
        # Baseline metrics (computed from first N samples)
        self.baseline_entropy: Optional[float] = None
        self.baseline_confidence: Optional[float] = None
        self.baseline_computed = False
    
    def record_prediction(
        self,
        predicted_label: str,
        entropy: float,
        confidence: float,
        uncertainty_flag: bool,
    ):
        """Record a prediction for drift monitoring"""
        self.emotion_history.append(predicted_label)
        self.entropy_history.append(entropy)
        self.confidence_history.append(confidence)
        self.uncertainty_flag_history.append(uncertainty_flag)
        
        self.total_predictions += 1
        
        # Compute baseline after first 20 predictions
        if not self.baseline_computed and len(self.entropy_history) >= 20:
            self._compute_baseline()
        
        # Check for drift (only after baseline established)
        if self.baseline_computed:
            self._check_for_drift()
    
    def _compute_baseline(self):
        """Compute baseline metrics from initial predictions"""
        if len(self.entropy_history) > 0:
            self.baseline_entropy = sum(self.entropy_history) / len(self.entropy_history)
        
        if len(self.confidence_history) > 0:
            self.baseline_confidence = sum(self.confidence_history) / len(
                self.confidence_history
            )
        
        self.baseline_computed = True
        logger.info(
            f"Baseline established: entropy={self.baseline_entropy:.3f}, "
            f"confidence={self.baseline_confidence:.3f}"
        )
    
    def _check_for_drift(self):
        """Check for various drift patterns"""
        self.active_alerts.clear()
        
        # Check 1: Neutral collapse
        self._check_neutral_collapse()
        
        # Check 2: Class imbalance
        self._check_class_imbalance()
        
        # Check 3: Entropy spike
        self._check_entropy_spike()
        
        # Check 4: Confidence degradation
        self._check_confidence_degradation()
        
        # Check 5: High uncertainty rate
        self._check_uncertainty_rate()
    
    def _check_neutral_collapse(self):
        """Alert if neutral predictions exceed threshold"""
        if not self.emotion_history:
            return
        
        emotion_counts = Counter(self.emotion_history)
        neutral_count = emotion_counts.get("neutral", 0)
        neutral_rate = neutral_count / len(self.emotion_history)
        
        if neutral_rate > self.neutral_collapse_threshold:
            alert = DriftAlert(
                alert_type="neutral_collapse",
                severity="high",
                metric_value=neutral_rate,
                threshold=self.neutral_collapse_threshold,
                message=f"Neutral collapse detected: {neutral_rate*100:.1f}% of predictions are neutral",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_class_imbalance(self):
        """Alert if any single class dominates"""
        if not self.emotion_history:
            return
        
        emotion_counts = Counter(self.emotion_history)
        total = len(self.emotion_history)
        
        for emotion, count in emotion_counts.items():
            rate = count / total
            if rate > self.class_imbalance_threshold:
                alert = DriftAlert(
                    alert_type="class_imbalance",
                    severity="medium",
                    metric_value=rate,
                    threshold=self.class_imbalance_threshold,
                    message=f"Class imbalance: '{emotion}' accounts for {rate*100:.1f}% of predictions",
                    timestamp=datetime.now().isoformat(),
                )
                self.active_alerts.append(alert)
                self.alert_count += 1
                logger.warning(alert.message)
    
    def _check_entropy_spike(self):
        """Alert if entropy significantly exceeds baseline"""
        if not self.entropy_history or self.baseline_entropy is None:
            return
        
        current_entropy = sum(self.entropy_history) / len(self.entropy_history)
        
        if current_entropy > self.baseline_entropy * self.entropy_spike_threshold:
            alert = DriftAlert(
                alert_type="entropy_spike",
                severity="medium",
                metric_value=current_entropy,
                threshold=self.baseline_entropy * self.entropy_spike_threshold,
                message=f"Entropy spike: current={current_entropy:.3f}, baseline={self.baseline_entropy:.3f}",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_confidence_degradation(self):
        """Alert if average confidence drops below floor"""
        if not self.confidence_history:
            return
        
        current_confidence = sum(self.confidence_history) / len(self.confidence_history)
        
        if current_confidence < self.confidence_floor:
            alert = DriftAlert(
                alert_type="confidence_drop",
                severity="high",
                metric_value=current_confidence,
                threshold=self.confidence_floor,
                message=f"Confidence degradation: average={current_confidence:.3f}",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def _check_uncertainty_rate(self):
        """Alert if high uncertainty rate"""
        if not self.uncertainty_flag_history:
            return
        
        uncertainty_count = sum(1 for flag in self.uncertainty_flag_history if flag)
        uncertainty_rate = uncertainty_count / len(self.uncertainty_flag_history)
        
        if uncertainty_rate > 0.5:  # More than 50% flagged as uncertain
            alert = DriftAlert(
                alert_type="high_uncertainty_rate",
                severity="medium",
                metric_value=uncertainty_rate,
                threshold=0.5,
                message=f"High uncertainty rate: {uncertainty_rate*100:.1f}% of predictions flagged",
                timestamp=datetime.now().isoformat(),
            )
            self.active_alerts.append(alert)
            self.alert_count += 1
            logger.warning(alert.message)
    
    def get_active_alerts(self) -> List[DriftAlert]:
        """Get currently active drift alerts"""
        return self.active_alerts.copy()
    
    def get_metrics_snapshot(self) -> MetricsSnapshot:
        """Get comprehensive metrics snapshot"""
        # Emotion distribution
        emotion_counts = Counter(self.emotion_history)
        total = len(self.emotion_history) if self.emotion_history else 1
        
        emotion_distribution = {
            emotion: count / total for emotion, count in emotion_counts.items()
        }
        
        # Ensure all emotions present
        for emotion in ["angry", "happy", "neutral", "sad"]:
            if emotion not in emotion_distribution:
                emotion_distribution[emotion] = 0.0
        
        # Average entropy
        avg_entropy = (
            sum(self.entropy_history) / len(self.entropy_history)
            if self.entropy_history
            else 0.0
        )
        
        # Average confidence
        avg_confidence = (
            sum(self.confidence_history) / len(self.confidence_history)
            if self.confidence_history
            else 0.0
        )
        
        # Uncertainty rate
        uncertainty_count = sum(1 for flag in self.uncertainty_flag_history if flag)
        uncertainty_rate = (
            uncertainty_count / len(self.uncertainty_flag_history)
            if self.uncertainty_flag_history
            else 0.0
        )
        
        # Latency percentiles (placeholder - would integrate with actual timings)
        latency_p50 = 200.0
        latency_p95 = 450.0
        latency_p99 = 600.0
        
        return MetricsSnapshot(
            total_requests=self.total_predictions,
            emotion_distribution=emotion_distribution,
            average_entropy=avg_entropy,
            average_confidence=avg_confidence,
            uncertainty_rate=uncertainty_rate,
            neutral_rate=emotion_distribution.get("neutral", 0.0),
            active_alerts=len(self.active_alerts),
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
        )
    
    def get_drift_stats(self) -> Dict[str, any]:
        """Get drift monitoring statistics"""
        return {
            "total_predictions": self.total_predictions,
            "alert_count": self.alert_count,
            "alert_rate": (
                self.alert_count / (self.total_predictions / self.window_size)
                if self.total_predictions > 0
                else 0.0
            ),
            "baseline_entropy": self.baseline_entropy,
            "baseline_confidence": self.baseline_confidence,
            "window_size": self.window_size,
        }
