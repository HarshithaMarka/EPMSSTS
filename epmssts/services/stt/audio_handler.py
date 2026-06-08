from __future__ import annotations

from io import BytesIO
from typing import Dict, Tuple

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt


TARGET_SAMPLE_RATE = 16_000

DEFAULT_VAD_FRAME_MS = 30
DEFAULT_VAD_HOP_MS = 10


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """
    Convert audio to mono.

    Accepts shapes:
    - (num_samples,)        → mono
    - (num_samples, num_channels) → average across channels
    """
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        # Average channels safely
        return audio.mean(axis=1)
    raise ValueError(f"Unsupported audio shape {audio.shape!r}")


def _remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    """Remove DC offset to stabilize RMS-based thresholds."""
    if audio.size == 0:
        return audio
    return audio - float(np.mean(audio))


def _normalize_audio(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Peak-normalize audio to a target amplitude."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0.0:
        return audio
    scale = target_peak / peak
    return (audio * scale).astype(np.float32)


def _highpass_filter(audio: np.ndarray, sample_rate: int, cutoff_hz: float = 60.0) -> np.ndarray:
    """Apply a gentle high-pass filter to reduce low-frequency rumble."""
    if audio.size == 0:
        return audio
    nyquist = sample_rate / 2.0
    normalized = min(max(cutoff_hz / nyquist, 0.001), 0.99)
    sos = butter(2, normalized, btype="highpass", output="sos")
    return sosfilt(sos, audio).astype(np.float32)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio to the target sample rate using polyphase filtering.
    """
    if orig_sr == target_sr:
        return audio

    # Use integer ratio resampling via greatest common divisor
    from math import gcd

    g = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    return resample_poly(audio, up, down)


def _trim_silence(
    audio: np.ndarray,
    sample_rate: int,
    frame_ms: int = DEFAULT_VAD_FRAME_MS,
    hop_ms: int = DEFAULT_VAD_HOP_MS,
    pad_ms: int = 120,
) -> np.ndarray:
    """
    Trim leading and trailing silence based on RMS energy.

    If no speech-like frames are detected, returns the original audio
    so downstream silence checks can still handle the case.
    """
    if audio.size == 0:
        return audio

    frame_len = int(sample_rate * frame_ms / 1000)
    hop_len = int(sample_rate * hop_ms / 1000)
    if frame_len <= 0 or hop_len <= 0 or audio.size < frame_len:
        return audio

    frames = []
    for start in range(0, audio.size - frame_len + 1, hop_len):
        frames.append(audio[start : start + frame_len])

    if not frames:
        return audio

    rms = np.array([np.sqrt(np.mean(frame ** 2)) for frame in frames], dtype=np.float32)
    max_rms = float(np.max(rms)) if rms.size else 0.0
    threshold = max(max_rms * 0.1, 1e-4)

    speech_indices = np.where(rms >= threshold)[0]
    if speech_indices.size == 0:
        return audio

    pad = int(sample_rate * pad_ms / 1000)
    start_frame = max(int(speech_indices[0]) * hop_len - pad, 0)
    end_frame = min(int(speech_indices[-1]) * hop_len + frame_len + pad, audio.size)
    return audio[start_frame:end_frame]


def _noise_gate(audio: np.ndarray) -> np.ndarray:
    """Simple noise gate using percentile-based threshold."""
    if audio.size == 0:
        return audio
    floor = float(np.percentile(np.abs(audio), 10))
    threshold = max(floor * 1.5, 1e-5)
    mask = np.abs(audio) >= threshold
    return (audio * mask).astype(np.float32)


def detect_voice_activity(
    audio: np.ndarray,
    sample_rate: int,
    frame_ms: int = DEFAULT_VAD_FRAME_MS,
    hop_ms: int = DEFAULT_VAD_HOP_MS,
) -> float:
    """
    Estimate the ratio of speech-active frames in the audio.

    Returns a float in [0, 1].
    """
    if audio.size == 0:
        return 0.0

    frame_len = int(sample_rate * frame_ms / 1000)
    hop_len = int(sample_rate * hop_ms / 1000)
    if frame_len <= 0 or hop_len <= 0 or audio.size < frame_len:
        return 0.0

    frames = []
    for start in range(0, audio.size - frame_len + 1, hop_len):
        frames.append(audio[start : start + frame_len])

    if not frames:
        return 0.0

    rms = np.array([np.sqrt(np.mean(frame ** 2)) for frame in frames], dtype=np.float32)
    max_rms = float(np.max(rms)) if rms.size else 0.0
    threshold = max(max_rms * 0.1, 1e-4)
    active = np.sum(rms >= threshold)
    return float(active / max(len(rms), 1))


def compute_audio_metrics(audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
    """Compute basic audio quality metrics for observability."""
    duration = float(audio.size / sample_rate) if sample_rate else 0.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    clipped = float(np.mean(np.abs(audio) >= 0.999)) if audio.size else 0.0
    speech_ratio = detect_voice_activity(audio, sample_rate)

    return {
        "duration_sec": duration,
        "peak": peak,
        "rms": rms,
        "clipped_ratio": clipped,
        "speech_ratio": speech_ratio,
    }


def preprocess_audio_bytes(
    file_bytes: bytes,
    *,
    normalize: bool = True,
    trim_silence: bool = True,
    reduce_noise: bool = True,
    target_sample_rate: int = TARGET_SAMPLE_RATE,
) -> Tuple[np.ndarray, int]:
    """
    Decode arbitrary audio bytes and convert to 16kHz mono float32 PCM.

    Raises:
        ValueError: If the bytes cannot be decoded as audio.
    """
    try:
        audio, sample_rate = sf.read(BytesIO(file_bytes), always_2d=False)
    except Exception as exc:
        raise ValueError(f"Invalid or unsupported audio format: {exc}") from exc

    if audio.size == 0:
        raise ValueError("Decoded audio is empty.")

    if not np.isfinite(audio).all():
        raise ValueError("Decoded audio contains NaN or Inf values.")

    audio = _to_mono(np.asarray(audio, dtype=np.float32))
    audio = _remove_dc_offset(audio)
    audio = _resample(audio, int(sample_rate), target_sample_rate)
    audio = _highpass_filter(audio, target_sample_rate)

    if reduce_noise:
        audio = _noise_gate(audio)

    if trim_silence:
        audio = _trim_silence(audio, target_sample_rate)

    # Ensure float32 in [-1, 1] as expected by faster-whisper
    # If the source was int PCM, soundfile already normalizes; this clamp
    # is a safe guardrail.
    if normalize:
        audio = _normalize_audio(audio)

    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)

    return audio, target_sample_rate


__all__ = [
    "preprocess_audio_bytes",
    "compute_audio_metrics",
    "detect_voice_activity",
    "TARGET_SAMPLE_RATE",
]

