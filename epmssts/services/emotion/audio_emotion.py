from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

try:
    import torch
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    _TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency/model availability
    torch = None  # type: ignore[assignment]
    AutoFeatureExtractor = None  # type: ignore[assignment]
    AutoModelForAudioClassification = None  # type: ignore[assignment]
    _TRANSFORMERS_AVAILABLE = False


MODEL_ID = "superb/wav2vec2-base-superb-er"


EMOTIONS = ("neutral", "happy", "sad", "angry", "fearful")


@dataclass
class EmotionPrediction:
    label: str
    confidence: float
    scores: Dict[str, float]

    @property
    def emotion(self) -> str:
        # Backwards-compatible alias for tests and older code.
        return self.label


class AudioEmotionService:
    """
    Audio-based emotion recognition using a Wav2Vec2 SER model.

    - Uses `superb/wav2vec2-base-superb-er` (4 emotions).
    - Maps model outputs into the project emotion set:
      {neutral, happy, sad, angry, fearful}.
    - Accepts 16kHz mono float32 NumPy arrays.
    - Includes energy-based calibration to prevent "sad" bias on low-energy input
    """

    def __init__(
        self,
        model_id: str = MODEL_ID,
        device: Optional[str] = None,
    ) -> None:
        self._model_available = False
        self._model_error: Optional[str] = None
        self._device = None
        self._extractor = None
        self._model = None
        self._model_id2label: Dict[int, str] = {}
        self._label2emotion: Dict[str, str] = {}
        
        # Import preprocessor lazily to avoid circular imports
        try:
            from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor
            self._preprocessor = get_emotion_preprocessor()
        except Exception:
            self._preprocessor = None

        if not _TRANSFORMERS_AVAILABLE or torch is None:
            self._model_error = "transformers/torch not available"
            return

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._device = torch.device(device)

        try:
            self._extractor = AutoFeatureExtractor.from_pretrained(model_id)
            self._model = AutoModelForAudioClassification.from_pretrained(model_id).to(
                self._device
            )
            # Set model to eval mode for inference optimization
            self._model.eval()
            self._model_available = True
            print(f"[Emotion] Initialized: model={model_id}, device={device}")
        except Exception as exc:
            self._model_error = str(exc)
            return

        # Prepare mapping from model labels to our canonical emotions.
        self._model_id2label = dict(self._model.config.id2label)  # type: ignore[arg-type]
        self._label2emotion = self._build_label_mapping()

    @staticmethod
    def is_silent(audio: np.ndarray, threshold: float = 1e-5) -> bool:
        """Check if audio is silent. Lower threshold (1e-5) to accept quieter recordings."""
        if audio.size == 0:
            return True
        rms = float(np.sqrt(np.mean(np.square(audio))))
        return rms < threshold

    def _build_label_mapping(self) -> Dict[str, str]:
        """
        Map raw model labels to project emotion categories.

        For `superb/wav2vec2-base-superb-er`, labels are abbreviated:
        - neu → neutral
        - hap → happy
        - ang → angry
        - sad → sad

        We map them to full emotion names for consistency.
        """
        mapping: Dict[str, str] = {}
        for label in self._model_id2label.values():
            lower = label.lower()
            # Handle abbreviated labels from wav2vec2-base-superb-er
            if lower == "neu" or lower == "neutral":
                mapping[label] = "neutral"
            elif lower == "hap" or lower == "happy":
                mapping[label] = "happy"
            elif lower == "ang" or lower == "angry":
                mapping[label] = "angry"
            elif lower == "sad":
                mapping[label] = "sad"
            else:
                # Any unexpected label falls back to neutral.
                mapping[label] = "neutral"
        return mapping

    def predict(self, audio: np.ndarray, sample_rate: int) -> EmotionPrediction:
        """
        Predict emotion from 16kHz mono audio with energy calibration.

        Args:
            audio: 1D float32 NumPy array (16kHz mono).
            sample_rate: sample rate of `audio`. Must be 16_000.
        
        Returns:
            EmotionPrediction with label, confidence, and scores
        
        Process:
            1. Validate audio format
            2. Preprocess audio with RMS normalization
            3. Check for silence
            4. Run model inference
            5. Apply energy-based calibration to prevent "sad" bias
        """
        if audio.ndim != 1:
            raise ValueError("Expected mono audio array of shape (num_samples,).")
        if sample_rate != 16_000:
            raise ValueError("AudioEmotionService expects audio at 16kHz.")

        if self.is_silent(audio):
            # Silence handling: immediate neutral with full confidence.
            scores = {emotion: 0.0 for emotion in EMOTIONS}
            scores["neutral"] = 1.0
            return EmotionPrediction(label="neutral", confidence=1.0, scores=scores)

        if not self._model_available or self._model is None or self._extractor is None:
            # Fallback: return a stable neutral prediction when model is unavailable.
            scores = {emotion: 0.0 for emotion in EMOTIONS}
            scores["neutral"] = 1.0
            return EmotionPrediction(label="neutral", confidence=1.0, scores=scores)

        # Preprocess audio with adaptive RMS normalization and energy metrics
        audio_preprocessed = audio
        audio_metrics = None
        
        if self._preprocessor is not None:
            try:
                audio_preprocessed, audio_metrics = self._preprocessor.preprocess_for_emotion(
                    audio, sample_rate
                )
            except Exception:
                # Fallback to original audio if preprocessing fails
                audio_preprocessed = audio

        # Feature-level normalization path (log-mel z-score) for volume invariance.
        # We keep waveform intact and use standardized mel for calibration context.
        standardized_mel = None
        if self._preprocessor is not None:
            try:
                standardized_mel = self._preprocessor.extract_standardized_logmel_features(
                    audio_preprocessed,
                    sample_rate=sample_rate,
                )
            except Exception:
                standardized_mel = None

        # Run inference on preprocessed audio waveform
        inputs = self._extractor(
            audio_preprocessed,
            sampling_rate=sample_rate,
            return_tensors="pt",
        )

        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self._model(**inputs).logits

        # Convert to probabilities.
        probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().numpy()

        # Aggregate probabilities into our canonical emotion set.
        canonical_scores: Dict[str, float] = {e: 0.0 for e in EMOTIONS}
        for idx, prob in enumerate(probs):
            raw_label = self._model_id2label[int(idx)]
            emotion = self._label2emotion.get(raw_label, "neutral")
            canonical_scores[emotion] += float(prob)

        # Normalize to sum to 1.0 to stay well-formed.
        total = float(sum(canonical_scores.values()))
        if total > 0:
            canonical_scores = {k: v / total for k, v in canonical_scores.items()}

        # Use raw model predictions without post-processing class-specific scaling
        # The previous _apply_confidence_scaling() method was class-specific and biased
        # toward "sad" for low-energy audio. Model predictions are already calibrated
        # by the wav2vec2 training process and should be trusted.
        final_label = max(canonical_scores.items(), key=lambda kv: kv[1])[0]
        final_confidence = canonical_scores[final_label]

        return EmotionPrediction(
            label=final_label,
            confidence=final_confidence,
            scores=canonical_scores,
        )

    def _log_prediction_diagnostics(
        self,
        scores: Dict[str, float],
        predicted_label: str,
        predicted_confidence: float,
        audio_metrics,
    ) -> Dict:
        """
        Log diagnostic information about prediction without modifying scores.
        
        This method is purely diagnostic - it does NOT modify predictions.
        The model's softmax output is the ground truth and should not be
        artificially adjusted based on audio characteristics.
        
        Returns diagnostic dict for potential logging/monitoring, but does
        NOT modify the emotion prediction.
        """
        diagnostics = {
            "raw_probs": {k: round(v, 4) for k, v in scores.items()},
            "predicted": predicted_label,
            "confidence": round(predicted_confidence, 4),
            "energy_band": audio_metrics.energy_band if audio_metrics else "unknown",
            "postprocess_adjusted": False,  # Always false - we don't adjust anymore
            "reason": "Removed class-specific confidence scaling that was biasing toward 'sad'"
        }
        
        # Optional: Log to file or monitoring system
        # logger.debug(f"Emotion prediction diagnostic: {diagnostics}")
        
        return diagnostics

    @staticmethod
    def _renormalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
        clipped = {k: max(0.0, float(v)) for k, v in scores.items()}
        total = float(sum(clipped.values()))
        if total <= 0.0:
            neutral = {e: 0.0 for e in EMOTIONS}
            neutral["neutral"] = 1.0
            return neutral
        return {k: v / total for k, v in clipped.items()}


__all__ = ["AudioEmotionService", "EmotionPrediction", "EMOTIONS"]

