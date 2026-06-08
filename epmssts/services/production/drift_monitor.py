from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class DriftReport:
    emotion_distribution_drift: float
    dialect_distribution_drift: float
    dialect_shift_detected: bool
    confidence_decay: bool
    embedding_norm_drift: float

    def to_dict(self) -> dict:
        return {
            "emotion_distribution_drift": float(self.emotion_distribution_drift),
            "dialect_distribution_drift": float(self.dialect_distribution_drift),
            "dialect_shift_detected": bool(self.dialect_shift_detected),
            "confidence_decay": bool(self.confidence_decay),
            "embedding_norm_drift": float(self.embedding_norm_drift),
        }


class DriftMonitor:
    def __init__(
        self,
        baseline_size: int = 200,
        window_size: int = 200,
        kl_threshold: float = 0.25,
        psi_threshold: float = 0.20,
        confidence_drop_threshold: float = 0.12,
        embedding_norm_drift_threshold: float = 0.25,
    ) -> None:
        self.baseline_size = baseline_size
        self.window_size = window_size
        self.kl_threshold = kl_threshold
        self.psi_threshold = psi_threshold
        self.confidence_drop_threshold = confidence_drop_threshold
        self.embedding_norm_drift_threshold = embedding_norm_drift_threshold

        self._baseline: List[dict] = []
        self._window: List[dict] = []

    def add_sample(
        self,
        emotion: str,
        dialect: str,
        confidence: float,
        embedding_norm: float,
    ) -> None:
        record = {
            "emotion": emotion,
            "dialect": dialect,
            "confidence": float(confidence),
            "embedding_norm": float(embedding_norm),
        }

        if len(self._baseline) < self.baseline_size:
            self._baseline.append(record)
        else:
            self._window.append(record)
            if len(self._window) > self.window_size:
                self._window.pop(0)

    @staticmethod
    def _distribution(items: List[str]) -> Dict[str, float]:
        if not items:
            return {}
        counts = Counter(items)
        total = max(1, sum(counts.values()))
        return {key: value / total for key, value in counts.items()}

    @staticmethod
    def _kl_divergence(p: Dict[str, float], q: Dict[str, float], eps: float = 1e-8) -> float:
        all_keys = set(p.keys()) | set(q.keys())
        kl = 0.0
        for key in all_keys:
            pv = max(eps, p.get(key, 0.0))
            qv = max(eps, q.get(key, 0.0))
            kl += pv * np.log(pv / qv)
        return float(kl)

    @staticmethod
    def _psi(expected: Dict[str, float], actual: Dict[str, float], eps: float = 1e-8) -> float:
        all_keys = set(expected.keys()) | set(actual.keys())
        value = 0.0
        for key in all_keys:
            e = max(eps, expected.get(key, 0.0))
            a = max(eps, actual.get(key, 0.0))
            value += (a - e) * np.log(a / e)
        return float(value)

    def report(self) -> DriftReport:
        if len(self._baseline) < self.baseline_size or len(self._window) < max(20, self.window_size // 4):
            return DriftReport(
                emotion_distribution_drift=0.0,
                dialect_distribution_drift=0.0,
                dialect_shift_detected=False,
                confidence_decay=False,
                embedding_norm_drift=0.0,
            )

        base_emotions = [row["emotion"] for row in self._baseline]
        win_emotions = [row["emotion"] for row in self._window]
        base_dialects = [row["dialect"] for row in self._baseline]
        win_dialects = [row["dialect"] for row in self._window]

        base_em_dist = self._distribution(base_emotions)
        win_em_dist = self._distribution(win_emotions)
        base_di_dist = self._distribution(base_dialects)
        win_di_dist = self._distribution(win_dialects)

        emotion_kl = self._kl_divergence(base_em_dist, win_em_dist)
        dialect_psi = self._psi(base_di_dist, win_di_dist)

        base_conf = float(np.mean([row["confidence"] for row in self._baseline]))
        win_conf = float(np.mean([row["confidence"] for row in self._window]))
        confidence_decay = (base_conf - win_conf) > self.confidence_drop_threshold

        base_norm = float(np.mean([row["embedding_norm"] for row in self._baseline]))
        win_norm = float(np.mean([row["embedding_norm"] for row in self._window]))
        embedding_norm_drift = abs(base_norm - win_norm)

        dialect_shift_detected = dialect_psi > self.psi_threshold or emotion_kl > self.kl_threshold

        return DriftReport(
            emotion_distribution_drift=emotion_kl,
            dialect_distribution_drift=dialect_psi,
            dialect_shift_detected=dialect_shift_detected,
            confidence_decay=confidence_decay,
            embedding_norm_drift=embedding_norm_drift,
        )
