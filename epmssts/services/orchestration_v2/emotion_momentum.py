from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class EmotionMomentumOutput:
    smoothed_embedding: torch.Tensor
    escalation_probability: torch.Tensor
    flip_probability: torch.Tensor


class EmotionMomentumModel(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 128,
        model_dim: int = 256,
        num_layers: int = 3,
        num_heads: int = 8,
        max_seq_len: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(embedding_dim, model_dim)
        self.pos_emb = nn.Parameter(torch.randn(1, max_seq_len, model_dim) * 0.01)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=model_dim,
            nhead=num_heads,
            dim_feedforward=model_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.smoothed_head = nn.Sequential(
            nn.Linear(model_dim, model_dim),
            nn.GELU(),
            nn.Linear(model_dim, embedding_dim),
        )

        self.escalation_head = nn.Sequential(
            nn.Linear(model_dim, model_dim // 2),
            nn.GELU(),
            nn.Linear(model_dim // 2, 1),
            nn.Sigmoid(),
        )

        self.flip_head = nn.Sequential(
            nn.Linear(model_dim, model_dim // 2),
            nn.GELU(),
            nn.Linear(model_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, emotion_sequence: torch.Tensor) -> EmotionMomentumOutput:
        if emotion_sequence.dim() != 3:
            raise ValueError("emotion_sequence must have shape [B, N, D]")

        B, N, _ = emotion_sequence.shape
        if N > self.pos_emb.shape[1]:
            raise ValueError(f"Sequence length {N} exceeds max {self.pos_emb.shape[1]}")

        x = self.input_proj(emotion_sequence) + self.pos_emb[:, :N, :]
        h = self.encoder(x)

        last_state = h[:, -1, :]
        pooled = h.mean(dim=1)

        smoothed = F.normalize(self.smoothed_head(last_state), dim=-1)

        trend_signal = (emotion_sequence[:, -1, :] - emotion_sequence[:, 0, :]).abs().mean(dim=-1, keepdim=True)
        escalation_prob = torch.clamp(self.escalation_head(pooled) + 0.15 * trend_signal, 0.0, 1.0)

        if N >= 3:
            diffs = torch.norm(emotion_sequence[:, 1:, :] - emotion_sequence[:, :-1, :], dim=-1)
            flip_signal = diffs.std(dim=-1, keepdim=True)
        else:
            flip_signal = torch.zeros((B, 1), device=emotion_sequence.device)

        flip_prob = torch.clamp(self.flip_head(last_state) + 0.2 * flip_signal, 0.0, 1.0)

        return EmotionMomentumOutput(
            smoothed_embedding=smoothed,
            escalation_probability=escalation_prob,
            flip_probability=flip_prob,
        )
