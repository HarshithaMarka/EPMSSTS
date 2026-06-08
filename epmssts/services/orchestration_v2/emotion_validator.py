from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, Tuple

import numpy as np


class EmotionEmbeddingModel(Protocol):
    async def extract_embedding(self, audio_waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        ...


@dataclass
class EmotionValidationResult:
    emotion_similarity: float
    retry_performed: bool
    waveform: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion_similarity": float(self.emotion_similarity),
            "retry_performed": bool(self.retry_performed),
        }


class EmotionValidator:
    def __init__(
        self,
        model: EmotionEmbeddingModel,
        threshold: float = 0.75,
    ):
        self.model = model
        self.threshold = threshold

    async def validate_and_retry(
        self,
        source_emotion_embedding: np.ndarray,
        generated_waveform: np.ndarray,
        sample_rate: int,
        resynthesize: Callable[[float], Awaitable[np.ndarray]],
        base_intensity: float = 1.0,
    ) -> EmotionValidationResult:
        output_embedding = await self.model.extract_embedding(generated_waveform, sample_rate)
        similarity = self._cosine_similarity(source_emotion_embedding, output_embedding)

        if similarity >= self.threshold:
            return EmotionValidationResult(
                emotion_similarity=float(similarity),
                retry_performed=False,
                waveform=generated_waveform,
            )

        boosted_intensity = min(1.35, base_intensity * 1.18)
        retried_waveform = await resynthesize(boosted_intensity)
        retried_embedding = await self.model.extract_embedding(retried_waveform, sample_rate)
        retried_similarity = self._cosine_similarity(source_emotion_embedding, retried_embedding)

        return EmotionValidationResult(
            emotion_similarity=float(retried_similarity),
            retry_performed=True,
            waveform=retried_waveform,
        )

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a_vec = a.astype(np.float32).reshape(-1)
        b_vec = b.astype(np.float32).reshape(-1)
        denom = (np.linalg.norm(a_vec) * np.linalg.norm(b_vec))
        if denom <= 1e-8:
            return 0.0
        return float(np.dot(a_vec, b_vec) / denom)


class NumpyEmotionEmbeddingModel:
    def __init__(self, extractor_fn: Callable[[np.ndarray, int], np.ndarray]):
        self.extractor_fn = extractor_fn

    async def extract_embedding(self, audio_waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        loop = asyncio.get_running_loop()
        emb = await loop.run_in_executor(None, self.extractor_fn, audio_waveform, sample_rate)
        emb_arr = np.asarray(emb, dtype=np.float32)
        if emb_arr.ndim != 1:
            emb_arr = emb_arr.reshape(-1)
        return emb_arr
