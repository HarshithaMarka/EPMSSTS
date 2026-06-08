"""
Emotion Detection Audio Preprocessing & Calibration.

Adaptive preprocessing to preserve emotional energy patterns while improving
volume invariance. This module intentionally avoids hard emotion overrides and
focuses on signal-quality-aware normalization + feature-level calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
from scipy.signal import butter, sosfilt, stft


@dataclass
class EmotionAudioMetrics:
    """Comprehensive audio metrics for emotion calibration and diagnostics."""

    rms_db: float
    peak_db: float
    peak_amplitude: float
    mean_amplitude: float
    spectral_centroid: float
    zero_crossing_rate: float
    energy_variance: float
    pitch_mean: float
    pitch_variance: float
    raw_rms_db: float
    raw_peak_db: float
    energy_band: str
    dynamic_range: float
    crest_factor: float
    energy_normalized: bool
    energy_level: str

    def to_dict(self) -> Dict[str, float | str | bool]:
        return {
            "rms_db": round(self.rms_db, 2),
            "peak_db": round(self.peak_db, 2),
            "peak_amplitude": round(self.peak_amplitude, 4),
            "mean_amplitude": round(self.mean_amplitude, 4),
            "spectral_centroid": round(self.spectral_centroid, 1),
            "zero_crossing_rate": round(self.zero_crossing_rate, 4),
            "energy_variance": round(self.energy_variance, 6),
            "pitch_mean": round(self.pitch_mean, 2),
            "pitch_variance": round(self.pitch_variance, 2),
            "raw_rms_db": round(self.raw_rms_db, 2),
            "raw_peak_db": round(self.raw_peak_db, 2),
            "energy_band": self.energy_band,
            "dynamic_range": round(self.dynamic_range, 2),
            "crest_factor": round(self.crest_factor, 2),
            "energy_normalized": self.energy_normalized,
            "energy_level": self.energy_level,
        }


class EmotionAudioPreprocessor:
    """
    Preprocess audio for emotion detection.

    Design goals:
    - Preserve natural emotional energy contrast
    - Improve volume invariance via adaptive, capped normalization
    - Keep waveform shape intact (no aggressive stretching)
    - Enable feature-level standardization using log-mel features
    """

    SILENT_THRESHOLD_DBFS = -60.0
    QUIET_THRESHOLD_DBFS = -35.0
    NORMAL_THRESHOLD_DBFS = -25.0
    LOUD_THRESHOLD_DBFS = -15.0

    TARGET_RMS_BY_BAND = {
        "very_low": -24.0,
        "low": -22.0,
        "normal": -20.0,
        "high": -18.0,
    }

    MAX_GAIN_DB_BY_BAND = {
        "very_low": 6.0,
        "low": 10.0,
        "normal": 12.0,
        "high": 12.0,
    }

    METRICS_MAX_SECONDS = 3.0

    def preprocess_for_emotion(
        self,
        audio: np.ndarray,
        sample_rate: int = 16_000,
        target_rms_dbfs: Optional[float] = None,
    ) -> tuple[np.ndarray, EmotionAudioMetrics]:
        """Adaptive preprocessing preserving emotion-specific energy patterns."""
        pre_metrics = self._compute_metrics(audio, sample_rate)

        audio = audio - np.mean(audio)
        audio = self._apply_highpass(audio, sample_rate, cutoff_hz=80.0)

        energy_band = self._classify_energy_band(pre_metrics.rms_db)
        adaptive_target = (
            self.TARGET_RMS_BY_BAND[energy_band]
            if target_rms_dbfs is None
            else target_rms_dbfs
        )

        audio_normalized = self._normalize_rms_adaptive(
            audio,
            target_rms_dbfs=adaptive_target,
            energy_band=energy_band,
        )

        post_metrics = self._compute_metrics(audio_normalized, sample_rate)
        energy_level = self._classify_energy_level(post_metrics.rms_db)

        metrics = EmotionAudioMetrics(
            rms_db=post_metrics.rms_db,
            peak_db=post_metrics.peak_db,
            peak_amplitude=post_metrics.peak_amplitude,
            mean_amplitude=post_metrics.mean_amplitude,
            spectral_centroid=post_metrics.spectral_centroid,
            zero_crossing_rate=post_metrics.zero_crossing_rate,
            energy_variance=post_metrics.energy_variance,
            pitch_mean=post_metrics.pitch_mean,
            pitch_variance=post_metrics.pitch_variance,
            raw_rms_db=pre_metrics.rms_db,
            raw_peak_db=pre_metrics.peak_db,
            energy_band=energy_band,
            dynamic_range=post_metrics.dynamic_range,
            crest_factor=post_metrics.crest_factor,
            energy_normalized=True,
            energy_level=energy_level,
        )

        return audio_normalized.astype(np.float32), metrics

    @staticmethod
    def _apply_highpass(
        audio: np.ndarray,
        sample_rate: int,
        cutoff_hz: float = 80.0,
    ) -> np.ndarray:
        if audio.size == 0:
            return audio

        nyquist = sample_rate / 2.0
        normalized_cutoff = min(max(cutoff_hz / nyquist, 0.001), 0.99)
        sos = butter(2, normalized_cutoff, btype="highpass", output="sos")
        filtered = sosfilt(sos, audio)
        return filtered.astype(np.float32)

    @classmethod
    def _normalize_rms_adaptive(
        cls,
        audio: np.ndarray,
        target_rms_dbfs: float,
        energy_band: str,
    ) -> np.ndarray:
        if audio.size == 0:
            return audio

        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < 1e-8:
            return audio

        rms_db = 20.0 * np.log10(rms + 1e-10)
        gain_db = target_rms_dbfs - rms_db

        max_gain_db = cls.MAX_GAIN_DB_BY_BAND.get(energy_band, 12.0)
        gain_db = float(np.clip(gain_db, -24.0, min(max_gain_db, 12.0)))

        gain_linear = 10 ** (gain_db / 20.0)
        normalized = audio * gain_linear

        # Preserve dynamic envelope: avoid hard clipping. If over-range, scale entire
        # waveform uniformly so temporal amplitude variation is preserved.
        peak_after = float(np.max(np.abs(normalized)))
        if peak_after > 1.0:
            normalized = normalized / (peak_after + 1e-10)

        # numerical safety only
        normalized = np.clip(normalized, -1.0, 1.0)
        return normalized.astype(np.float32)

    @classmethod
    def _compute_metrics(
        cls,
        audio: np.ndarray,
        sample_rate: int,
    ) -> EmotionAudioMetrics:
        if audio.size == 0:
            return EmotionAudioMetrics(
                rms_db=-100.0,
                peak_db=-100.0,
                peak_amplitude=0.0,
                mean_amplitude=0.0,
                spectral_centroid=0.0,
                zero_crossing_rate=0.0,
                energy_variance=0.0,
                pitch_mean=0.0,
                pitch_variance=0.0,
                raw_rms_db=-100.0,
                raw_peak_db=-100.0,
                energy_band="very_low",
                dynamic_range=0.0,
                crest_factor=0.0,
                energy_normalized=False,
                energy_level="silent",
            )

        max_len = int(cls.METRICS_MAX_SECONDS * sample_rate)
        analysis_audio = audio[:max_len] if len(audio) > max_len else audio

        rms = float(np.sqrt(np.mean(np.square(analysis_audio))))
        peak = float(np.max(np.abs(analysis_audio)))
        mean_abs = float(np.mean(np.abs(analysis_audio)))
        rms_db = 20.0 * np.log10(rms + 1e-10)
        peak_db = 20.0 * np.log10(peak + 1e-10)
        crest_factor = peak / (rms + 1e-10)
        dynamic_range = peak_db - rms_db

        signs = np.sign(analysis_audio)
        zcr = float(np.mean(np.abs(np.diff(signs)) > 0))

        fft = np.abs(np.fft.rfft(analysis_audio))
        freqs = np.fft.rfftfreq(len(analysis_audio), 1 / sample_rate)
        spectral_centroid = (
            float(np.sum(freqs * fft) / np.sum(fft))
            if np.sum(fft) > 0
            else 0.0
        )

        energy_variance = cls._frame_energy_variance(analysis_audio, sample_rate)
        pitch_mean, pitch_variance = cls._pitch_stats(analysis_audio, sample_rate)
        energy_band = cls._classify_energy_band(rms_db)

        return EmotionAudioMetrics(
            rms_db=rms_db,
            peak_db=peak_db,
            peak_amplitude=peak,
            mean_amplitude=mean_abs,
            spectral_centroid=spectral_centroid,
            zero_crossing_rate=zcr,
            energy_variance=energy_variance,
            pitch_mean=pitch_mean,
            pitch_variance=pitch_variance,
            raw_rms_db=rms_db,
            raw_peak_db=peak_db,
            energy_band=energy_band,
            dynamic_range=dynamic_range,
            crest_factor=crest_factor,
            energy_normalized=False,
            energy_level="unknown",
        )

    @staticmethod
    def _frame_energy_variance(audio: np.ndarray, sample_rate: int) -> float:
        frame = int(0.025 * sample_rate)
        hop = int(0.010 * sample_rate)
        if len(audio) < frame:
            return 0.0
        energies: list[float] = []
        for start in range(0, len(audio) - frame + 1, hop):
            window = audio[start:start + frame]
            energies.append(float(np.sqrt(np.mean(window * window) + 1e-12)))
        if not energies:
            return 0.0
        return float(np.var(energies))

    @staticmethod
    def _pitch_stats(audio: np.ndarray, sample_rate: int) -> tuple[float, float]:
        frame = int(0.032 * sample_rate)
        hop = int(0.016 * sample_rate)
        if len(audio) < frame:
            return 0.0, 0.0

        min_f0 = 70.0
        max_f0 = 350.0
        pitches: list[float] = []
        fft_window = np.hanning(frame).astype(np.float32)

        min_bin = int(np.floor(min_f0 * frame / sample_rate))
        max_bin = int(np.ceil(max_f0 * frame / sample_rate))

        for start in range(0, len(audio) - frame + 1, hop):
            frame_audio = audio[start:start + frame]
            if np.max(np.abs(frame_audio)) < 1e-4:
                continue

            spectrum = np.abs(np.fft.rfft(frame_audio * fft_window))
            if spectrum.size <= 2:
                continue

            lo = max(1, min_bin)
            hi = min(max_bin, spectrum.size - 1)
            if hi <= lo:
                continue

            idx_local = int(np.argmax(spectrum[lo:hi + 1]))
            peak_bin = lo + idx_local
            f0 = (peak_bin * sample_rate) / float(frame)
            if min_f0 <= f0 <= max_f0:
                pitches.append(f0)

        if len(pitches) < 2:
            return 0.0, 0.0
        return float(np.mean(pitches)), float(np.var(pitches))

    @classmethod
    def _classify_energy_level(cls, rms_db: float) -> str:
        if rms_db < cls.SILENT_THRESHOLD_DBFS:
            return "silent"
        if rms_db < cls.QUIET_THRESHOLD_DBFS:
            return "quiet"
        if rms_db < cls.NORMAL_THRESHOLD_DBFS:
            return "normal"
        if rms_db < cls.LOUD_THRESHOLD_DBFS:
            return "loud"
        return "very_loud"

    @staticmethod
    def _classify_energy_band(rms_db: float) -> str:
        if rms_db < -35.0:
            return "very_low"
        if rms_db < -25.0:
            return "low"
        if rms_db < -15.0:
            return "normal"
        return "high"

    @staticmethod
    def _mel_filterbank(sample_rate: int, n_fft: int, n_mels: int) -> np.ndarray:
        def hz_to_mel(hz: np.ndarray) -> np.ndarray:
            return 2595.0 * np.log10(1.0 + hz / 700.0)

        def mel_to_hz(mel: np.ndarray) -> np.ndarray:
            return 700.0 * (10 ** (mel / 2595.0) - 1.0)

        fmin, fmax = 0.0, sample_rate / 2.0
        mels = np.linspace(hz_to_mel(np.array([fmin]))[0], hz_to_mel(np.array([fmax]))[0], n_mels + 2)
        hz = mel_to_hz(mels)
        bins = np.floor((n_fft + 1) * hz / sample_rate).astype(int)

        fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
        for m in range(1, n_mels + 1):
            left = bins[m - 1]
            center = bins[m]
            right = bins[m + 1]
            if center <= left:
                center = left + 1
            if right <= center:
                right = center + 1

            for k in range(left, min(center, fb.shape[1])):
                fb[m - 1, k] = (k - left) / max(center - left, 1)
            for k in range(center, min(right, fb.shape[1])):
                fb[m - 1, k] = (right - k) / max(right - center, 1)

        return fb

    @classmethod
    def extract_logmel_features(
        cls,
        audio: np.ndarray,
        sample_rate: int = 16_000,
        n_fft: int = 512,
        hop_length: int = 160,
        n_mels: int = 64,
    ) -> np.ndarray:
        """Compute log-mel features for feature-level normalization and invariance."""
        if audio.size == 0:
            return np.zeros((n_mels, 1), dtype=np.float32)

        _, _, zxx = stft(
            audio,
            fs=sample_rate,
            nperseg=n_fft,
            noverlap=n_fft - hop_length,
            boundary=None,
            padded=False,
        )
        power = np.abs(zxx) ** 2
        mel_fb = cls._mel_filterbank(sample_rate, n_fft, n_mels)
        mel_spec = np.dot(mel_fb, power)
        return np.log(mel_spec + 1e-8).astype(np.float32)

    @classmethod
    def extract_standardized_logmel_features(
        cls,
        audio: np.ndarray,
        sample_rate: int = 16_000,
        n_fft: int = 512,
        hop_length: int = 160,
        n_mels: int = 64,
    ) -> np.ndarray:
        """Log-mel + per-sample standardization for feature-level invariance."""
        mel = cls.extract_logmel_features(
            audio=audio,
            sample_rate=sample_rate,
            n_fft=n_fft,
            hop_length=hop_length,
            n_mels=n_mels,
        )
        return cls.standardize_features(mel)

    @staticmethod
    def standardize_features(features: np.ndarray) -> np.ndarray:
        """Per-sample feature standardization (z-score)."""
        mean = float(np.mean(features))
        std = float(np.std(features))
        if std < 1e-6:
            return features - mean
        return (features - mean) / std

    @classmethod
    def should_override_to_neutral(
        cls,
        rms_db: float,
        confidence: float,
        predicted_emotion: str,
    ) -> tuple[bool, Optional[str]]:
        """Deprecated compatibility API. Hard emotion overrides are disabled."""
        return False, None


_preprocessor = None


def get_emotion_preprocessor() -> EmotionAudioPreprocessor:
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = EmotionAudioPreprocessor()
    return _preprocessor


__all__ = [
    "EmotionAudioPreprocessor",
    "EmotionAudioMetrics",
    "get_emotion_preprocessor",
]
