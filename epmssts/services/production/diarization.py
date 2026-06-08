from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import librosa


@dataclass
class SpeakerProfile:
    speaker_id: str
    centroid: np.ndarray
    turns: int = 0


class SpeakerDiarizer:
    def __init__(self, cosine_threshold: float = 0.82, max_speakers: int = 16) -> None:
        self.cosine_threshold = cosine_threshold
        self.max_speakers = max_speakers
        self._profiles: Dict[str, SpeakerProfile] = {}
        self._next_speaker_index = 1
        self._emotion_trends: Dict[str, List[str]] = {}

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector) + 1e-8
        return vector / norm

    @staticmethod
    def extract_embedding(audio: np.ndarray, sample_rate: int, window_seconds: float = 1.0) -> np.ndarray:
        frame_len = max(1, int(sample_rate * window_seconds))
        if audio.shape[0] < frame_len:
            padded = np.pad(audio, (0, frame_len - audio.shape[0]))
        else:
            padded = audio[:frame_len]

        mfcc = librosa.feature.mfcc(y=padded, sr=sample_rate, n_mfcc=20)
        delta = librosa.feature.delta(mfcc)
        embedding = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), delta.mean(axis=1)], axis=0)
        return SpeakerDiarizer._normalize(embedding.astype(np.float32))

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8))

    def assign_speaker(self, embedding: np.ndarray) -> str:
        if not self._profiles:
            return self._create_profile(embedding)

        best_id = None
        best_score = -1.0
        for speaker_id, profile in self._profiles.items():
            score = self._cosine_similarity(embedding, profile.centroid)
            if score > best_score:
                best_score = score
                best_id = speaker_id

        if best_id is not None and best_score >= self.cosine_threshold:
            profile = self._profiles[best_id]
            profile.centroid = self._normalize(0.8 * profile.centroid + 0.2 * embedding)
            profile.turns += 1
            return best_id

        if len(self._profiles) >= self.max_speakers and best_id is not None:
            profile = self._profiles[best_id]
            profile.centroid = self._normalize(0.7 * profile.centroid + 0.3 * embedding)
            profile.turns += 1
            return best_id

        return self._create_profile(embedding)

    def _create_profile(self, embedding: np.ndarray) -> str:
        speaker_id = f"speaker_{self._next_speaker_index:03d}"
        self._next_speaker_index += 1
        self._profiles[speaker_id] = SpeakerProfile(
            speaker_id=speaker_id,
            centroid=self._normalize(embedding.copy()),
            turns=1,
        )
        self._emotion_trends[speaker_id] = []
        return speaker_id

    def update_emotion_trend(self, speaker_id: str, emotion: str, max_points: int = 50) -> None:
        trend = self._emotion_trends.setdefault(speaker_id, [])
        trend.append(emotion)
        if len(trend) > max_points:
            del trend[:-max_points]

    def get_speaker_emotion_trend(self, speaker_id: str) -> List[str]:
        return list(self._emotion_trends.get(speaker_id, []))

    def snapshot(self) -> Dict[str, dict]:
        return {
            speaker_id: {
                "turns": profile.turns,
                "centroid_norm": float(np.linalg.norm(profile.centroid)),
                "emotion_trend": self.get_speaker_emotion_trend(speaker_id),
            }
            for speaker_id, profile in self._profiles.items()
        }
