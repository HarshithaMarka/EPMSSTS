from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import librosa

from epmssts.services.stt.audio_handler import compute_audio_metrics


@dataclass
class EdgeDefenseResult:
    valid: bool
    status: str
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        payload = {"status": self.status}
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


class EdgeCaseDefenseSystem:
    def __init__(
        self,
        min_speech_ratio: float = 0.05,
        max_clipped_ratio: float = 0.1,
        max_peak: float = 0.995,
        max_spectral_flatness: float = 0.75,
    ) -> None:
        self.min_speech_ratio = min_speech_ratio
        self.max_clipped_ratio = max_clipped_ratio
        self.max_peak = max_peak
        self.max_spectral_flatness = max_spectral_flatness

    def validate_audio(self, audio: np.ndarray, sample_rate: int) -> EdgeDefenseResult:
        if audio.size == 0:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="empty_audio")

        metrics = compute_audio_metrics(audio, sample_rate)
        if metrics.get("speech_ratio", 0.0) < self.min_speech_ratio:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="insufficient_speech_ratio")
        if metrics.get("clipped_ratio", 0.0) > self.max_clipped_ratio:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="clipped_audio")

        peak = float(np.max(np.abs(audio)))
        if peak > self.max_peak:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="over_amplified_input")

        flatness = float(np.mean(librosa.feature.spectral_flatness(y=audio)))
        if flatness > self.max_spectral_flatness:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="adversarial_audio_pattern")

        return EdgeDefenseResult(valid=True, status="ok")

    def validate_transcript(self, transcript: str) -> EdgeDefenseResult:
        if not transcript or not transcript.strip():
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="empty_stt_output")
        return EdgeDefenseResult(valid=True, status="ok")

    def validate_language(self, detected_language: str) -> EdgeDefenseResult:
        if detected_language and detected_language.lower() not in {"te", "telugu"}:
            return EdgeDefenseResult(valid=False, status="invalid_audio", reason="non_telugu_speech")
        return EdgeDefenseResult(valid=True, status="ok")
