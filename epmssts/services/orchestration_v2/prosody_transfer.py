from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import librosa
import numpy as np
import torch

from .prosody_extractor import ProsodyFeatures


@dataclass
class ProsodyTransferOutput:
    pitch: torch.Tensor
    energy: torch.Tensor
    duration: torch.Tensor
    pause_mask: torch.Tensor
    variance_adaptor_features: torch.Tensor

    def as_dict(self) -> Dict[str, torch.Tensor]:
        return {
            "pitch": self.pitch,
            "energy": self.energy,
            "duration": self.duration,
            "pause_mask": self.pause_mask,
            "variance_adaptor_features": self.variance_adaptor_features,
        }


class ProsodyTransferEngine:
    def __init__(self, sample_rate: int = 16000, hop_length: int = 128):
        self.sample_rate = sample_rate
        self.hop_length = hop_length

    def transfer(
        self,
        source: ProsodyFeatures,
        translated_phonemes_ipa: Sequence[str],
        target_mel_length: int,
    ) -> ProsodyTransferOutput:
        if target_mel_length <= 0:
            raise ValueError("target_mel_length must be > 0")

        tokens = list(translated_phonemes_ipa)
        if not tokens:
            raise ValueError("translated_phonemes_ipa cannot be empty")

        src_pitch = np.asarray(source.f0_curve, dtype=np.float32)
        src_energy = np.asarray(source.energy_curve, dtype=np.float32)

        if src_pitch.ndim != 1 or src_energy.ndim != 1:
            raise ValueError("source curves must be 1D")

        src_len = int(min(len(src_pitch), len(src_energy)))
        src_pitch = src_pitch[:src_len]
        src_energy = src_energy[:src_len]

        target_anchor_len = max(len(tokens), 2)
        target_proto = self._phoneme_prosody_prototype(tokens=tokens)

        src_feat = np.stack([src_pitch, src_energy], axis=0)
        tgt_feat = np.stack([target_proto[:, 0], target_proto[:, 1]], axis=0)

        _, wp = librosa.sequence.dtw(X=src_feat, Y=tgt_feat, metric="euclidean")
        wp = wp[::-1]

        mapped_pitch, mapped_energy = self._map_with_warp_path(
            src_pitch=src_pitch,
            src_energy=src_energy,
            warp_path=wp,
            target_len=target_anchor_len,
        )

        mel_pitch = self._resample_curve(mapped_pitch, target_mel_length)
        mel_energy = self._resample_curve(mapped_energy, target_mel_length)

        pause_mask = self._inject_pauses(
            pause_durations=source.pause_durations,
            target_mel_length=target_mel_length,
            total_source_frames=src_len,
        )

        mel_energy = np.clip(mel_energy * (1.0 - 0.25 * pause_mask), 0.0, 1.5).astype(np.float32)

        duration = self._derive_durations(
            warp_path=wp,
            token_count=len(tokens),
            target_mel_length=target_mel_length,
        )

        pitch_tensor = torch.from_numpy(mel_pitch).float()
        energy_tensor = torch.from_numpy(mel_energy).float()
        pause_tensor = torch.from_numpy(pause_mask).float()
        duration_tensor = torch.from_numpy(duration).long()

        variance_feats = torch.stack(
            [pitch_tensor, energy_tensor, pause_tensor], dim=-1
        ).unsqueeze(0)

        return ProsodyTransferOutput(
            pitch=pitch_tensor,
            energy=energy_tensor,
            duration=duration_tensor,
            pause_mask=pause_tensor,
            variance_adaptor_features=variance_feats,
        )

    def _phoneme_prosody_prototype(self, tokens: Sequence[str]) -> np.ndarray:
        vowels = {
            "a", "e", "i", "o", "u", "ɑ", "ə", "ɐ", "ɛ", "ɪ", "ʊ", "ɔ", "æ", "ɒ", "ɯ", "ɨ", "y", "ø", "œ"
        }
        sonorants = {"m", "n", "ɳ", "ɲ", "ŋ", "l", "ɭ", "ɾ", "r", "j", "w"}

        proto = np.zeros((len(tokens), 2), dtype=np.float32)
        for idx, token in enumerate(tokens):
            t = token.strip()
            if not t:
                proto[idx] = np.array([0.0, 0.2], dtype=np.float32)
                continue

            if any(ch in vowels for ch in t):
                proto[idx] = np.array([0.7, 0.8], dtype=np.float32)
            elif any(ch in sonorants for ch in t):
                proto[idx] = np.array([0.4, 0.55], dtype=np.float32)
            else:
                proto[idx] = np.array([0.2, 0.35], dtype=np.float32)

        return proto

    def _map_with_warp_path(
        self,
        src_pitch: np.ndarray,
        src_energy: np.ndarray,
        warp_path: np.ndarray,
        target_len: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        mapped_pitch = np.zeros(target_len, dtype=np.float32)
        mapped_energy = np.zeros(target_len, dtype=np.float32)
        counts = np.zeros(target_len, dtype=np.float32)

        for src_idx, tgt_idx in warp_path:
            tgt_i = int(np.clip(tgt_idx, 0, target_len - 1))
            src_i = int(np.clip(src_idx, 0, len(src_pitch) - 1))
            mapped_pitch[tgt_i] += float(src_pitch[src_i])
            mapped_energy[tgt_i] += float(src_energy[src_i])
            counts[tgt_i] += 1.0

        counts = np.maximum(counts, 1.0)
        mapped_pitch /= counts
        mapped_energy /= counts

        mapped_pitch = self._fill_zeros_by_interp(mapped_pitch)
        mapped_energy = self._fill_zeros_by_interp(mapped_energy)

        return mapped_pitch.astype(np.float32), mapped_energy.astype(np.float32)

    def _fill_zeros_by_interp(self, curve: np.ndarray) -> np.ndarray:
        nz = np.where(np.abs(curve) > 1e-8)[0]
        if nz.size <= 1:
            return curve
        x = np.arange(curve.shape[0], dtype=np.float32)
        curve_interp = np.interp(x, nz.astype(np.float32), curve[nz].astype(np.float32))
        return curve_interp.astype(np.float32)

    def _resample_curve(self, curve: np.ndarray, target_len: int) -> np.ndarray:
        if len(curve) == target_len:
            return curve.astype(np.float32)
        src_x = np.linspace(0.0, 1.0, num=len(curve), dtype=np.float32)
        tgt_x = np.linspace(0.0, 1.0, num=target_len, dtype=np.float32)
        mapped = np.interp(tgt_x, src_x, curve).astype(np.float32)
        return mapped

    def _inject_pauses(
        self,
        pause_durations: Sequence[float],
        target_mel_length: int,
        total_source_frames: int,
    ) -> np.ndarray:
        pause_mask = np.zeros(target_mel_length, dtype=np.float32)
        if not pause_durations:
            return pause_mask

        total_pause_sec = float(np.sum(pause_durations))
        if total_pause_sec <= 1e-6:
            return pause_mask

        total_source_sec = total_source_frames * (self.hop_length / self.sample_rate)
        if total_source_sec <= 1e-6:
            total_source_sec = total_pause_sec

        pause_frames_total = int(round((total_pause_sec / total_source_sec) * target_mel_length))
        pause_frames_total = int(np.clip(pause_frames_total, 1, max(1, target_mel_length // 2)))

        slot_count = max(1, len(pause_durations))
        frames_per_slot = max(1, pause_frames_total // slot_count)

        anchors = np.linspace(
            int(0.1 * target_mel_length),
            int(0.9 * target_mel_length),
            num=slot_count,
            dtype=int,
        )

        for anchor in anchors.tolist():
            start = max(0, anchor - frames_per_slot // 2)
            end = min(target_mel_length, start + frames_per_slot)
            pause_mask[start:end] = 1.0

        return pause_mask

    def _derive_durations(
        self,
        warp_path: np.ndarray,
        token_count: int,
        target_mel_length: int,
    ) -> np.ndarray:
        durations = np.zeros(token_count, dtype=np.int64)
        for _, tgt_idx in warp_path:
            token_idx = int(np.clip(tgt_idx, 0, token_count - 1))
            durations[token_idx] += 1

        durations[durations == 0] = 1
        total = int(np.sum(durations))
        if total != target_mel_length:
            scale = target_mel_length / float(total)
            durations = np.maximum(1, np.round(durations * scale)).astype(np.int64)
            delta = target_mel_length - int(np.sum(durations))
            if delta != 0:
                idx = int(np.argmax(durations))
                durations[idx] = max(1, durations[idx] + delta)

        return durations
