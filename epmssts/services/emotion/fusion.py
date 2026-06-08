"""
Emotion fusion utilities with adaptive weighting.

Audio is the primary signal. Text is optional and only used for English.
Uses adaptive weighting based on confidence levels and signal quality.

Key improvements:
- Adaptive text weight based on transcript strength
- Fallback to neutral for low-confidence predictions
- Better handling of conflicting signals
"""

from __future__ import annotations

from typing import Dict, Optional

from epmssts.services.emotion.audio_emotion import EMOTIONS, EmotionPrediction


def _normalize(scores: Dict[str, float]) -> Dict[str, float]:
	"""Normalize scores to sum to 1.0."""
	total = float(sum(scores.values()))
	if total <= 0:
		return {e: 0.0 for e in EMOTIONS}
	return {k: v / total for k, v in scores.items()}


def fuse_emotions(
	audio_pred: EmotionPrediction,
	text_pred: Optional[EmotionPrediction],
	*,
	text_min_confidence: float = 0.40,
	audio_min_confidence: float = 0.40,
	audio_weight: float = 0.65,
	text_weight: float = 0.35,
	audio_energy_rms_db: Optional[float] = None,
) -> EmotionPrediction:
	"""
	Fuse audio and text emotion predictions with adaptive weighting.

	Rules:
	1. If no text prediction, return audio prediction with validation
	2. If both predictions have low confidence, fallback to neutral
	3. If text confidence is strong, increase its weight relative to audio
	4. If transcript is neutral in sentiment, reduce text weight
	5. Low-energy audio: require higher confidence or fallback to neutral

	Args:
		audio_pred: Audio emotion prediction
		text_pred: Optional text emotion prediction  
		text_min_confidence: Minimum confidence for text to be considered
		audio_min_confidence: Minimum confidence for audio to be considered
		audio_weight: Base weight for audio (0.0 to 1.0)
		text_weight: Base weight for text (0.0 to 1.0)
		audio_energy_rms_db: RMS energy level in dBFS for energy-based adjustment

	Returns:
		Fused emotion prediction
	"""
	# Validate audio prediction (energy-based override)
	if audio_energy_rms_db is not None and audio_energy_rms_db < -40.0:
		# Very low energy → require high confidence or fallback to neutral
		if audio_pred.confidence < 0.70:
			neutral_scores = {e: 0.0 for e in EMOTIONS}
			neutral_scores["neutral"] = 1.0
			return EmotionPrediction(
				label="neutral",
				confidence=1.0,
				scores=neutral_scores,
			)

	# Rule 1: No text prediction
	if text_pred is None:
		return audio_pred

	# Rule 2: Both predictions low confidence
	if (audio_pred.confidence < audio_min_confidence and 
	    text_pred.confidence < text_min_confidence):
		neutral_scores = {e: 0.0 for e in EMOTIONS}
		neutral_scores["neutral"] = 1.0
		return EmotionPrediction(
			label="neutral",
			confidence=1.0,
			scores=neutral_scores,
		)

	# Rule 3: Only text is confident
	if (audio_pred.confidence < audio_min_confidence and 
	    text_pred.confidence >= text_min_confidence):
		return text_pred

	# Rule 4: Only audio is confident
	if (text_pred.confidence < text_min_confidence and 
	    audio_pred.confidence >= audio_min_confidence):
		return audio_pred

	# Rule 5: Both are confident → adaptive weighting
	# Increase text weight if its confidence is significantly higher
	adaptive_text_weight = text_weight
	adaptive_audio_weight = audio_weight

	confidence_ratio = text_pred.confidence / (audio_pred.confidence + 1e-6)
	if confidence_ratio > 1.5:  # Text much more confident
		adaptive_text_weight = min(0.60, text_weight + 0.15)
		adaptive_audio_weight = max(0.40, audio_weight - 0.15)
	elif confidence_ratio < 0.67:  # Audio much more confident
		adaptive_audio_weight = min(0.75, audio_weight + 0.10)
		adaptive_text_weight = max(0.25, text_weight - 0.10)

	# Normalize weights
	total_weight = adaptive_audio_weight + adaptive_text_weight
	adaptive_audio_weight /= total_weight
	adaptive_text_weight /= total_weight

	# Fuse with adaptive weights
	audio_scores = _normalize(audio_pred.scores)
	text_scores = _normalize(text_pred.scores)

	combined: Dict[str, float] = {e: 0.0 for e in EMOTIONS}
	for emotion in EMOTIONS:
		combined[emotion] = (
			adaptive_audio_weight * audio_scores.get(emotion, 0.0)
			+ adaptive_text_weight * text_scores.get(emotion, 0.0)
		)

	combined = _normalize(combined)
	top_label = max(combined.items(), key=lambda kv: kv[1])[0]
	confidence = combined[top_label]

	# Rule 6: Fallback to neutral if confidence is too low
	if confidence < 0.30:
		neutral_scores = {e: 0.0 for e in EMOTIONS}
		neutral_scores["neutral"] = 1.0
		return EmotionPrediction(
			label="neutral",
			confidence=1.0,
			scores=neutral_scores,
		)

	return EmotionPrediction(
		label=top_label,
		confidence=confidence,
		scores=combined,
	)


__all__ = ["fuse_emotions"]

