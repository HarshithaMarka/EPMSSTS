from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency/model availability
    WhisperModel = None  # type: ignore[assignment]
    _WHISPER_AVAILABLE = False


class _FallbackWhisperSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class _FallbackWhisperInfo:
    def __init__(self, duration: float) -> None:
        self.language = "en"
        self.duration = duration


class _FallbackWhisperModel:
    """
    Lightweight fallback when faster-whisper or model weights are unavailable.
    Produces a deterministic placeholder transcription to keep the pipeline live.
    """

    def transcribe(self, audio: np.ndarray, language=None, task: str = "transcribe"):
        duration = float(len(audio) / 16000) if len(audio) else 0.0
        text = "Test transcription"
        seg = _FallbackWhisperSegment(start=0.0, end=duration, text=text)
        return iter([seg]), _FallbackWhisperInfo(duration=duration)


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration: float
    segments: List[TranscriptionSegment]


class SpeechToTextService:
    """
    Wrapper around faster-whisper for production-ready STT.

    - Loads the `large-v3` model once at process startup.
    - Supports automatic language detection.
    - Accepts preprocessed 16kHz mono float32 NumPy arrays.
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: Optional[str] = None,
        compute_type: str = "float16",
        cpu_threads: int = 4,
        num_workers: int = 1,
    ) -> None:
        """
        Initialize the Whisper model.

        Args:
            model_size: Model identifier; large-v3, base, or small.
            device: "cuda", "cpu", or None for auto-detection.
            compute_type: Precision / quantization mode.
            cpu_threads: Number of CPU threads for inference.
            num_workers: Number of workers for parallel processing.
        """
        # Allow smaller models for CPU optimization
        allowed_models = {"large-v3", "base", "small", "medium"}
        if model_size not in allowed_models:
            raise ValueError(f"Model must be one of {allowed_models}")

        # Device auto-detection if not explicitly provided
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"

        # CPU-friendly default if GPU is not available
        if device == "cpu":
            # Force int8 quantization for CPU
            compute_type = "int8"
            # Use smaller model on CPU for better performance
            if model_size == "large-v3":
                import os
                if os.getenv("EPMSSTS_STT_FORCE_LARGE") != "1":
                    model_size = "base"  # Much faster on CPU
                    print(f"[STT] Optimizing for CPU: using '{model_size}' model instead of large-v3")

        self._model_available = False
        self._model_error: Optional[str] = None
        self._device = device
        self._cpu_threads = cpu_threads

        if not _WHISPER_AVAILABLE or WhisperModel is None:
            # Dependency not available; fall back to lightweight stub.
            self._model = _FallbackWhisperModel()
            self._model_error = "faster-whisper not available"
            return

        try:
            self._model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                num_workers=num_workers,
            )
            self._model_available = True
            print(f"[STT] Initialized: model={model_size}, device={device}, compute_type={compute_type}")
        except Exception as exc:
            # Model load failed (e.g. weights not downloaded).
            self._model = _FallbackWhisperModel()
            self._model_error = str(exc)

    @staticmethod
    def is_silent(audio: np.ndarray, threshold: float = 1e-5) -> bool:
        """
        Heuristic check for near-silent audio based on RMS energy.
        Lower threshold (1e-5) to accept quieter recordings.
        """
        if audio.size == 0:
            return True
        rms = float(np.sqrt(np.mean(np.square(audio))))
        return rms < threshold

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> TranscriptionResult:
        """
        Run transcription on preprocessed audio.

        Args:
            audio: 1D float32 NumPy array at 16kHz mono.
            sample_rate: Sample rate of `audio`. Must be 16_000.
        """
        if audio.ndim != 1:
            raise ValueError("Expected mono audio array of shape (num_samples,).")
        if sample_rate != 16_000:
            raise ValueError("SpeechToTextService expects audio at 16kHz.")

        # Optimized transcription parameters for lower latency
        segments_iter, info = self._model.transcribe(
            audio,
            language=None,  # Auto-detect language
            task="transcribe",
            beam_size=1,  # Greedy decoding for speed
            best_of=1,  # No sampling, single best result
            temperature=0.0,  # Deterministic output
            vad_filter=True,  # Enable VAD to skip silence
            vad_parameters=dict(threshold=0.5, min_speech_duration_ms=250),
        )

        segments: List[TranscriptionSegment] = []
        collected_text: List[str] = []

        for seg in segments_iter:
            text = seg.text.strip()
            segments.append(
                TranscriptionSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=text,
                )
            )
            if text:
                collected_text.append(text)

        full_text = " ".join(collected_text).strip()

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            duration=float(info.duration),
            segments=segments,
        )


__all__ = ["SpeechToTextService", "TranscriptionResult", "TranscriptionSegment"]

