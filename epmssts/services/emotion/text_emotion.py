"""
Text-based emotion detection for English.

This service is OPTIONAL and only used when language == English.
It uses a pretrained transformer model and maps labels into the
canonical EPMSSTS emotion set:

{neutral, happy, sad, angry, fearful}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from epmssts.services.emotion.audio_emotion import EMOTIONS, EmotionPrediction


MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"


@dataclass
class TextEmotionConfig:
	model_id: str = MODEL_ID
	max_length: int = 256


class TextEmotionService:
	"""
	Text-based emotion recognition for English text.

	- Uses a pretrained transformer classifier.
	- Maps model labels into the canonical EPMSSTS emotion set.
	- Returns an `EmotionPrediction` compatible with audio emotion output.
	"""

	def __init__(
		self,
		model_id: str = MODEL_ID,
		device: Optional[str] = None,
		max_length: int = 256,
	) -> None:
		if device is None:
			device = "cuda" if torch.cuda.is_available() else "cpu"

		self._device = torch.device(device)
		self._tokenizer = AutoTokenizer.from_pretrained(model_id)
		self._model = AutoModelForSequenceClassification.from_pretrained(
			model_id
		).to(self._device)
		self._max_length = max_length

		id2label = self._model.config.id2label
		self._model_id2label: Dict[int, str] = {
			int(k): str(v) for k, v in id2label.items()
		}
		self._label2emotion = self._build_label_mapping()

	def _build_label_mapping(self) -> Dict[str, str]:
		"""
		Map model labels into EPMSSTS emotion set.

		Supported labels for this model typically include:
		{anger, disgust, fear, joy, neutral, sadness, surprise}
		"""
		mapping: Dict[str, str] = {}
		for label in self._model_id2label.values():
			lower = label.lower()
			if lower in {"anger", "angry"}:
				mapping[label] = "angry"
			elif lower in {"fear", "fearful"}:
				mapping[label] = "fearful"
			elif lower in {"joy", "happy"}:
				mapping[label] = "happy"
			elif lower in {"sadness", "sad"}:
				mapping[label] = "sad"
			elif lower in {"neutral"}:
				mapping[label] = "neutral"
			elif lower in {"disgust", "surprise"}:
				# Conservative mapping: treat as neutral rather than overfitting
				mapping[label] = "neutral"
			else:
				mapping[label] = "neutral"
		return mapping

	def predict(self, text: str) -> EmotionPrediction:
		"""
		Predict emotion from English text.

		Args:
			text: input text in English.
		"""
		if text is None or not isinstance(text, str) or not text.strip():
			raise ValueError("Text must be a non-empty string.")

		inputs = self._tokenizer(
			text,
			return_tensors="pt",
			truncation=True,
			max_length=self._max_length,
		)
		inputs = {k: v.to(self._device) for k, v in inputs.items()}

		with torch.no_grad():
			logits = self._model(**inputs).logits

		probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().numpy()

		canonical_scores: Dict[str, float] = {e: 0.0 for e in EMOTIONS}
		for idx, prob in enumerate(probs):
			raw_label = self._model_id2label[int(idx)]
			emotion = self._label2emotion.get(raw_label, "neutral")
			canonical_scores[emotion] += float(prob)

		total = float(sum(canonical_scores.values()))
		if total > 0:
			canonical_scores = {k: v / total for k, v in canonical_scores.items()}

		top_label = max(canonical_scores.items(), key=lambda kv: kv[1])[0]
		confidence = canonical_scores[top_label]

		return EmotionPrediction(
			label=top_label,
			confidence=confidence,
			scores=canonical_scores,
		)


__all__ = ["TextEmotionService", "TextEmotionConfig"]

