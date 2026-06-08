from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List
import json
import math

import numpy as np


@dataclass
class CalibrationResult:
    temperature: float
    ece: float
    recalibrated: bool


class ConfidenceCalibrator:
    def __init__(
        self,
        artifact_path: Path,
        initial_temperature: float = 1.0,
        recompute_days: int = 30,
    ) -> None:
        self.artifact_path = artifact_path
        self.temperature = float(initial_temperature)
        self.recompute_days = recompute_days
        self.last_recompute: datetime | None = None
        self._load()

    def _load(self) -> None:
        if not self.artifact_path.exists():
            return
        payload = json.loads(self.artifact_path.read_text(encoding="utf-8"))
        self.temperature = float(payload.get("temperature", self.temperature))
        timestamp = payload.get("last_recompute")
        if timestamp:
            self.last_recompute = datetime.fromisoformat(timestamp)

    def save(self) -> None:
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "temperature": self.temperature,
            "last_recompute": (self.last_recompute or datetime.now(timezone.utc)).isoformat(),
        }
        self.artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def calibrate_probability(self, confidence: float) -> float:
        confidence = min(1.0, max(1e-6, float(confidence)))
        logit = math.log(confidence / (1.0 - confidence))
        scaled = logit / max(1e-6, self.temperature)
        return float(1.0 / (1.0 + math.exp(-scaled)))

    @staticmethod
    def expected_calibration_error(
        y_true: List[int],
        y_prob: List[float],
        bins: int = 10,
    ) -> float:
        if not y_true or not y_prob or len(y_true) != len(y_prob):
            return 0.0

        y_true_np = np.asarray(y_true, dtype=np.float32)
        y_prob_np = np.asarray(y_prob, dtype=np.float32)

        bin_edges = np.linspace(0.0, 1.0, bins + 1)
        ece = 0.0
        n = y_true_np.shape[0]

        for i in range(bins):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            mask = (y_prob_np >= lo) & (y_prob_np < hi if i < bins - 1 else y_prob_np <= hi)
            if not np.any(mask):
                continue
            bin_conf = float(np.mean(y_prob_np[mask]))
            bin_acc = float(np.mean(y_true_np[mask]))
            weight = float(np.sum(mask)) / float(n)
            ece += abs(bin_acc - bin_conf) * weight

        return float(ece)

    def should_recompute(self, dataset_size: int) -> bool:
        if dataset_size < 200:
            return False
        if self.last_recompute is None:
            return True
        now = datetime.now(timezone.utc)
        return now - self.last_recompute >= timedelta(days=self.recompute_days)

    def maybe_recompute_from_dataset(self, dataset_path: Path) -> CalibrationResult:
        if not dataset_path.exists():
            return CalibrationResult(temperature=self.temperature, ece=0.0, recalibrated=False)

        rows = [
            json.loads(line)
            for line in dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        y_true = [int(row["correct"]) for row in rows if "correct" in row and "confidence" in row]
        y_prob = [float(row["confidence"]) for row in rows if "correct" in row and "confidence" in row]

        if not self.should_recompute(len(y_true)):
            ece = self.expected_calibration_error(y_true, [self.calibrate_probability(x) for x in y_prob])
            return CalibrationResult(temperature=self.temperature, ece=ece, recalibrated=False)

        return self.recompute_temperature(y_true, y_prob)

    def recompute_temperature(self, y_true: List[int], y_prob: List[float]) -> CalibrationResult:
        if not y_true or not y_prob:
            return CalibrationResult(temperature=self.temperature, ece=0.0, recalibrated=False)

        candidate_grid = np.linspace(0.7, 2.5, 37)
        best_temp = self.temperature
        best_ece = float("inf")

        for temp in candidate_grid:
            calibrated = [self._calibrate_with_temp(prob, float(temp)) for prob in y_prob]
            ece = self.expected_calibration_error(y_true, calibrated)
            if ece < best_ece:
                best_ece = ece
                best_temp = float(temp)

        self.temperature = best_temp
        self.last_recompute = datetime.now(timezone.utc)
        self.save()
        return CalibrationResult(temperature=self.temperature, ece=float(best_ece), recalibrated=True)

    @staticmethod
    def _calibrate_with_temp(prob: float, temperature: float) -> float:
        prob = min(1.0, max(1e-6, float(prob)))
        logit = math.log(prob / (1.0 - prob))
        scaled = logit / max(1e-6, temperature)
        return float(1.0 / (1.0 + math.exp(-scaled)))
