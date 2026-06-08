from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List

import numpy as np


@dataclass
class DriftSnapshot:
    distribution: Dict[str, float]
    mean_entropy: float
    mean_confidence: float
    alerts: List[str]


class DialectDriftMonitor:
    def __init__(self, window_size: int = 500):
        self.window_size = window_size
        self.predictions: Deque[int] = deque(maxlen=window_size)
        self.probabilities: Deque[np.ndarray] = deque(maxlen=window_size)

    @staticmethod
    def _entropy(prob: np.ndarray) -> float:
        p = np.clip(prob, 1e-8, 1.0)
        return float(-(p * np.log(p)).sum())

    def update(self, predicted_class: int, class_probabilities: np.ndarray) -> DriftSnapshot:
        self.predictions.append(predicted_class)
        self.probabilities.append(class_probabilities.astype(np.float32))
        return self.snapshot()

    def snapshot(self) -> DriftSnapshot:
        if len(self.predictions) == 0:
            return DriftSnapshot(
                distribution={"andhra": 0.0, "telangana": 0.0},
                mean_entropy=0.0,
                mean_confidence=0.0,
                alerts=["insufficient_data"],
            )

        preds = np.array(self.predictions)
        probs = np.stack(list(self.probabilities), axis=0)

        andhra_ratio = float((preds == 0).mean())
        telangana_ratio = float((preds == 1).mean())
        entropies = np.array([self._entropy(p) for p in probs], dtype=np.float32)
        confidences = probs.max(axis=1)

        alerts: List[str] = []
        if andhra_ratio > 0.70:
            alerts.append("class_imbalance_alert:andhra_over_70")
        if telangana_ratio > 0.70:
            alerts.append("class_imbalance_alert:telangana_over_70")

        mean_entropy = float(entropies.mean())
        mean_confidence = float(confidences.mean())

        if mean_entropy < 0.20:
            alerts.append("confidence_collapse_alert:low_entropy")
        if mean_confidence > 0.95:
            alerts.append("confidence_collapse_alert:overconfident")

        return DriftSnapshot(
            distribution={"andhra": andhra_ratio, "telangana": telangana_ratio},
            mean_entropy=mean_entropy,
            mean_confidence=mean_confidence,
            alerts=alerts,
        )
