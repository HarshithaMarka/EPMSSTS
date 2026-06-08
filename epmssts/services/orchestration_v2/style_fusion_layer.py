from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class StyleFusionLayer(nn.Module):
    def __init__(
        self,
        text_dim: int,
        style_dim: int = 256,
        num_heads: int = 8,
        dropout: float = 0.1,
        num_transformer_blocks: int = 2,
    ):
        super().__init__()

        self.style_proj = nn.Linear(style_dim, text_dim)
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=text_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )

        self.gate = nn.Sequential(
            nn.Linear(text_dim * 2, text_dim),
            nn.GELU(),
            nn.Linear(text_dim, text_dim),
            nn.Sigmoid(),
        )

        self.blocks = nn.ModuleList(
            [
                nn.TransformerEncoderLayer(
                    d_model=text_dim,
                    nhead=num_heads,
                    dim_feedforward=text_dim * 4,
                    dropout=dropout,
                    batch_first=True,
                    activation="gelu",
                )
                for _ in range(num_transformer_blocks)
            ]
        )

        self.out_norm = nn.LayerNorm(text_dim)

    def forward(
        self,
        text_features: torch.Tensor,
        style_embedding: Optional[torch.Tensor] = None,
        emotion_embedding: Optional[torch.Tensor] = None,
        dialect_embedding: Optional[torch.Tensor] = None,
        speaker_embedding: Optional[torch.Tensor] = None,
        key_padding_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if style_embedding is None:
            embeds = []
            if emotion_embedding is not None:
                embeds.append(emotion_embedding)
            if dialect_embedding is not None:
                embeds.append(dialect_embedding)
            if speaker_embedding is not None:
                embeds.append(speaker_embedding)
            if not embeds:
                raise ValueError("Provide style_embedding or component embeddings")
            style_embedding = torch.cat(embeds, dim=-1)

        if style_embedding.dim() != 2:
            raise ValueError("style_embedding must be [B, D]")

        B, T, C = text_features.shape

        style_proj = self.style_proj(style_embedding).unsqueeze(1)
        style_tokens = style_proj.repeat(1, T, 1)

        attn_out, _ = self.cross_attn(
            query=text_features,
            key=style_tokens,
            value=style_tokens,
            key_padding_mask=key_padding_mask,
            need_weights=False,
        )

        gate_in = torch.cat([text_features, attn_out], dim=-1)
        g = self.gate(gate_in)

        fused = text_features + g * attn_out

        for block in self.blocks:
            fused = block(fused, src_key_padding_mask=key_padding_mask)

        return self.out_norm(fused)


class ResidualStyleConditioner(nn.Module):
    def __init__(self, channels: int, style_dim: int = 256):
        super().__init__()
        self.scale = nn.Linear(style_dim, channels)
        self.shift = nn.Linear(style_dim, channels)

    def forward(self, x: torch.Tensor, style_embedding: torch.Tensor) -> torch.Tensor:
        scale = torch.tanh(self.scale(style_embedding)).unsqueeze(1)
        shift = self.shift(style_embedding).unsqueeze(1)
        return x + (x * scale) + shift
