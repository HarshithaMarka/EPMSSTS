from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import Wav2Vec2Model


@dataclass
class StyleEncoderOutput:
    style_embedding: torch.Tensor
    emotion_regression: torch.Tensor
    dialect_logits: torch.Tensor
    speaker_projection: torch.Tensor


class UnifiedStyleEncoder(nn.Module):
    def __init__(
        self,
        wav2vec_model_id: str = "facebook/wav2vec2-large-xlsr-53",
        style_dim: int = 256,
        emotion_dim: int = 2,
        dialect_classes: int = 3,
        speaker_proj_dim: int = 256,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.backbone = Wav2Vec2Model.from_pretrained(wav2vec_model_id)
        hidden = int(self.backbone.config.hidden_size)

        self.attn_pool = nn.MultiheadAttention(
            embed_dim=hidden,
            num_heads=8,
            dropout=dropout,
            batch_first=True,
        )

        self.projection = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, style_dim),
            nn.LayerNorm(style_dim),
        )

        self.emotion_head = nn.Sequential(
            nn.Linear(style_dim, style_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(style_dim // 2, emotion_dim),
        )

        self.dialect_head = nn.Sequential(
            nn.Linear(style_dim, style_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(style_dim // 2, dialect_classes),
        )

        self.speaker_head = nn.Sequential(
            nn.Linear(style_dim, style_dim),
            nn.GELU(),
            nn.Linear(style_dim, speaker_proj_dim),
            nn.LayerNorm(speaker_proj_dim),
        )

    def forward(self, input_values: torch.Tensor, attention_mask: Optional[torch.Tensor] = None) -> StyleEncoderOutput:
        backbone_out = self.backbone(input_values=input_values, attention_mask=attention_mask)
        hidden_states = backbone_out.last_hidden_state

        pooled, _ = self.attn_pool(hidden_states, hidden_states, hidden_states, key_padding_mask=None)
        pooled = pooled.mean(dim=1)

        style_embedding = F.normalize(self.projection(pooled), dim=-1)
        emotion_pred = self.emotion_head(style_embedding)
        dialect_logits = self.dialect_head(style_embedding)
        speaker_proj = F.normalize(self.speaker_head(style_embedding), dim=-1)

        return StyleEncoderOutput(
            style_embedding=style_embedding,
            emotion_regression=emotion_pred,
            dialect_logits=dialect_logits,
            speaker_projection=speaker_proj,
        )

    def compute_losses(
        self,
        output: StyleEncoderOutput,
        emotion_targets: torch.Tensor,
        dialect_targets: torch.Tensor,
        speaker_positive: torch.Tensor,
        speaker_negative: torch.Tensor,
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, torch.Tensor]:
        w = {
            "emotion": 1.0,
            "dialect": 1.0,
            "speaker": 1.0,
            "total": 1.0,
        }
        if weights:
            w.update(weights)

        emotion_loss = F.mse_loss(output.emotion_regression, emotion_targets)
        dialect_loss = F.cross_entropy(output.dialect_logits, dialect_targets)

        anchor = output.speaker_projection
        pos_sim = F.cosine_similarity(anchor, F.normalize(speaker_positive, dim=-1), dim=-1)
        neg_sim = F.cosine_similarity(anchor, F.normalize(speaker_negative, dim=-1), dim=-1)
        margin = 0.2
        speaker_loss = torch.clamp(margin - pos_sim + neg_sim, min=0.0).mean()

        total = w["emotion"] * emotion_loss + w["dialect"] * dialect_loss + w["speaker"] * speaker_loss
        total = w["total"] * total

        return {
            "emotion_loss": emotion_loss,
            "dialect_loss": dialect_loss,
            "speaker_loss": speaker_loss,
            "total_loss": total,
        }
