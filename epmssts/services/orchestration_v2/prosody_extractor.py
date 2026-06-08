from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import librosa
import numpy as np
import soundfile as sf

TARGET_SAMPLE_RATE = 16000


@dataclass
class ProsodyFeatures:
    f0_curve: np.ndarray
    energy_curve: np.ndarray
    pause_durations: List[float]
    speaking_rate: float
    voiced_ratio: float
    voiced_durations: List[float]
    processing_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "f0_curve": self.f0_curve,
            "energy_curve": self.energy_curve,
            "pause_durations": self.pause_durations,
            "speaking_rate": float(self.speaking_rate),
            "voiced_ratio": float(self.voiced_ratio),
            "voiced_durations": self.voiced_durations,
            "processing_ms": float(self.processing_ms),
        }


class ProsodyExtractor:
    def __init__(
        self,
        sample_rate: int = TARGET_SAMPLE_RATE,
        frame_length: int = 512,
        hop_length: int = 128,
        f0_min_hz: float = 65.0,
        f0_max_hz: float = 500.0,
        pause_threshold_db: float = -38.0,
        min_pause_ms: float = 80.0,
        min_voiced_ms: float = 60.0,
    ):
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.hop_length = hop_length
        self.f0_min_hz = f0_min_hz
        self.f0_max_hz = f0_max_hz
        self.pause_threshold_db = pause_threshold_db
        self.min_pause_ms = min_pause_ms
        self.min_voiced_ms = min_voiced_ms

    def extract(
        self,
        wav_input: Union[str, bytes, np.ndarray],
        whisper_segments: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> ProsodyFeatures:
        started = time.perf_counter()
        waveform = self._load_mono_waveform(wav_input)

        if waveform.size == 0:
            return ProsodyFeatures(
                f0_curve=np.zeros(1, dtype=np.float32),
                energy_curve=np.zeros(1, dtype=np.float32),
                pause_durations=[],
                speaking_rate=0.0,
                voiced_ratio=0.0,
                voiced_durations=[],
                processing_ms=(time.perf_counter() - started) * 1000.0,
            )

        f0 = librosa.yin(
            waveform,
            fmin=self.f0_min_hz,
            fmax=self.f0_max_hz,
            sr=self.sample_rate,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
        ).astype(np.float32)

        rms = librosa.feature.rms(
            y=waveform,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
            center=True,
        )[0].astype(np.float32)

        frame_count = int(min(f0.shape[0], rms.shape[0]))
        f0 = f0[:frame_count]
        rms = rms[:frame_count]

        voiced_mask = self._compute_voiced_mask(f0, rms)
        voiced_ratio = float(np.mean(voiced_mask)) if voiced_mask.size else 0.0

        voiced_durations, pause_durations = self._segment_durations(voiced_mask)

        speaking_rate = self._compute_speaking_rate(
            whisper_segments=whisper_segments,
            voiced_durations=voiced_durations,
            total_duration_sec=float(len(waveform) / self.sample_rate),
        )

        f0_norm = self._normalize_f0(f0=f0, voiced_mask=voiced_mask)
        energy_norm = self._normalize_energy(rms)

        return ProsodyFeatures(
            f0_curve=f0_norm,
            energy_curve=energy_norm,
            pause_durations=pause_durations,
            speaking_rate=speaking_rate,
            voiced_ratio=voiced_ratio,
            voiced_durations=voiced_durations,
            processing_ms=(time.perf_counter() - started) * 1000.0,
        )

    def _load_mono_waveform(self, wav_input: Union[str, bytes, np.ndarray]) -> np.ndarray:
        if isinstance(wav_input, np.ndarray):
            y = wav_input.astype(np.float32)
            if y.ndim == 2:
                y = np.mean(y, axis=1)
            return self._resample_if_needed(y, self.sample_rate)

        if isinstance(wav_input, bytes):
            y, sr = sf.read(io.BytesIO(wav_input), always_2d=False)
        else:
            y, sr = sf.read(wav_input, always_2d=False)

        y = np.asarray(y, dtype=np.float32)
        if y.ndim == 2:
            y = np.mean(y, axis=1)

        y = self._resample_if_needed(y, int(sr))
        y = y - float(np.mean(y))

        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak > 0.0:
            y = y / peak

        return np.clip(y, -1.0, 1.0).astype(np.float32)

    def _resample_if_needed(self, y: np.ndarray, source_sr: int) -> np.ndarray:
        if source_sr == self.sample_rate:
            return y.astype(np.float32)
        return librosa.resample(y, orig_sr=source_sr, target_sr=self.sample_rate).astype(np.float32)

    def _compute_voiced_mask(self, f0: np.ndarray, rms: np.ndarray) -> np.ndarray:
        energy_db = librosa.amplitude_to_db(np.maximum(rms, 1e-7), ref=np.max)
        valid_f0 = np.isfinite(f0) & (f0 > self.f0_min_hz) & (f0 < self.f0_max_hz)
        voiced_mask = valid_f0 & (energy_db > self.pause_threshold_db)

        if voiced_mask.size >= 3:
            smoothed = voiced_mask.copy()
            smoothed[1:-1] = (voiced_mask[:-2] | voiced_mask[1:-1] | voiced_mask[2:])
            voiced_mask = smoothed

        return voiced_mask

    def _segment_durations(self, voiced_mask: np.ndarray) -> Tuple[List[float], List[float]]:
        if voiced_mask.size == 0:
            return [], []

        frame_sec = self.hop_length / float(self.sample_rate)
        changes = np.diff(voiced_mask.astype(np.int8), prepend=int(voiced_mask[0]))
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == -1)

        if voiced_mask[0]:
            starts = np.insert(starts, 0, 0)
        if voiced_mask[-1]:
            ends = np.append(ends, voiced_mask.size)

        voiced_durations: List[float] = []
        for start, end in zip(starts.tolist(), ends.tolist()):
            dur = (end - start) * frame_sec
            if dur * 1000.0 >= self.min_voiced_ms:
                voiced_durations.append(float(dur))

        pause_mask = ~voiced_mask
        changes_pause = np.diff(pause_mask.astype(np.int8), prepend=int(pause_mask[0]))
        pause_starts = np.flatnonzero(changes_pause == 1)
        pause_ends = np.flatnonzero(changes_pause == -1)

        if pause_mask[0]:
            pause_starts = np.insert(pause_starts, 0, 0)
        if pause_mask[-1]:
            pause_ends = np.append(pause_ends, pause_mask.size)

        pause_durations: List[float] = []
        for start, end in zip(pause_starts.tolist(), pause_ends.tolist()):
            dur = (end - start) * frame_sec
            if dur * 1000.0 >= self.min_pause_ms:
                pause_durations.append(float(dur))

        return voiced_durations, pause_durations

    def _compute_speaking_rate(
        self,
        whisper_segments: Optional[Sequence[Dict[str, Any]]],
        voiced_durations: Sequence[float],
        total_duration_sec: float,
    ) -> float:
        if not whisper_segments:
            voiced_time = float(np.sum(voiced_durations))
            return 0.0 if voiced_time <= 1e-6 else float(len(voiced_durations) / voiced_time)

        phoneme_count = 0.0
        timing_start = None
        timing_end = None

        for seg in whisper_segments:
            seg_start = seg.get("start")
            seg_end = seg.get("end")
            if isinstance(seg_start, (int, float)) and isinstance(seg_end, (int, float)):
                timing_start = float(seg_start) if timing_start is None else min(timing_start, float(seg_start))
                timing_end = float(seg_end) if timing_end is None else max(timing_end, float(seg_end))

            words = seg.get("words", [])
            if isinstance(words, list) and words:
                for word_obj in words:
                    token = str(word_obj.get("word", "")).strip()
                    if token:
                        phoneme_count += float(self._estimate_phonemes_in_word(token))
            else:
                text = str(seg.get("text", ""))
                for token in text.split():
                    phoneme_count += float(self._estimate_phonemes_in_word(token))

        voiced_window = 0.0
        if timing_start is not None and timing_end is not None and timing_end > timing_start:
            voiced_window = timing_end - timing_start
        else:
            voiced_window = float(np.sum(voiced_durations))

        if voiced_window <= 1e-6:
            voiced_window = max(total_duration_sec, 1e-6)

        return float(phoneme_count / voiced_window)

    def _estimate_phonemes_in_word(self, token: str) -> int:
        cleaned = "".join(ch for ch in token.lower() if ch.isalpha())
        if not cleaned:
            return 1

        vowels = set("aeiouy")
        groups = 0
        prev_vowel = False
        for ch in cleaned:
            is_vowel = ch in vowels
            if is_vowel and not prev_vowel:
                groups += 1
            prev_vowel = is_vowel

        base = max(1, groups)
        consonants = sum(1 for ch in cleaned if ch not in vowels)
        phoneme_est = int(round(base + min(3, consonants * 0.25)))
        return max(1, phoneme_est)

    def _normalize_f0(self, f0: np.ndarray, voiced_mask: np.ndarray) -> np.ndarray:
        norm = np.zeros_like(f0, dtype=np.float32)
        if not np.any(voiced_mask):
            return norm

        voiced_vals = f0[voiced_mask]
        mu = float(np.mean(voiced_vals))
        sigma = float(np.std(voiced_vals))
        sigma = sigma if sigma > 1e-6 else 1.0
        norm[voiced_mask] = ((voiced_vals - mu) / sigma).astype(np.float32)
        return np.clip(norm, -4.0, 4.0)

    def _normalize_energy(self, rms: np.ndarray) -> np.ndarray:
        if rms.size == 0:
            return rms.astype(np.float32)
        p10 = float(np.percentile(rms, 10))
        p90 = float(np.percentile(rms, 90))
        denom = max(p90 - p10, 1e-6)
        scaled = (rms - p10) / denom
        return np.clip(scaled, 0.0, 1.0).astype(np.float32)
