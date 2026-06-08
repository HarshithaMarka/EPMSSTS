from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
import torch
import torch.nn as nn


@dataclass
class DialectTransformResult:
    tokens: List[str]
    retroflex_rate: float
    vowel_elongation_ratio: float
    nasalization_rate: float
    final_pitch_marker_rate: float


class DialectPhonemeTransformer(nn.Module):
    def __init__(self, embedding_dim: int = 64, hidden_dim: int = 128, seed: int = 42):
        super().__init__()
        self.embedding_dim = embedding_dim

        self.controller = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
        )

        self.retroflex_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())
        self.vowel_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())
        self.nasal_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())
        self.final_pitch_head = nn.Sequential(nn.Linear(hidden_dim, 1), nn.Sigmoid())

        self._rng = np.random.default_rng(seed)

        self.retroflex_map = {
            "t": "ʈ",
            "d": "ɖ",
            "n": "ɳ",
            "l": "ɭ",
            "r": "ɽ",
        }

        self.softening_map = {
            "k": "ɡ",
            "p": "b",
            "t": "d",
            "ʈ": "ɖ",
            "s": "z",
        }

        self.vowels = {
            "a", "e", "i", "o", "u", "ɑ", "ə", "ɐ", "ɛ", "ɪ", "ʊ", "ɔ", "æ", "ɒ", "ɯ", "ɨ", "y", "ø", "œ"
        }

        self.nasalizable_vowels = {"a", "ɑ", "ə", "o", "u", "e", "i"}

        self.final_pitch_markers = ["↘", "↗", "→"]

    def tokenize_ipa(self, ipa_sequence: str) -> List[str]:
        pattern = r"[a-zA-Zɐ-ʯː̃ˈˌʰʲʷɡɽɳɭʈɖŋɲɾ]+|[.,!?;:↘↗→]|\s+"
        raw = re.findall(pattern, ipa_sequence)
        tokens = [tok for tok in raw if tok.strip()]
        return tokens

    def transform(
        self,
        ipa_tokens: Sequence[str],
        dialect_embedding: np.ndarray,
    ) -> DialectTransformResult:
        if len(dialect_embedding.shape) != 1 or dialect_embedding.shape[0] != self.embedding_dim:
            raise ValueError(f"dialect_embedding must have shape ({self.embedding_dim},)")

        emb = torch.from_numpy(dialect_embedding.astype(np.float32)).unsqueeze(0)
        with torch.no_grad():
            h = self.controller(emb)
            retroflex_p = float(self.retroflex_head(h).item())
            vowel_p = float(self.vowel_head(h).item())
            nasal_p = float(self.nasal_head(h).item())
            final_pitch_p = float(self.final_pitch_head(h).item())

        out: List[str] = []
        retroflex_count = 0
        vowel_elong_count = 0
        nasal_count = 0
        final_pitch_count = 0

        token_count = max(1, len(ipa_tokens))

        for idx, token in enumerate(ipa_tokens):
            transformed = token

            transformed, is_retro = self._apply_retroflex(transformed, retroflex_p)
            retroflex_count += int(is_retro)

            transformed, is_vowel_long = self._apply_vowel_elongation(transformed, vowel_p)
            vowel_elong_count += int(is_vowel_long)

            transformed, is_nasalized = self._apply_nasalization(transformed, nasal_p)
            nasal_count += int(is_nasalized)

            transformed = self._apply_softening(transformed, 0.4 * (1.0 - retroflex_p))

            if idx == token_count - 1 and self._rng.random() < final_pitch_p:
                marker = self._choose_final_pitch_marker(dialect_embedding)
                transformed = f"{transformed}{marker}"
                final_pitch_count += 1

            out.append(transformed)

        return DialectTransformResult(
            tokens=out,
            retroflex_rate=retroflex_count / token_count,
            vowel_elongation_ratio=vowel_elong_count / token_count,
            nasalization_rate=nasal_count / token_count,
            final_pitch_marker_rate=final_pitch_count / token_count,
        )

    def _apply_retroflex(self, token: str, prob: float) -> tuple[str, bool]:
        chars = list(token)
        changed = False
        for i, ch in enumerate(chars):
            if ch in self.retroflex_map and self._rng.random() < prob:
                chars[i] = self.retroflex_map[ch]
                changed = True
        return "".join(chars), changed

    def _apply_vowel_elongation(self, token: str, prob: float) -> tuple[str, bool]:
        chars = list(token)
        changed = False
        for i, ch in enumerate(chars):
            if ch in self.vowels and "ː" not in token and self._rng.random() < prob:
                chars[i] = f"{ch}ː"
                changed = True
                break
        return "".join(chars), changed

    def _apply_nasalization(self, token: str, prob: float) -> tuple[str, bool]:
        chars = list(token)
        changed = False
        for i, ch in enumerate(chars):
            if ch in self.nasalizable_vowels and "̃" not in token and self._rng.random() < prob:
                chars[i] = f"{ch}̃"
                changed = True
                break
        return "".join(chars), changed

    def _apply_softening(self, token: str, prob: float) -> str:
        chars = list(token)
        for i, ch in enumerate(chars):
            if ch in self.softening_map and self._rng.random() < prob:
                chars[i] = self.softening_map[ch]
        return "".join(chars)

    def _choose_final_pitch_marker(self, dialect_embedding: np.ndarray) -> str:
        e0 = float(dialect_embedding[0])
        e1 = float(dialect_embedding[1])
        if e0 > 0.35:
            return "↘"
        if e1 > 0.35:
            return "↗"
        return "→"
