from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass
class NaturalizerConfig:
    enabled: bool = True
    breath_level: float = 0.006
    jitter_strength: float = 0.008
    timing_variance_strength: float = 0.006
    fade_ms: float = 12.0
    random_seed: int = 1234


class Naturalizer:
    def __init__(self, config: Optional[NaturalizerConfig] = None):
        self.config = config or NaturalizerConfig()
        self._rng = np.random.default_rng(self.config.random_seed)

    def process(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        audio = np.asarray(waveform, dtype=np.float32)
        if not self.config.enabled or audio.size == 0:
            return audio

        out = audio.copy()
        out = self._apply_timing_variance(out)
        out = self._apply_micro_pitch_jitter(out)
        out = self._inject_breath_noise(out, sample_rate)
        out = self._apply_fades(out, sample_rate)

        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 0.98:
            out = out * (0.98 / peak)

        return out.astype(np.float32)

    def _apply_timing_variance(self, waveform: np.ndarray) -> np.ndarray:
        n = waveform.shape[0]
        x = np.arange(n, dtype=np.float32)
        drift = self._rng.normal(0.0, self.config.timing_variance_strength, size=n).astype(np.float32)
        drift = np.cumsum(drift) / np.sqrt(n)
        drift = np.clip(drift, -0.02, 0.02)

        x_warp = np.clip(x + drift * n, 0, n - 1)
        warped = np.interp(x, x_warp, waveform).astype(np.float32)
        return warped

    def _apply_micro_pitch_jitter(self, waveform: np.ndarray) -> np.ndarray:
        n = waveform.shape[0]
        if n < 4:
            return waveform

        x = np.arange(n, dtype=np.float32)
        jitter = self._rng.normal(0.0, self.config.jitter_strength, size=n).astype(np.float32)
        jitter = np.convolve(jitter, np.ones(9, dtype=np.float32) / 9.0, mode="same")
        jitter = np.clip(jitter, -0.009, 0.009)

        phase = np.clip(x + jitter * x, 0, n - 1)
        return np.interp(x, phase, waveform).astype(np.float32)

    def _inject_breath_noise(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        n = waveform.shape[0]
        noise = self._rng.normal(0.0, 1.0, size=n).astype(np.float32)

        sos = butter(2, [100.0 / (sample_rate / 2.0), 1200.0 / (sample_rate / 2.0)], btype="band", output="sos")
        breath = sosfiltfilt(sos, noise).astype(np.float32)

        env = np.abs(waveform)
        env = np.convolve(env, np.ones(401, dtype=np.float32) / 401.0, mode="same")
        inv_env = 1.0 - np.clip(env / (np.max(env) + 1e-6), 0.0, 1.0)

        breath_scaled = self.config.breath_level * inv_env * breath
        return (waveform + breath_scaled).astype(np.float32)

    def _apply_fades(self, waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        fade_samples = int((self.config.fade_ms / 1000.0) * sample_rate)
        fade_samples = max(1, min(fade_samples, waveform.shape[0] // 2))

        envelope = np.ones_like(waveform, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        envelope[:fade_samples] *= fade_in
        envelope[-fade_samples:] *= fade_out

        return (waveform * envelope).astype(np.float32)
